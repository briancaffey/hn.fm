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

logger = logging.getLogger(__name__)


@celery_app.task(name="src.hnfm.web.tasks.hn_fetch_item")
def hn_fetch_item(item_id: int) -> Dict[str, any]:
    """Fetch and store a Hacker News item"""
    try:
        # Get Redis client
        redis_host = os.getenv("REDIS_HOST", "localhost")
        redis_port = int(os.getenv("REDIS_PORT", "6379"))
        redis_db = int(os.getenv("REDIS_DB", "0"))

        redis_client = redis.Redis(
            host=redis_host,
            port=redis_port,
            db=redis_db,
            decode_responses=False,  # Keep as bytes for JSON compatibility
        )

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


@celery_app.task(name="hnfm.web.tasks.process_hn_item_run")
def process_hn_item_run(item_id: int, run: int) -> Dict[str, any]:
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
    8) return {"status": "ok", "item_id": item_id, "run": run}
    """
    try:
        # Get Redis client
        redis_host = os.getenv("REDIS_HOST", "localhost")
        redis_port = int(os.getenv("REDIS_PORT", "6379"))
        redis_db = int(os.getenv("REDIS_DB", "0"))

        redis_client = redis.Redis(
            host=redis_host,
            port=redis_port,
            db=redis_db,
            decode_responses=False,  # Keep as bytes for JSON compatibility
        )

        # Get outputs directory
        outputs_dir = os.getenv("OUTPUTS_DIR", "/app/outputs")

        # Step 1: Get the HN item from Redis
        item_key = f"hnfm:item:{item_id}"
        item_json = redis_client.get(item_key)

        if not item_json:
            raise RuntimeError(f"Item {item_id} not found in Redis")

        # Step 2: Parse JSON and get URL
        item_data = json.loads(item_json)
        url = item_data.get('url')

        if not url:
            raise RuntimeError(f"Item {item_id} has no URL")

        # Step 3: Scrape content
        logger.info(f"Scraping content from {url}")
        content_raw = scrape_url_firecrawl(url)

        # Step 4: Clean content
        content_clean = clean_content(content_raw)

        # Step 5: Summarize content
        logger.info(f"Summarizing content for item {item_id}, run {run}")
        summary = summarize_text_v1(content_clean)

        # Step 6: Generate additional content fields
        logger.info(f"Generating short description for item {item_id}, run {run}")
        short_description = generate_short_description(summary)

        logger.info(f"Generating tags for item {item_id}, run {run}")
        tags = generate_tags(summary)

        logger.info(f"Generating emoji for item {item_id}, run {run}")
        emoji = generate_emoji(summary)

        logger.info(f"Generating haiku for item {item_id}, run {run}")
        haiku = generate_haiku(content_clean)

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
            haiku=haiku
        )

        # Step 8: Save to Redis and disk
        save_processed_run(processed_run, redis_client=redis_client, outputs_root=outputs_dir)

        logger.info(f"Successfully processed run {run} for item {item_id}")
        return {"status": "ok", "item_id": item_id, "run": run}

    except Exception as e:
        logger.error(f"Failed to process run {run} for item {item_id}: {e}")
        raise


@celery_app.task(name="src.hnfm.web.tasks.generate_segment")
def generate_segment(item_id: int, run: int, seg: int) -> Dict[str, any]:
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
    6) return {"status":"ok","item_id":item_id,"run":run,"seg":seg}
    """
    try:
        # Get Redis client
        redis_host = os.getenv("REDIS_HOST", "localhost")
        redis_port = int(os.getenv("REDIS_PORT", "6379"))
        redis_db = int(os.getenv("REDIS_DB", "0"))

        redis_client = redis.Redis(
            host=redis_host,
            port=redis_port,
            db=redis_db,
            decode_responses=False,  # Keep as bytes for JSON compatibility
        )

        # Get outputs directory
        outputs_dir = os.getenv("OUTPUTS_DIR", "/app/outputs")

        # Step 1: Load ProcessedRun from Redis
        processed_run_key = f"hnfm:item:{item_id}:run:{run}"
        processed_run_json = redis_client.get(processed_run_key)

        if not processed_run_json:
            raise RuntimeError(f"ProcessedRun {processed_run_key} not found in Redis")

        # Step 2: Parse JSON and extract content_clean and summary
        processed_run_data = json.loads(processed_run_json)
        content_clean = processed_run_data.get('content_clean', '')
        summary = processed_run_data.get('summary', '')

        if not content_clean or not summary:
            raise RuntimeError(f"ProcessedRun {processed_run_key} missing content_clean or summary")

        # Step 3: Generate script
        logger.info(f"Generating script for segment {seg} of run {run} for item {item_id}")
        script = generate_script_v1(content_clean, summary)

        # Step 4: Build Segment
        segment = Segment(
            key=k_seg(item_id, run, seg),
            item_id=item_id,
            run=run,
            seg=seg,
            created_at=datetime.utcnow(),
            processed_run_key=processed_run_key,
            script=script
        )

        # Step 5: Save segment
        save_segment(segment, redis_client=redis_client, outputs_root=outputs_dir)

        logger.info(f"Successfully generated segment {seg} for run {run} of item {item_id}")
        return {"status": "ok", "item_id": item_id, "run": run, "seg": seg}

    except Exception as e:
        logger.error(f"Failed to generate segment {seg} for run {run} of item {item_id}: {e}")
        raise


