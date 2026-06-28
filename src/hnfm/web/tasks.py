"""Celery tasks for Hacker News operations"""

import os
import json
import logging
from typing import Dict
import redis
from datetime import datetime

from .celery_app import celery_app
from ..utils.hn_utils import exists_item, get_item_json_and_store
from ..utils.run_utils import (
    scrape_url_firecrawl,
    clean_content,
    summarize_text_v1,
    save_processed_run,
)
from ..content.content_enrichment import (
    generate_short_description,
    generate_tags,
    generate_emoji,
    generate_haiku,
)
from .models import ProcessedRun, Segment, SegmentSection
from ..utils.segment_utils import (
    generate_script_v1,
    save_segment,
    k_seg,
    get_segment,
    asr_json_path,
    write_json,
)
from ..audio.audio_utils import (
    split_script_into_sections,
    tts_synthesize_to_wav,
    studio_voice_clean_inplace,
    save_section_meta,
    get_section_meta,
    list_section_numbers,
    stitch_sections_to_wav,
    update_segment_audio_status,
    k_sec,
    k_sec_list,
    sec_audio_path,
    combined_audio_path,
)
from ..audio.asr_service import ASRService

logger = logging.getLogger(__name__)


def get_redis_client(decode_responses=False):
    """Get Redis client with configuration from environment variables."""
    redis_host = os.getenv("REDIS_HOST", "localhost")
    redis_port = int(os.getenv("REDIS_PORT", "6379"))
    redis_db = int(os.getenv("REDIS_DB", "0"))

    return redis.Redis(
        host=redis_host,
        port=redis_port,
        db=redis_db,
        decode_responses=decode_responses,
    )


@celery_app.task(name="hnfm.web.tasks.hn_fetch_item")
def hn_fetch_item(item_id: int) -> Dict[str, any]:
    """Fetch and store a Hacker News item"""
    try:
        # Get Redis client
        redis_client = get_redis_client()

        # Check if item already exists
        if exists_item(item_id, redis_client=redis_client):
            logger.info(f"Item {item_id} already exists, skipping")
            return {"status": "exists", "id": item_id}

        # Get outputs directory
        outputs_dir = os.getenv("OUTPUTS_DIR", "/app/outputs")

        # Fetch and store the item
        get_item_json_and_store(
            item_id, redis_client=redis_client, outputs_dir=outputs_dir
        )

        logger.info(f"Successfully fetched and stored item {item_id}")
        return {"status": "fetched", "id": item_id}

    except Exception as e:
        logger.error(f"Failed to fetch item {item_id}: {e}")
        raise


@celery_app.task(
    name="hnfm.web.tasks.process_hn_item_run", time_limit=1800, soft_time_limit=1800
)
def process_hn_item_run(
    item_id: int, run: int = None, continue_chain: bool = False
) -> Dict[str, any]:
    """
    Process a HN item run: scrape, clean, summarize, and store.

    Steps:
    1) GET hn:item:{item_id} from Redis. If missing → raise.
    2) Parse JSON; read item['url']. If missing → raise.
    3) content_raw = scrape_url_firecrawl(url)
    4) content_clean = clean_content(content_raw)
    5) summary = summarize_text_v1(content_clean)
    6) Build ProcessedRun(...) with created_at=utcnow()
    7) save_processed_run(...)
    8) If continue_chain=True, trigger generate_segment task
    9) return {"status": "ok", "item_id": item_id, "run": run}
    """
    try:
        # Get Redis client
        redis_client = get_redis_client()

        # Get next run ID if not provided
        if run is None:
            from ..utils.run_utils import next_run_id

            run = next_run_id(item_id, redis_client=redis_client)

        # Get outputs directory
        outputs_dir = os.getenv("OUTPUTS_DIR", "/app/outputs")

        # Step 1: Get the HN item from Redis
        item_key = f"hnfm:item:{item_id}"
        item_json = redis_client.get(item_key)

        if not item_json:
            raise RuntimeError(f"Item {item_id} not found in Redis")

        # Step 2: Parse JSON and get URL
        item_data = json.loads(item_json)
        url = item_data.get("url")

        if not url:
            raise RuntimeError(f"Item {item_id} has no URL")

        # Step 3: Scrape content (non-fatal: degrade to HN title/text on failure
        # so paywalled/blocked URLs don't kill the whole pipeline)
        logger.info(f"Scraping content from {url}")
        try:
            content_raw = scrape_url_firecrawl(url)
        except Exception as scrape_err:
            logger.warning(
                f"⚠️ Scrape failed ({scrape_err}); falling back to HN title/text"
            )
            _title = item_data.get("title", "") or ""
            _text = item_data.get("text", "") or ""
            content_raw = (f"{_title}\n\n{_text}").strip() or _title or url
            if len(content_raw) < 40:
                content_raw = (
                    f"This Hacker News story is titled '{_title}'. "
                    f"The linked source could not be retrieved, so discuss the topic "
                    f"based on the title and general knowledge."
                )

        # Step 4: Clean content
        content_clean = clean_content(content_raw)

        # Step 5: Summarize content
        logger.info(f"Summarizing content for item {item_id}, run {run}")
        summary = summarize_text_v1(content_clean)

        # Step 6: Generate additional content fields. These are cosmetic metadata
        # — a flaky LLM response must NOT fail the whole video. Each falls back.
        def _safe(fn, default, label):
            try:
                return fn()
            except Exception as e:
                logger.warning(f"{label} fell back to default (non-fatal): {e}")
                return default

        logger.info(f"Generating metadata for item {item_id}, run {run}")
        short_description = _safe(lambda: generate_short_description(summary),
                                  (summary or "")[:160], "short_description")
        tags = _safe(lambda: generate_tags(summary), ["tech", "news"], "tags")
        emoji = _safe(lambda: generate_emoji(summary), ["📰", "✨", "🔥", "💡"], "emoji")
        haiku = _safe(lambda: generate_haiku(content_clean),
                      "A story unfolds\nthrough pixels and quiet code\ninsight takes its form", "haiku")

        # Step 7: Build ProcessedRun
        processed_run = ProcessedRun(
            key=f"hnfm:item:{item_id}:run:{run}",
            item_id=item_id,
            run=run,
            created_at=datetime.utcnow(),
            source_url=url,
            content_raw=content_raw,
            content_clean=content_clean,
            summary=summary,
            short_description=short_description,
            tags=tags,
            emoji=emoji,
            haiku=haiku,
        )

        # Step 8: Save to Redis and disk
        save_processed_run(
            processed_run, redis_client=redis_client, outputs_root=outputs_dir
        )

        logger.info(f"Successfully processed run {run} for item {item_id}")

        # If continue_chain is True, trigger the next task in the pipeline
        if continue_chain:
            logger.info(
                f"Continuing chain: triggering generate_segment for item {item_id}, run {run}"
            )
            generate_segment.apply_async(
                args=[item_id, run, None, True], queue="hnfm_tasks"
            )

        return {"status": "ok", "item_id": item_id, "run": run}

    except Exception as e:
        logger.error(f"Failed to process run {run} for item {item_id}: {e}")
        raise


@celery_app.task(
    name="hnfm.web.tasks.generate_segment", time_limit=1800, soft_time_limit=1800
)
def generate_segment(
    item_id: int, run: int, seg: int = None, continue_chain: bool = False
) -> Dict[str, any]:
    """
    Generate a script segment for a specific run.

    Steps:
    1) Load ProcessedRun from Redis: GET "hnfm:item:{item_id}:run:{run}".
       - If missing → raise.
    2) Extract content_clean and summary.
       - If missing/empty → raise.
    3) script = generate_script_v1(content_clean, summary)
    4) Build Segment(...)
    5) save_segment(...)
    6) If continue_chain=True, trigger build_segment_audio task
    7) return {"status":"ok","item_id":item_id,"run":run,"seg":seg}
    """
    try:
        # Get Redis client
        redis_client = get_redis_client()

        # Get next segment ID if not provided
        if seg is None:
            from ..utils.segment_utils import next_seg_id

            seg = next_seg_id(item_id, run, redis_client=redis_client)

        # Get outputs directory
        outputs_dir = os.getenv("OUTPUTS_DIR", "/app/outputs")

        # Step 1: Load ProcessedRun from Redis
        processed_run_key = f"hnfm:item:{item_id}:run:{run}"
        processed_run_json = redis_client.get(processed_run_key)

        if not processed_run_json:
            raise RuntimeError(f"ProcessedRun {processed_run_key} not found in Redis")

        # Step 2: Parse JSON and extract content_clean and summary
        processed_run_data = json.loads(processed_run_json)
        content_clean = processed_run_data.get("content_clean", "")
        summary = processed_run_data.get("summary", "")

        if not content_clean or not summary:
            raise RuntimeError(
                f"ProcessedRun {processed_run_key} missing content_clean or summary"
            )

        # Step 3: Generate script
        logger.info(
            f"Generating script for segment {seg} of run {run} for item {item_id}"
        )
        script = generate_script_v1(content_clean, summary)

        # Step 4: Build Segment
        segment = Segment(
            key=k_seg(item_id, run, seg),
            item_id=item_id,
            run=run,
            seg=seg,
            created_at=datetime.utcnow(),
            processed_run_key=processed_run_key,
            script=script,
        )

        # Step 5: Save segment
        save_segment(segment, redis_client=redis_client, outputs_root=outputs_dir)

        logger.info(
            f"Successfully generated segment {seg} for run {run} of item {item_id}"
        )

        # If continue_chain is True, trigger the next task in the pipeline
        if continue_chain:
            logger.info(
                f"Continuing chain: triggering build_segment_audio for item {item_id}, run {run}, seg {seg}"
            )
            build_segment_audio.apply_async(
                args=[item_id, run, seg, "all", None, None, True], queue="hnfm_tasks"
            )

        return {"status": "ok", "item_id": item_id, "run": run, "seg": seg}

    except Exception as e:
        logger.error(
            f"Failed to generate segment {seg} for run {run} of item {item_id}: {e}"
        )
        raise