@celery_app.task(name="src.hnfm.web.tasks.build_segment_audio")
def build_segment_audio(item_id: int, run: int, seg: int, mode: str = "all", section: int = None, text_override: str = None) -> Dict[str, any]:
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
        redis_host = os.getenv("REDIS_HOST", "localhost")
        redis_port = int(os.getenv("REDIS_PORT", "6379"))
        redis_db = int(os.getenv("REDIS_DB", "0"))

        redis_client = redis.Redis(
            host=redis_host,
            port=redis_port,
            db=redis_db,
            decode_responses=False,  # Keep as bytes for JSON compatibility
        )

        # Get outputs directory
        outputs_dir = os.getenv("OUTPUTS_DIR", "/app/outputs")

        # Step 1: Load Segment (must exist)
        segment = get_segment(item_id, run, seg, redis_client=redis_client)
        if not segment:
            raise RuntimeError(f"Segment {item_id}:{run}:{seg} not found")

        if mode == "all":
            # Build all sections
            logger.info(f"Building all audio sections for segment {item_id}:{run}:{seg}")

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
                    updated_at=datetime.utcnow()
                )
                section_metas.append(meta)

            # Step 2d: Save all section metadata to Redis
            for meta in section_metas:
                # Add section to the list
                redis_client.rpush(section_key, str(meta.section))
                # Save section metadata
                save_section_meta(meta, redis_client=redis_client, outputs_root=outputs_dir)

            # Step 2e: Get all section paths in order and stitch together
            section_numbers = list_section_numbers(item_id, run, seg, redis_client=redis_client)
            paths = [sec_audio_path(outputs_dir, item_id, run, seg, s) for s in section_numbers]

            combined_path = combined_audio_path(outputs_dir, item_id, run, seg)
            total_ms = stitch_sections_to_wav(paths, combined_path)

            # Step 2f: Update segment status
            update_segment_audio_status(
                item_id, run, seg,
                sections_total=len(paths),
                combined_path=combined_path,
                ready=True,
                redis_client=redis_client,
                outputs_root=outputs_dir
            )

            logger.info(f"Successfully built {len(paths)} audio sections for segment {item_id}:{run}:{seg}")
            return {"status": "ok", "item_id": item_id, "run": run, "seg": seg, "sections": len(paths)}

        elif mode == "one":
            # Build one specific section
            if section is None:
                raise ValueError("Section number required for mode 'one'")

            logger.info(f"Building audio section {section} for segment {item_id}:{run}:{seg}")

            # Step 3a: Get text (override or existing)
            if text_override is None:
                existing_meta = get_section_meta(item_id, run, seg, section, redis_client=redis_client)
                if not existing_meta:
                    raise RuntimeError(f"Section {section} not found and no text override provided")
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
                updated_at=datetime.utcnow()
            )
            save_section_meta(meta, redis_client=redis_client, outputs_root=outputs_dir)

            # Step 3e: Re-stitch all sections
            section_numbers = list_section_numbers(item_id, run, seg, redis_client=redis_client)
            paths = [sec_audio_path(outputs_dir, item_id, run, seg, s) for s in section_numbers]
            combined_path = combined_audio_path(outputs_dir, item_id, run, seg)
            total_ms = stitch_sections_to_wav(paths, combined_path)

            # Step 3f: Update segment status
            update_segment_audio_status(
                item_id, run, seg,
                sections_total=len(paths),
                combined_path=combined_path,
                ready=True,
                redis_client=redis_client,
                outputs_root=outputs_dir
            )

            logger.info(f"Successfully built audio section {section} for segment {item_id}:{run}:{seg}")
            return {"status": "ok", "item_id": item_id, "run": run, "seg": seg, "section": section}

        else:
            raise ValueError(f"Invalid mode: {mode}. Must be 'all' or 'one'")

    except Exception as e:
        logger.error(f"Failed to build audio for segment {item_id}:{run}:{seg}: {e}")
        raise