@celery_app.task(
    name="hnfm.web.tasks.build_segment_audio", time_limit=1800, soft_time_limit=1800
)
def build_segment_audio(
    item_id: int,
    run: int,
    seg: int,
    mode: str = "all",
    section: int = None,
    text_override: str = None,
    continue_chain: bool = False,
) -> Dict[str, any]:
    """
    Build audio for segment sections.

    Args:
        item_id: Item ID
        run: Run number
        seg: Segment number
        mode: Build mode ("all" or "one")
        section: Section number (required if mode is "one")
        text_override: Override text for section (optional)

    Returns:
        Status dictionary
    """
    try:
        # Get Redis client
        redis_client = get_redis_client()

        # Get outputs directory
        outputs_dir = os.getenv("OUTPUTS_DIR", "/app/outputs")

        # Step 1: Load Segment (must exist)
        segment = get_segment(item_id, run, seg, redis_client=redis_client)
        if not segment:
            raise RuntimeError(f"Segment {item_id}:{run}:{seg} not found")

        if mode == "all":
            # Build all sections
            logger.info(
                f"Building all audio sections for segment {item_id}:{run}:{seg}"
            )

            # Step 2a: Split script into sections
            sections_text = split_script_into_sections(segment.script)
            logger.info(f"Script split into {len(sections_text)} sections")

            # Step 2b: Clear existing section list
            section_key = k_sec_list(item_id, run, seg)
            redis_client.delete(section_key)  # Clear existing sections

            # Step 2c: Generate all audio sections first
            section_metas = []
            for idx, text in enumerate(sections_text, start=1):
                logger.info(f"Processing section {idx} of {len(sections_text)}")

                # Generate audio
                out_wav = sec_audio_path(outputs_dir, item_id, run, seg, idx)
                duration = tts_synthesize_to_wav(text, out_wav)

                # Clean with studio-voice
                studio_voice_clean_inplace(out_wav)

                # Create metadata (don't save yet)
                meta = SegmentSection(
                    key=k_sec(item_id, run, seg, idx),
                    item_id=item_id,
                    run=run,
                    seg=seg,
                    section=idx,
                    text=text,
                    audio_path=out_wav,
                    cleaned=True,
                    duration_ms=duration,
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow(),
                )
                section_metas.append(meta)

            # Step 2d: Save all section metadata to Redis
            for meta in section_metas:
                # Add section to the list
                redis_client.rpush(section_key, str(meta.section))
                # Save section metadata
                save_section_meta(
                    meta, redis_client=redis_client, outputs_root=outputs_dir
                )

            # Step 2e: Get all section paths in order and stitch together
            section_numbers = list_section_numbers(
                item_id, run, seg, redis_client=redis_client
            )
            paths = [
                sec_audio_path(outputs_dir, item_id, run, seg, s)
                for s in section_numbers
            ]

            combined_path = combined_audio_path(outputs_dir, item_id, run, seg)
            total_ms = stitch_sections_to_wav(paths, combined_path)

            # Step 2f: Update segment status
            update_segment_audio_status(
                item_id,
                run,
                seg,
                sections_total=len(paths),
                combined_path=combined_path,
                ready=True,
                redis_client=redis_client,
                outputs_root=outputs_dir,
            )

            # Step 2g: ASR processing
            result_dict = {
                "status": "ok",
                "item_id": item_id,
                "run": run,
                "seg": seg,
                "sections": len(paths),
            }

            # Check if combined audio exists for ASR
            if os.path.exists(combined_path):
                try:
                    # Run ASR
                    asr_service = ASRService()
                    asr_result = asr_service.process_audio(combined_path)

                    # Persist ASR JSON
                    asr_path = asr_json_path(outputs_dir, item_id, run, seg)
                    write_json(asr_path, asr_result)

                    # QA: compare what was narrated to the script (a receipt)
                    qa = None
                    seg_obj = get_segment(item_id, run, seg, redis_client=redis_client)
                    if seg_obj:
                        try:
                            from ..audio.asr_service import asr_qa_report

                            qa = asr_qa_report(
                                asr_result.get("text", ""), seg_obj.script or ""
                            )
                            write_json(
                                asr_path.replace("asr.json", "asr_qa.json"), qa
                            )
                            logger.info(
                                f"🔎 ASR QA: {qa['verdict']} (ratio={qa['ratio']}, "
                                f"{qa['heard_words']}/{qa['script_words']} words)"
                            )
                        except Exception as qa_err:
                            logger.warning(f"ASR QA failed: {qa_err}")
                        seg_obj.asr_json_path = asr_path
                        seg_obj.asr_qa = qa
                        save_segment(
                            seg_obj, redis_client=redis_client, outputs_root=outputs_dir
                        )

                    result_dict["asr"] = "ok"
                    if qa:
                        result_dict["asr_qa"] = f"{qa['verdict']} {qa['ratio']}"
                    logger.info(
                        f"ASR processing completed for segment {item_id}:{run}:{seg}"
                    )
                except Exception as e:
                    # Fail ASR silently: keep task success, frontend will show "not ready" gracefully
                    logger.warning(
                        f"ASR processing failed for segment {item_id}:{run}:{seg}: {e}"
                    )
                    result_dict["asr"] = "error"
            else:
                logger.warning(f"Combined audio not found for ASR: {combined_path}")
                result_dict["asr"] = "no_audio"

            logger.info(
                f"Successfully built {len(paths)} audio sections for segment {item_id}:{run}:{seg}"
            )

            # If continue_chain is True, trigger the next task in the pipeline
            if continue_chain:
                logger.info(
                    f"Continuing chain: triggering build_segment_images for item {item_id}, run {run}, seg {seg}"
                )
                build_segment_images.apply_async(
                    args=[item_id, run, seg, True], queue="hnfm_tasks"
                )

            return result_dict

        elif mode == "one":
            # Build one specific section
            if section is None:
                raise ValueError("Section number required for mode 'one'")

            logger.info(
                f"Building audio section {section} for segment {item_id}:{run}:{seg}"
            )

            # Step 3a: Get text (override or existing)
            if text_override is None:
                existing_meta = get_section_meta(
                    item_id, run, seg, section, redis_client=redis_client
                )
                if not existing_meta:
                    raise RuntimeError(
                        f"Section {section} not found and no text override provided"
                    )
                text = existing_meta.text
            else:
                text = text_override

            # Step 3b: Generate audio
            out_wav = sec_audio_path(outputs_dir, item_id, run, seg, section)
            duration = tts_synthesize_to_wav(text, out_wav)

            # Step 3c: Clean with studio-voice
            studio_voice_clean_inplace(out_wav)

            # Step 3d: Create and save metadata
            meta = SegmentSection(
                key=k_sec(item_id, run, seg, section),
                item_id=item_id,
                run=run,
                seg=seg,
                section=section,
                text=text,
                audio_path=out_wav,
                cleaned=True,
                duration_ms=duration,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            save_section_meta(meta, redis_client=redis_client, outputs_root=outputs_dir)

            # Step 3e: Re-stitch all sections
            section_numbers = list_section_numbers(
                item_id, run, seg, redis_client=redis_client
            )
            paths = [
                sec_audio_path(outputs_dir, item_id, run, seg, s)
                for s in section_numbers
            ]
            combined_path = combined_audio_path(outputs_dir, item_id, run, seg)
            total_ms = stitch_sections_to_wav(paths, combined_path)

            # Step 3f: Update segment status
            update_segment_audio_status(
                item_id,
                run,
                seg,
                sections_total=len(paths),
                combined_path=combined_path,
                ready=True,
                redis_client=redis_client,
                outputs_root=outputs_dir,
            )

            logger.info(
                f"Successfully built audio section {section} for segment {item_id}:{run}:{seg}"
            )

            # Step 3g: ASR processing
            result_dict = {
                "status": "ok",
                "item_id": item_id,
                "run": run,
                "seg": seg,
                "section": section,
            }

            # Check if combined audio exists for ASR
            if os.path.exists(combined_path):
                try:
                    # Run ASR
                    asr_service = ASRService()
                    asr_result = asr_service.process_audio(combined_path)

                    # Persist ASR JSON
                    asr_path = asr_json_path(outputs_dir, item_id, run, seg)
                    write_json(asr_path, asr_result)

                    # QA: compare what was narrated to the script (a receipt)
                    qa = None
                    seg_obj = get_segment(item_id, run, seg, redis_client=redis_client)
                    if seg_obj:
                        try:
                            from ..audio.asr_service import asr_qa_report

                            qa = asr_qa_report(
                                asr_result.get("text", ""), seg_obj.script or ""
                            )
                            write_json(
                                asr_path.replace("asr.json", "asr_qa.json"), qa
                            )
                            logger.info(
                                f"🔎 ASR QA: {qa['verdict']} (ratio={qa['ratio']}, "
                                f"{qa['heard_words']}/{qa['script_words']} words)"
                            )
                        except Exception as qa_err:
                            logger.warning(f"ASR QA failed: {qa_err}")
                        seg_obj.asr_json_path = asr_path
                        seg_obj.asr_qa = qa
                        save_segment(
                            seg_obj, redis_client=redis_client, outputs_root=outputs_dir
                        )

                    result_dict["asr"] = "ok"
                    if qa:
                        result_dict["asr_qa"] = f"{qa['verdict']} {qa['ratio']}"
                    logger.info(
                        f"ASR processing completed for segment {item_id}:{run}:{seg}"
                    )
                except Exception as e:
                    # Fail ASR silently: keep task success, frontend will show "not ready" gracefully
                    logger.warning(
                        f"ASR processing failed for segment {item_id}:{run}:{seg}: {e}"
                    )
                    result_dict["asr"] = "error"
            else:
                logger.warning(f"Combined audio not found for ASR: {combined_path}")
                result_dict["asr"] = "no_audio"

            # If continue_chain is True, trigger the next task in the pipeline
            if continue_chain:
                logger.info(
                    f"Continuing chain: triggering build_segment_images for item {item_id}, run {run}, seg {seg}"
                )
                build_segment_images.apply_async(
                    args=[item_id, run, seg, True], queue="hnfm_tasks"
                )

            return result_dict

        else:
            raise ValueError(f"Invalid mode: {mode}. Must be 'all' or 'one'")

    except Exception as e:
        logger.error(f"Failed to build audio for segment {item_id}:{run}:{seg}: {e}")
        raise


@celery_app.task(
    name="hnfm.web.tasks.build_segment_images", time_limit=7200, soft_time_limit=7200
)
def build_segment_images(
    item_id: int, run: int, seg: int, continue_chain: bool = False
) -> Dict:
    """
    Build all prompts & images for a segment.

    1) Load Segment; require non-empty script. If empty → raise.
    2) Determine text chunks: sections = split_script_into_sections(segment.script)
    3) Determine alignment (optional): align = alignment_from_sections(...) or None
    4) Load ProcessedRun summary via segment.processed_run_key; use as context.
    5) Loop i, text in enumerate(sections, start=1):
        prompt = generate_image_prompt_v1(text, run_summary)
        out = img_path(..., index=i)
        generate_image_from_prompt(prompt, out)
        start_ms, duration_ms = align[i-1] if align else (None, None)
        si = SegmentImage(...)
        save_segment_image(si, ...)
    6) update_segment_images_status(..., total=len(sections), ready=True)
    7) return {"status":"ok","item_id":item_id,"run":run,"seg":seg,"images":len(sections)}
    """
    try:
        from ..utils.segment_utils import (
            get_segment,
            alignment_from_sections,
            generate_image_prompt_v1,
            generate_image_from_prompt,
            img_path,
            k_img,
            save_segment_image,
            update_segment_images_status,
        )
        from ..audio.audio_utils import split_script_into_sections
        from ..utils.run_utils import get_run
        from .models import SegmentImage

        # Get Redis client
        redis_client = get_redis_client()

        # Get outputs directory
        outputs_root = os.getenv("OUTPUTS_DIR", "/app/outputs")

        # 1) Load Segment; require non-empty script
        segment = get_segment(item_id, run, seg, redis_client=redis_client)
        if not segment:
            raise RuntimeError(f"Segment not found: {item_id}:{run}:{seg}")

        if not segment.script.strip():
            raise RuntimeError("Script not ready")

        # 2) Determine text chunks
        sections = split_script_into_sections(segment.script)
        logger.info(f"Split script into {len(sections)} sections for images")

        # 3) Determine alignment (optional)
        align = alignment_from_sections(item_id, run, seg, redis_client=redis_client)
        if align:
            logger.info(f"Found alignment data: {len(align)} sections")
        else:
            logger.info("No alignment data available")

        # 4) Load ProcessedRun summary
        processed_run = get_run(segment.item_id, segment.run, redis_client=redis_client)
        if not processed_run:
            raise RuntimeError(
                f"ProcessedRun not found: {segment.item_id}:{segment.run}"
            )

        run_summary = processed_run.summary
        logger.info(f"Using run summary: {run_summary[:100]}...")

        # Art direction: pick a cohesive visual theme for this take. Stable per
        # take, varied across takes; honor a pre-set theme (multi-take override).
        from ..content.art_direction import get_theme, pick_theme

        theme = get_theme(segment.style_theme) or pick_theme(
            seed=item_id + run * 131 + seg * 977
        )
        segment.style_theme = theme.key
        segment.style_theme_name = theme.name
        redis_client.set(segment.key, segment.model_dump_json())

        # Aspect format for this take -> image/video/subtitle dimensions
        from ..content.art_direction import format_dims

        _fmt = getattr(segment, "aspect_format", None) or "16:9"
        _w, _h = format_dims(_fmt)
        logger.info(f"🎨 Take theme: {theme.name} ({theme.key}) · format {_fmt} {_w}x{_h}")

        # Cycle shot types so compositions vary within the take.
        SHOTS = [
            "wide establishing shot",
            "extreme macro detail",
            "high overhead / top-down view",
            "dramatic low-angle hero shot",
            "over-the-shoulder perspective",
            "symbolic conceptual metaphor",
            "intimate close-up",
            "dynamic dutch-angle composition",
        ]

        # 5) Loop through sections and generate images
        for i, text in enumerate(sections, start=1):
            logger.info(f"Processing section {i}/{len(sections)}: {text[:50]}...")

            # Generate prompt (varied scene + the take's theme)
            shot_hint = SHOTS[(i - 1) % len(SHOTS)]
            prompt = generate_image_prompt_v1(
                text, run_summary, theme=theme, shot_hint=shot_hint
            )
            logger.info(f"Generated prompt: {prompt[:100]}...")

            # Generate the root frame (text-to-image) at the take's format
            out = img_path(outputs_root, item_id, run, seg, i)
            generate_image_from_prompt(prompt, out, width=_w, height=_h)
            logger.info(f"Generated image: {out}")

            # Alignment (start/duration) — drives sequence length + timeline
            start_ms, duration_ms = (
                align[i - 1] if align and i <= len(align) else (None, None)
            )

            # Image sequence: evolve the root into N frames via image-to-image
            # edits (count scales with spoken duration). Non-fatal per frame.
            sequence_paths = [out]
            if os.getenv("SEQ_ENABLED", "true").lower() == "true":
                from ..content.art_direction import frames_for_duration
                from ..content.sequence_planner import plan_sequence_edits
                from ..utils.segment_utils import img_dir as _img_dir

                dur_s = (duration_ms / 1000.0) if duration_ms else (len(text.split()) / 2.5)
                n_frames = frames_for_duration(dur_s)
                if n_frames > 1:
                    try:
                        from ..image.image_service_factory import ImageServiceFactory

                        svc = ImageServiceFactory.create_image_service()
                    except Exception:
                        svc = None
                    # Plan content-evolving edits by LOOKING at the root frame
                    # (Nemotron vision) — unique per section, not a fixed cycle.
                    edit_prompts = plan_sequence_edits(
                        out, text, (theme.name if theme else ""),
                        n_frames - 1, seed=item_id * 131 + i * 977,
                    )
                    prev = out
                    for k in range(2, n_frames + 1):
                        if not svc or not hasattr(svc, "generate_and_save_edit"):
                            break
                        try:
                            fdir = _img_dir(outputs_root, item_id, run, seg, i)
                            fname = f"frame_{k}.png"
                            directive = edit_prompts[k - 2] if (k - 2) < len(edit_prompts) else ""
                            # Reinforce continuity + theme; the directive carries
                            # the (content) change to make this frame.
                            edit_prompt = (
                                f"{directive}. Keep the same scene, characters and "
                                f"{(theme.name if theme else '')} style; coherent, high quality."
                            )
                            svc.generate_and_save_edit(
                                edit_prompt, prev, fdir, fname, width=_w, height=_h,
                            )
                            fp = os.path.join(fdir, fname)
                            sequence_paths.append(fp)
                            prev = fp
                        except Exception as se:
                            logger.warning(f"seq frame {k}/{n_frames} sec {i} failed: {se}")
                            break
                    logger.info(
                        f"🖼️  Section {i}: image sequence of {len(sequence_paths)} frames "
                        f"(vision-planned)"
                    )

            # Create SegmentImage
            si = SegmentImage(
                key=k_img(item_id, run, seg, i),
                item_id=item_id,
                run=run,
                seg=seg,
                index=i,
                line_text=text,
                prompt=prompt,
                image_path=out,
                sequence_paths=sequence_paths,
                start_ms=start_ms,
                duration_ms=duration_ms,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )

            # Save to Redis and disk
            save_segment_image(si, redis_client=redis_client, outputs_root=outputs_root)
            logger.info(f"Saved image {i} metadata")

        # 6) Update segment image status
        update_segment_images_status(
            item_id,
            run,
            seg,
            total=len(sections),
            ready=True,
            redis_client=redis_client,
            outputs_root=outputs_root,
        )

        logger.info(
            f"Successfully generated {len(sections)} images for segment {item_id}:{run}:{seg}"
        )

        # If continue_chain is True, trigger the next task in the pipeline
        if continue_chain:
            logger.info(
                f"Continuing chain: triggering generate_segment_video for item {item_id}, run {run}, seg {seg}"
            )
            generate_segment_video.apply_async(
                args=[item_id, run, seg, True], queue="hnfm_tasks"
            )

        # 7) Return result
        return {
            "status": "ok",
            "item_id": item_id,
            "run": run,
            "seg": seg,
            "images": len(sections),
        }

    except Exception as e:
        logger.error(f"Failed to build images for segment {item_id}:{run}:{seg}: {e}")
        raise


@celery_app.task(
    name="hnfm.web.tasks.rebuild_single_image", time_limit=3600, soft_time_limit=3600
)
def rebuild_single_image(
    item_id: int,
    run: int,
    seg: int,
    index: int,
    prompt_override: str = None,
    line_override: str = None,
) -> Dict:
    """
    Regenerate a single image (with optional prompt/line override).

    1) Load existing SegmentImage if present; else create shell using current script chunk at index.
    2) Decide line_text: line_override or existing or split_script index text.
    3) Decide prompt: prompt_override or generate_image_prompt_v1(line_text, run_summary).
    4) out = img_path(..., index)
       generate_image_from_prompt(prompt, out)  # overwrite
    5) Compute alignment if available; set start_ms/duration_ms.
    6) Save SegmentImage with updated prompt/line_text/image_path/updated_at.
    7) return {"status":"ok","item_id":...,"run":...,"seg":...,"index":index}
    """
    try:
        from ..utils.segment_utils import (
            get_segment,
            get_segment_image,
            alignment_from_sections,
            generate_image_prompt_v1,
            generate_image_from_prompt,
            img_path,
            k_img,
            save_segment_image,
        )
        from ..audio.audio_utils import split_script_into_sections
        from ..utils.run_utils import get_run
        from .models import SegmentImage

        # Get Redis client
        redis_client = get_redis_client()

        # Get outputs directory
        outputs_root = os.getenv("OUTPUTS_DIR", "/app/outputs")

        # 1) Load existing SegmentImage or create shell
        existing_image = get_segment_image(
            item_id, run, seg, index, redis_client=redis_client
        )

        # Load segment for script access
        segment = get_segment(item_id, run, seg, redis_client=redis_client)
        if not segment:
            raise RuntimeError(f"Segment not found: {item_id}:{run}:{seg}")

        # 2) Decide line_text
        if line_override:
            line_text = line_override
        elif existing_image:
            line_text = existing_image.line_text
        else:
            # Get from script sections
            sections = split_script_into_sections(segment.script)
            if index <= len(sections):
                line_text = sections[index - 1]
            else:
                raise RuntimeError(
                    f"Index {index} out of range for {len(sections)} sections"
                )

        # 3) Decide prompt
        if prompt_override:
            prompt = prompt_override
        else:
            # Load ProcessedRun summary for context
            processed_run = get_run(
                segment.item_id, segment.run, redis_client=redis_client
            )
            if not processed_run:
                raise RuntimeError(
                    f"ProcessedRun not found: {segment.item_id}:{segment.run}"
                )

            run_summary = processed_run.summary
            prompt = generate_image_prompt_v1(line_text, run_summary)

        # 4) Generate image
        out = img_path(outputs_root, item_id, run, seg, index)
        generate_image_from_prompt(prompt, out)
        logger.info(f"Regenerated image: {out}")

        # 5) Compute alignment if available
        align = alignment_from_sections(item_id, run, seg, redis_client=redis_client)
        start_ms, duration_ms = (
            align[index - 1] if align and index <= len(align) else (None, None)
        )

        # 6) Save SegmentImage
        si = SegmentImage(
            key=k_img(item_id, run, seg, index),
            item_id=item_id,
            run=run,
            seg=seg,
            index=index,
            line_text=line_text,
            prompt=prompt,
            image_path=out,
            start_ms=start_ms,
            duration_ms=duration_ms,
            created_at=(
                existing_image.created_at if existing_image else datetime.utcnow()
            ),
            updated_at=datetime.utcnow(),
        )

        save_segment_image(si, redis_client=redis_client, outputs_root=outputs_root)
        logger.info(f"Saved regenerated image {index} metadata")

        # 7) Return result
        return {
            "status": "ok",
            "item_id": item_id,
            "run": run,
            "seg": seg,
            "index": index,
        }

    except Exception as e:
        logger.error(
            f"Failed to rebuild image {index} for segment {item_id}:{run}:{seg}: {e}"
        )
        raise


def ingest_source_images(item_id: int, run: int) -> Dict[str, any]:
    """Pull, rank, describe and store the best real images from the article.

    Stored under redis key `hnfm:item:{id}:run:{run}:source_images` + a JSON on
    disk. Gated on SOURCE_IMAGES_ENABLED; always non-fatal.
    """
    if os.getenv("SOURCE_IMAGES_ENABLED", "false").lower() != "true":
        return {"status": "skipped", "reason": "SOURCE_IMAGES_ENABLED!=true"}

    import json as _json
    from ..scraper.source_images import ingest
    from ..utils.run_utils import get_run

    redis_client = get_redis_client()
    outputs_root = os.getenv("OUTPUTS_DIR", "/app/outputs")
    pr = get_run(item_id, run, redis_client=redis_client)
    if not pr or not getattr(pr, "source_url", None):
        return {"status": "skipped", "reason": "no run/url"}

    out_dir = os.path.join(
        outputs_root, "hn", "item", str(item_id), "runs", str(run), "source_images"
    )
    results = ingest(
        pr.source_url, pr.summary or "", out_dir,
        top_n=int(os.getenv("SOURCE_IMAGES_TOP_N", "4")),
    )
    redis_client.set(
        f"hnfm:item:{item_id}:run:{run}:source_images", _json.dumps(results)
    )
    try:
        os.makedirs(out_dir, exist_ok=True)
        with open(os.path.join(out_dir, "source_images.json"), "w") as f:
            f.write(_json.dumps(results, indent=2))
    except Exception:
        pass
    return {"status": "ok", "count": len(results)}


def build_segment_motion_clips(item_id: int, run: int, seg: int) -> Dict[str, any]:
    """Generate LTX-2 motion clips for the N longest sections (most screen time).

    Each clip animates that section's root image and is stretched to the section's
    spoken duration. Stored on SegmentImage.video_clip_path; the timeline then uses
    the clip for that slot instead of a still/sequence. Non-fatal + gated on
    VIDEO_ENABLED so it never blocks the pipeline.
    """
    if os.getenv("VIDEO_ENABLED", "false").lower() != "true":
        return {"status": "skipped", "reason": "VIDEO_ENABLED!=true"}

    from ..utils.segment_utils import (
        get_segment,
        get_segment_image,
        save_segment_image,
        list_section_numbers,
        load_section_and_image,
        img_dir,
    )
    from ..content.art_direction import format_dims
    from ..video.ltx_service import make_motion_clip, clip_target_seconds

    redis_client = get_redis_client()
    outputs_root = os.getenv("OUTPUTS_DIR", "/app/outputs")
    n_clips = int(os.getenv("VIDEO_CLIPS_PER_SEGMENT", "2"))

    segment = get_segment(item_id, run, seg, redis_client=redis_client)
    if not segment:
        return {"status": "error", "reason": "no segment"}
    w, h = format_dims(getattr(segment, "aspect_format", None) or "16:9")

    # Collect sections with a root image + their real (audio) durations.
    rows = []
    for idx in list_section_numbers(item_id, run, seg, redis_client=redis_client):
        si = get_segment_image(item_id, run, seg, idx, redis_client=redis_client)
        if not si or not si.image_path or not os.path.exists(si.image_path):
            continue
        data = load_section_and_image(item_id, run, seg, idx, redis_client=redis_client)
        dur = (data.get("duration_ms") or 0) / 1000.0
        rows.append((idx, si, dur))
    if not rows:
        return {"status": "skipped", "reason": "no images"}

    chosen = sorted(rows, key=lambda r: r[2], reverse=True)[:n_clips]
    made = 0
    for j, (idx, si, dur) in enumerate(chosen):
        # A real 3-4s clip, stretched only a little; the rest of the section
        # falls back to the image sequence (handled in build_timeline).
        target = clip_target_seconds(dur)
        clip_out = os.path.join(img_dir(outputs_root, item_id, run, seg, idx), "motion.mp4")
        logger.info(f"🎞️ LTX motion clip: section {idx} ({dur:.1f}s) -> clip {target:.1f}s")
        if make_motion_clip(si.image_path, si.prompt, clip_out, target, w, h, idx=j):
            si.video_clip_path = clip_out
            si.video_clip_seconds = target
            save_segment_image(si, redis_client=redis_client, outputs_root=outputs_root)
            made += 1
        else:
            logger.warning(f"motion clip failed for section {idx} (non-fatal)")
    return {"status": "ok", "clips": made}


def build_segment_media_plan(item_id: int, run: int, seg: int) -> Dict[str, any]:
    """Agentic meta-sequencer: plan per-section template, then produce the media.

    Falls back to the LTX-only heuristic when META_SEQUENCER_ENABLED is off.
    image_sequence sections need no work (build_segment_images already made them);
    'video' → LTX motion clip, 'hyperframe' → HyperFrames kinetic-text clip. Both
    play their length and the image sequence fills the rest (partial coverage).
    """
    if os.getenv("META_SEQUENCER_ENABLED", "false").lower() != "true":
        return build_segment_motion_clips(item_id, run, seg)

    import json as _json
    from ..utils.segment_utils import (
        get_segment, get_segment_image, save_segment_image,
        list_section_numbers, load_section_and_image, img_dir,
    )
    from ..audio.audio_utils import split_script_into_sections
    from ..utils.run_utils import get_run
    from ..utils import metrics
    from ..content.art_direction import format_dims
    from ..content.meta_sequencer import plan_segment
    from ..video.ltx_service import make_motion_clip, clip_target_seconds

    redis_client = get_redis_client()
    outputs_root = os.getenv("OUTPUTS_DIR", "/app/outputs")

    segment = get_segment(item_id, run, seg, redis_client=redis_client)
    if not segment:
        return {"status": "error", "reason": "no segment"}
    theme_key = getattr(segment, "style_theme", None) or "default"
    theme_name = getattr(segment, "style_theme_name", None) or theme_key
    w, h = format_dims(getattr(segment, "aspect_format", None) or "16:9")
    sections = split_script_into_sections(segment.script)

    pr = get_run(item_id, run, redis_client=redis_client)
    summary = (pr.summary if pr else "") or ""
    src_raw = redis_client.get(f"hnfm:item:{item_id}:run:{run}:source_images")
    source_images = _json.loads(src_raw) if src_raw else []

    plan = plan_segment(
        sections, summary, theme_name, source_images,
        max_video=int(os.getenv("META_MAX_VIDEO", "2")),
        max_hyper=int(os.getenv("META_MAX_HYPER", "2")),
    )
    segment.meta_plan = plan
    redis_client.set(segment.key, segment.model_dump_json())

    made = {"video": 0, "hyperframe": 0}
    hf_enabled = os.getenv("HYPERFRAMES_ENABLED", "false").lower() == "true"
    for p in plan:
        t = p.get("template")
        if t not in ("video", "hyperframe"):
            continue
        idx = p["index"]
        si = get_segment_image(item_id, run, seg, idx, redis_client=redis_client)
        if not si or not si.image_path or not os.path.exists(si.image_path):
            continue
        data = load_section_and_image(item_id, run, seg, idx, redis_client=redis_client)
        dur = (data.get("duration_ms") or 0) / 1000.0
        out_dir = img_dir(outputs_root, item_id, run, seg, idx)

        if t == "video":
            target = clip_target_seconds(dur)
            clip = os.path.join(out_dir, "motion.mp4")
            if make_motion_clip(si.image_path, si.prompt, clip, target, w, h, idx=idx):
                si.video_clip_path = clip
                si.video_clip_seconds = target
                save_segment_image(si, redis_client=redis_client, outputs_root=outputs_root)
                made["video"] += 1
                metrics.count(item_id, run, seg, "ltx_clips")
            else:
                metrics.count(item_id, run, seg, "ltx_failures")
        elif t == "hyperframe" and hf_enabled:
            from ..hyperframes.produce import produce_hyperframe_clip

            hf_dur = min(dur if dur > 0 else 5.0, float(os.getenv("HF_MAX_SECONDS", "5")))
            clip = produce_hyperframe_clip(
                out_dir, p.get("recipe", "keypoints"), p.get("content", {}),
                theme_key, w, h, hf_dur, bg_image=si.image_path,
            )
            if clip:
                si.video_clip_path = clip
                si.video_clip_seconds = hf_dur
                save_segment_image(si, redis_client=redis_client, outputs_root=outputs_root)
                made["hyperframe"] += 1
                metrics.count(item_id, run, seg, "hyperframes")
            else:
                metrics.count(item_id, run, seg, "hyperframe_failures")
    # plan composition (what the director chose) for the dashboard
    plan_counts = {}
    for p in plan:
        plan_counts[p["template"]] = plan_counts.get(p["template"], 0) + 1
    metrics.count(item_id, run, seg, "sections", len(plan))
    metrics.count(item_id, run, seg, "planned_video", plan_counts.get("video", 0))
    metrics.count(item_id, run, seg, "planned_hyperframe", plan_counts.get("hyperframe", 0))
    logger.info(f"🎬 meta-sequence executed: {made}")
    return {"status": "ok", **made}


@celery_app.task(
    name="hnfm.web.tasks.full_pipeline", time_limit=10800, soft_time_limit=10800
)
def full_pipeline(
    item_id: int, aspect_format: str = None, style_theme: str = None
) -> Dict[str, any]:
    """
    Run the entire pipeline in a single task for an item.

    This task orchestrates all pipeline steps linearly without using apply_async,
    so continue_chain should be set to False for all sub-tasks.

    Steps:
    1) Process HN item run (scrape, clean, summarize)
    2) Generate segment (script generation)
    3) Build segment audio (TTS, ASR)
    4) Build segment images (image generation)
    5) Generate segment video (video creation)

    Args:
        item_id: The HN item ID to process

    Returns:
        Dict with status and results
    """
    try:
        logger.info(f"🚀 Starting full pipeline for item {item_id}")

        # Get Redis client
        redis_client = get_redis_client()

        # Get next run ID
        from ..utils.run_utils import next_run_id

        run = next_run_id(item_id, redis_client=redis_client)

        import time as _time
        from ..utils import metrics

        logger.info(f"📝 Step 1/5: Processing run {run} for item {item_id}")
        # Step 1: Process HN item run (with continue_chain=False)
        _t = _time.time()
        run_result = process_hn_item_run(item_id, run, continue_chain=False)
        _scrape_s = _time.time() - _t
        logger.info(f"✅ Run processing completed: {run_result}")

        # Step 1b: ingest real source images from the article (optional, non-fatal)
        _t = _time.time()
        _src_count = 0
        try:
            src_img_result = ingest_source_images(item_id, run)
            _src_count = (src_img_result or {}).get("count", 0)
            logger.info(f"📸 Source images: {src_img_result}")
        except Exception as _se:
            logger.warning(f"source images skipped (non-fatal): {_se}")
        _srcimg_s = _time.time() - _t

        # Get next segment ID
        from ..utils.segment_utils import next_seg_id

        seg = next_seg_id(item_id, run, redis_client=redis_client)

        # Begin metrics for this run
        metrics.init(item_id, run, seg, theme=style_theme, fmt=aspect_format)
        metrics.record_seconds(item_id, run, seg, "scrape", _scrape_s)
        metrics.record_seconds(item_id, run, seg, "source_images", _srcimg_s)
        metrics.count(item_id, run, seg, "source_images", _src_count)

        logger.info(f"📝 Step 2/5: Generating segment {seg} for run {run}")
        # Step 2: Generate segment (with continue_chain=False)
        with metrics.stage(item_id, run, seg, "script"):
            segment_result = generate_segment(item_id, run, seg, continue_chain=False)
        logger.info(f"✅ Segment generation completed: {segment_result}")

        # Apply requested take format/theme (multi-take / multi-format)
        if aspect_format or style_theme:
            from ..utils.segment_utils import get_segment

            _seg = get_segment(item_id, run, seg, redis_client=redis_client)
            if _seg:
                if aspect_format:
                    _seg.aspect_format = aspect_format
                if style_theme:
                    _seg.style_theme = style_theme
                redis_client.set(_seg.key, _seg.model_dump_json())
                logger.info(
                    f"🎛️ Take format={_seg.aspect_format} theme={_seg.style_theme}"
                )

        logger.info(f"📝 Step 3/5: Building audio for segment {seg}")
        # Step 3: Build segment audio (with continue_chain=False)
        with metrics.stage(item_id, run, seg, "audio"):
            audio_result = build_segment_audio(
                item_id, run, seg, "all", None, None, continue_chain=False
            )
        logger.info(f"✅ Audio building completed: {audio_result}")

        logger.info(f"📝 Step 4/5: Building images for segment {seg}")
        # Step 4: Build segment images (with continue_chain=False)
        with metrics.stage(item_id, run, seg, "images"):
            images_result = build_segment_images(item_id, run, seg, continue_chain=False)
        metrics.count(item_id, run, seg, "images", (images_result or {}).get("images", 0))
        logger.info(f"✅ Image building completed: {images_result}")

        # Step 4b: agentic meta-sequence — plan + produce per-section media
        # (LTX video / hyperframes); falls back to LTX-only heuristic. Non-fatal.
        try:
            with metrics.stage(item_id, run, seg, "media_plan"):
                plan_result = build_segment_media_plan(item_id, run, seg)
            logger.info(f"🎬 Media plan: {plan_result}")
        except Exception as _ve:
            logger.warning(f"media plan skipped (non-fatal): {_ve}")

        logger.info(f"📝 Step 5/5: Generating video for segment {seg}")
        # Step 5: Generate segment video (with continue_chain=False)
        with metrics.stage(item_id, run, seg, "video"):
            video_result = generate_segment_video(item_id, run, seg, continue_chain=False)
        logger.info(f"✅ Video generation completed: {video_result}")

        metrics.finalize(item_id, run, seg, status="ok")

        logger.info(
            f"🎉 Full pipeline completed successfully for item {item_id}, run {run}, seg {seg}"
        )

        return {
            "status": "completed",
            "item_id": item_id,
            "run": run,
            "seg": seg,
            "steps_completed": 5,
            "results": {
                "run": run_result,
                "segment": segment_result,
                "audio": audio_result,
                "images": images_result,
                "video": video_result,
            },
        }

    except Exception as e:
        logger.error(f"❌ Full pipeline failed for item {item_id}: {e}")
        raise


@celery_app.task(
    name="hnfm.web.tasks.generate_segment_video", time_limit=3600, soft_time_limit=3600
)
def generate_segment_video(
    item_id: int, run: int, seg: int, continue_chain: bool = False
) -> Dict:
    """
    Generate video for a segment from audio, images, and timeline.

    Steps:
    1) Load Segment and validate prerequisites
    2) Build timeline from sections and images
    3) Create video directory
    4) Write subtitles VTT file
    5) Save timeline debug JSON
    6) Call VideoGenerator to create video
    7) Update segment video fields

    Args:
        item_id: Item ID
        run: Run number
        seg: Segment number

    Returns:
        Dict with status and metadata
    """
    try:
        # Get configuration
        outputs_root = os.getenv("OUTPUTS_ROOT", "outputs")

        # Get Redis client (with decode_responses=True for this function)
        redis_client = get_redis_client(decode_responses=True)

        logger.info(f"🎬 Starting video generation for segment {item_id}:{run}:{seg}")

        # 1) Load Segment and validate prerequisites
        segment = get_segment(item_id, run, seg, redis_client=redis_client)
        if not segment:
            raise RuntimeError(f"Segment not found: {item_id}:{run}:{seg}")

        if not segment.script:
            raise RuntimeError(f"Segment script is empty: {item_id}:{run}:{seg}")

        if not segment.audio_ready or not segment.audio_combined_path:
            raise RuntimeError(f"Segment audio not ready: {item_id}:{run}:{seg}")

        if not segment.images_ready:
            raise RuntimeError(f"Segment images not ready: {item_id}:{run}:{seg}")

        if not os.path.exists(segment.audio_combined_path):
            raise RuntimeError(f"Audio file not found: {segment.audio_combined_path}")

        logger.info(f"✅ Prerequisites validated for segment {item_id}:{run}:{seg}")

        # 2) Build timeline from sections and images
        from ..utils.segment_utils import build_timeline

        timeline = build_timeline(item_id, run, seg, redis_client=redis_client)

        if not timeline:
            raise RuntimeError(
                f"No timeline data generated for segment {item_id}:{run}:{seg}"
            )

        logger.info(f"📊 Built timeline with {len(timeline)} items")

        # 3) Create video directory
        from ..utils.segment_utils import (
            video_dir,
            video_path,
            subtitles_path,
            timeline_path,
        )

        video_dir_path = video_dir(outputs_root, item_id, run, seg)
        os.makedirs(video_dir_path, exist_ok=True)

        # 4) Write subtitles file from ASR data or timeline
        from ..utils.segment_utils import write_ass_from_asr, write_vtt_from_timeline
        from ..content.art_direction import format_dims

        _fmt = getattr(segment, "aspect_format", None) or "16:9"
        _vw, _vh = format_dims(_fmt)

        # Initialize subtitle path variable
        subtitle_path = None

        # Load ASR data if available
        if segment.asr_json_path and os.path.exists(segment.asr_json_path):
            # Generate word-level ASS subtitles from ASR data
            ass_path = subtitles_path(outputs_root, item_id, run, seg).replace(
                ".vtt", ".ass"
            )
            import json

            with open(segment.asr_json_path, "r") as f:
                asr_data = json.load(f)
            write_ass_from_asr(asr_data, ass_path, width=_vw, height=_vh)
            subtitle_path = ass_path
            logger.info(f"📝 Created word-level ASS subtitles: {ass_path}")
        else:
            # Fallback to VTT from timeline if no ASR data
            vtt_path = subtitles_path(outputs_root, item_id, run, seg)
            write_vtt_from_timeline(timeline, vtt_path)
            subtitle_path = vtt_path
            logger.info(f"📝 Created VTT subtitles (fallback): {vtt_path}")

        # 5) Save timeline debug JSON
        timeline_debug_path = timeline_path(outputs_root, item_id, run, seg)
        write_json(timeline_debug_path, {"timeline": timeline})
        logger.info(f"📋 Saved timeline debug: {timeline_debug_path}")

        # 6) Create combined audio with intro
        from ..video.video_generator import VideoGenerator
        from pathlib import Path
        import tempfile

        video_generator = VideoGenerator()

        # Check if intro audio exists and create combined audio
        intro_audio_path = (
            Path(__file__).parent.parent / "video" / "media" / "intro.wav"
        )
        combined_audio_path = segment.audio_combined_path

        # Create a temporary combined audio file with intro + segment audio + outro silence
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_audio:
            temp_audio_path = temp_audio.name

        # Use ffmpeg to create: intro + segment audio + 4 seconds of silence for outro
        import subprocess

        if intro_audio_path.exists():
            # Combine intro + segment audio + outro silence
            cmd = [
                "ffmpeg",
                "-y",  # Overwrite output file
                "-i",
                str(intro_audio_path),
                "-i",
                segment.audio_combined_path,
                "-f",
                "lavfi",
                "-i",
                "anullsrc=channel_layout=stereo:sample_rate=48000",
                "-filter_complex",
                "[0:a][1:a]concat=n=2:v=0:a=1[main];[2:a]atrim=duration=4[outro];[main][outro]concat=n=2:v=0:a=1[final]",
                "-map",
                "[final]",
                temp_audio_path,
            ]
        else:
            # Just segment audio + outro silence
            cmd = [
                "ffmpeg",
                "-y",  # Overwrite output file
                "-i",
                segment.audio_combined_path,
                "-f",
                "lavfi",
                "-i",
                "anullsrc=channel_layout=stereo:sample_rate=48000",
                "-filter_complex",
                "[0:a][1:a]concat=n=2:v=0:a=1[final]",
                "-map",
                "[final]",
                temp_audio_path,
            ]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            combined_audio_path = temp_audio_path
            logger.info(
                f"🎵 Combined audio with intro + segment + outro silence: {combined_audio_path}"
            )
        except subprocess.CalledProcessError as e:
            logger.warning(f"Failed to combine audio, using segment audio only: {e}")
            combined_audio_path = segment.audio_combined_path

        # Themed low-volume music bed under the whole video (optional, non-fatal).
        if os.getenv("MUSIC_ENABLED", "false").lower() == "true":
            try:
                from ..audio.music_service import generate_music_bed
                from ..content.art_direction import get_theme

                _theme = get_theme(segment.style_theme)
                _mood = (_theme.mood if _theme else "") or "energetic modern"
                _music_wav = os.path.join(
                    video_dir(outputs_root, item_id, run, seg), "music_bed.wav"
                )
                if generate_music_bed(
                    f"instrumental {_mood} electronic tech background music, "
                    f"steady groove, no vocals, loopable",
                    _music_wav,
                ):
                    # duration of the narration track to size the bed
                    _dur = float(
                        subprocess.run(
                            ["ffprobe", "-v", "error", "-show_entries",
                             "format=duration", "-of", "csv=p=0", combined_audio_path],
                            capture_output=True, text=True,
                        ).stdout.strip() or 0
                    )
                    _vol = os.getenv("MUSIC_BED_VOLUME", "0.14")
                    _mixed = combined_audio_path.replace(".wav", "_music.wav")
                    _fade = max(0.0, _dur - 2.5)
                    mcmd = [
                        "ffmpeg", "-y",
                        "-i", combined_audio_path,
                        "-stream_loop", "-1", "-i", _music_wav,
                        "-filter_complex",
                        f"[1:a]volume={_vol},afade=t=in:st=0:d=1.5,"
                        f"afade=t=out:st={_fade}:d=2.5[bed];"
                        f"[0:a][bed]amix=inputs=2:duration=first:dropout_transition=0[a]",
                        "-map", "[a]", _mixed,
                    ]
                    mr = subprocess.run(mcmd, capture_output=True, text=True)
                    if mr.returncode == 0 and os.path.exists(_mixed):
                        combined_audio_path = _mixed
                        logger.info(f"🎵 Mixed music bed (vol={_vol}) under narration")
                    else:
                        logger.warning(f"music mix failed: {mr.stderr[:160]}")
            except Exception as _m:
                logger.warning(f"music bed skipped (non-fatal): {_m}")

        output_video_path = video_path(outputs_root, item_id, run, seg)

        result = video_generator.create_video(
            audio_path=combined_audio_path,
            timeline=timeline,
            subtitles_path=subtitle_path,
            output_path=output_video_path,
            size=(_vw, _vh),
            fps=30,
        )

        if not result.get("success"):
            raise RuntimeError(f"Video generation failed: {result}")

        logger.info(f"🎥 Video generated successfully: {output_video_path}")

        # Clean up temporary audio file if it was created
        if combined_audio_path != segment.audio_combined_path and os.path.exists(
            combined_audio_path
        ):
            try:
                os.unlink(combined_audio_path)
                logger.debug(
                    f"🧹 Cleaned up temporary audio file: {combined_audio_path}"
                )
            except Exception as e:
                logger.warning(f"Failed to clean up temporary audio file: {e}")

        # 7) Update segment video fields
        from ..utils.segment_utils import update_segment_video_fields

        update_segment_video_fields(
            item_id=item_id,
            run=run,
            seg=seg,
            redis_client=redis_client,
            outputs_root=outputs_root,
            video_path_str=output_video_path,
            subtitles_path_str=subtitle_path,
            video_ready=True,
        )

        logger.info(f"✅ Video generation completed for segment {item_id}:{run}:{seg}")

        # If continue_chain is True, this is the end of the pipeline
        if continue_chain:
            logger.info(
                f"🎉 Pipeline completed successfully for item {item_id}, run {run}, seg {seg}"
            )

        return {
            "status": "ok",
            "item_id": item_id,
            "run": run,
            "seg": seg,
            "video_path": output_video_path,
            "subtitles_path": subtitle_path,
            "timeline_items": len(timeline),
        }

    except Exception as e:
        logger.error(
            f"❌ Video generation failed for segment {item_id}:{run}:{seg}: {e}"
        )
        raise
