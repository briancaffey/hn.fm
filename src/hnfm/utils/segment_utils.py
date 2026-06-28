"""Utilities for managing script segments"""

import json
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional, List
import redis

from ..web.models import Segment


def k_seg(item_id: int, run: int, seg: int) -> str:
    """Generate Redis key for a segment"""
    return f"hnfm:seg:{item_id}:{run}:{seg}"


def k_seg_seq(item_id: int, run: int) -> str:
    """Generate Redis key for segment sequence counter"""
    return f"hnfm:seg:seq:{item_id}:{run}"


def k_seg_list(item_id: int, run: int) -> str:
    """Generate Redis key for segment list (newest-first)"""
    return f"hnfm:seg:list:{item_id}:{run}"


def k_img(item_id: int, run: int, seg: int, index: int) -> str:
    """Generate Redis key for a segment image"""
    return f"hnfm:seg:{item_id}:{run}:{seg}:img:{index}"


def k_img_list(item_id: int, run: int, seg: int) -> str:
    """Generate Redis key for segment image list (ordered)"""
    return f"hnfm:seg:{item_id}:{run}:{seg}:img:list"


def seg_dir(outputs_root: str, item_id: int, run: int, seg: int) -> str:
    """Generate disk directory path for a segment"""
    return f"{outputs_root}/hn/item/{item_id}/runs/{run}/segments/{seg}"


def asr_json_path(outputs_root: str, item_id: int, run: int, seg: int) -> str:
    """Generate path for ASR JSON file"""
    return f"{outputs_root}/hn/item/{item_id}/runs/{run}/segments/{seg}/audio/asr.json"


def seg_root(outputs_root: str, item_id: int, run: int, seg: int) -> str:
    """Generate root directory path for a segment (same as seg_dir)"""
    return seg_dir(outputs_root, item_id, run, seg)


def img_dir(outputs_root: str, item_id: int, run: int, seg: int, index: int) -> str:
    """Generate directory path for a segment image"""
    return f"{outputs_root}/hn/item/{item_id}/runs/{run}/segments/{seg}/images/{index}"


def img_path(outputs_root: str, item_id: int, run: int, seg: int, index: int) -> str:
    """Generate path for segment image file"""
    return f"{img_dir(outputs_root, item_id, run, seg, index)}/image.png"


def img_meta_path(
    outputs_root: str, item_id: int, run: int, seg: int, index: int
) -> str:
    """Generate path for segment image metadata file"""
    return f"{img_dir(outputs_root, item_id, run, seg, index)}/meta.json"


def video_dir(outputs_root: str, item_id: int, run: int, seg: int) -> str:
    """Generate directory path for segment video files"""
    return f"{outputs_root}/hn/item/{item_id}/runs/{run}/segments/{seg}/video"


def video_path(outputs_root: str, item_id: int, run: int, seg: int) -> str:
    """Generate path for segment video file"""
    return f"{video_dir(outputs_root, item_id, run, seg)}/segment.mp4"


def subtitles_path(outputs_root: str, item_id: int, run: int, seg: int) -> str:
    """Generate path for segment subtitles VTT file"""
    return f"{video_dir(outputs_root, item_id, run, seg)}/captions.vtt"


def timeline_path(outputs_root: str, item_id: int, run: int, seg: int) -> str:
    """Generate path for segment timeline debug JSON file"""
    return f"{video_dir(outputs_root, item_id, run, seg)}/timeline.json"


def write_json(path: str, data: dict) -> None:
    """Write JSON data to file with proper directory creation"""
    path_obj = Path(path)
    path_obj.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def _clean_script_for_tts(script: str) -> str:
    """
    Clean script text for better TTS results.

    Args:
        script: Raw script text from LLM

    Returns:
        Cleaned script text with TTS-friendly characters
    """
    replacements = {
        ord("“"): '"',
        ord("”"): '"',
        ord("‘"): "'",
        ord("’"): "'",
        ord("—"): ", ",
        ord("–"): ", ",
        # ord('\n\n'): '\n',
        ord("…"): ", ",
        ord("`"): "",
        ord("_"): " ",
    }

    script = script.replace("\n\n", "\n")

    script = script.translate(replacements)

    return script


def next_seg_id(item_id: int, run: int, *, redis_client: redis.Redis) -> int:
    """Get next segment ID atomically"""
    return int(redis_client.incr(k_seg_seq(item_id, run)))


def generate_script_v1(content_clean: str, summary: str) -> str:
    """
    Generate script using LLM service with detailed formatting instructions.

    Args:
        content_clean: Cleaned article content
        summary: Article summary

    Returns:
        Generated script text with [S1] and [S2] speaker tags

    Raises:
        RuntimeError: If script generation fails
    """
    try:
        from ..content.llm_service import LLMService
        from ..utils.config import config_manager

        # Get LLM configuration
        llm_config = config_manager.get("llm", {})

        # Initialize LLM service
        if llm_config.get("enabled", False):
            base_url = llm_config.get("base_url")
            model = llm_config.get("model", "gpt-oss")
            llm_service = LLMService(base_url=base_url, model=model)
        else:
            llm_service = LLMService()

        # Create detailed prompt with specific formatting requirements
        script_prompt = f"""
        Create a natural, engaging podcast script from this article.

        Article Summary: {summary}

        Content:
        {content_clean}

        Requirements:
        - Use [S1] and [S2] speaker tags for dialogue (NOT **S1:** format)
        - Make it conversational and engaging
        - Break into natural speaking segments (2-3 sentences max per line)
        - Maintain the key insights and information
        - Keep total length reasonable for a podcast segment (3-5 minutes)
        - Use straight quotes (") and apostrophes (') instead of curly quotes (") and apostrophes (')
        - Avoid special characters that might cause TTS issues
        - Each line should start with [S1] or [S2] followed by the dialogue

        Format the output as a script with [S1] and [S2] tags, one per line.
        Example:
        [S1] Hey there, welcome to the podcast!
        [S2] Today we're talking about an interesting topic.
        [S1] Let's dive right in.
        """

        script = llm_service.generate_content(script_prompt)

        if not script:
            raise RuntimeError("LLM returned empty script")

        # Clean the script for better TTS results
        script = _clean_script_for_tts(script)

        return script

    except Exception as e:
        raise RuntimeError(f"Failed to generate script: {e}")


def save_segment(
    seg_obj: Segment, *, redis_client: redis.Redis, outputs_root: str
) -> None:
    """
    Save segment to Redis and disk.

    Args:
        seg_obj: Segment object to save
        redis_client: Redis client
        outputs_root: Root outputs directory
    """
    # Save to Redis
    redis_client.set(
        k_seg(seg_obj.item_id, seg_obj.run, seg_obj.seg), seg_obj.model_dump_json()
    )

    # Add to segment list (newest-first) only if not already present
    list_key = k_seg_list(seg_obj.item_id, seg_obj.run)
    seg_id_str = str(seg_obj.seg)

    # Check if segment ID is already in the list
    existing_segments = redis_client.lrange(list_key, 0, -1)
    if seg_id_str not in [
        seg.decode() if isinstance(seg, bytes) else seg for seg in existing_segments
    ]:
        redis_client.lpush(list_key, seg_id_str)

    # Save to disk
    seg_path = seg_dir(outputs_root, seg_obj.item_id, seg_obj.run, seg_obj.seg)
    Path(seg_path).mkdir(parents=True, exist_ok=True)

    segment_file = os.path.join(seg_path, "segment.json")
    with open(segment_file, "w", encoding="utf-8") as f:
        f.write(seg_obj.model_dump_json())


def get_segment(
    item_id: int, run: int, seg: int, *, redis_client: redis.Redis
) -> Optional[Segment]:
    """
    Get segment from Redis.

    Args:
        item_id: Item ID
        run: Run number
        seg: Segment number
        redis_client: Redis client

    Returns:
        Segment object or None if not found
    """
    key = k_seg(item_id, run, seg)
    data = redis_client.get(key)

    if not data:
        return None

    try:
        return Segment.model_validate_json(data)
    except Exception:
        return None


def list_segments_for_run(
    item_id: int,
    run: int,
    *,
    redis_client: redis.Redis,
    offset: int = 0,
    limit: int = 20,
) -> List[int]:
    """
    List segment IDs for a run (newest-first).

    Args:
        item_id: Item ID
        run: Run number
        redis_client: Redis client
        offset: Pagination offset
        limit: Pagination limit

    Returns:
        List of segment IDs
    """
    key = k_seg_list(item_id, run)
    segment_ids = redis_client.lrange(key, offset, offset + limit - 1)

    return [int(seg_id) for seg_id in segment_ids]


def list_all_segments(
    *,
    redis_client: redis.Redis,
    offset: int = 0,
    limit: int = 50,
) -> List[Segment]:
    """
    List all segments across all items and runs (newest-first).

    Args:
        redis_client: Redis client
        offset: Pagination offset
        limit: Pagination limit

    Returns:
        List of Segment objects
    """
    # Get all segment keys from Redis
    pattern = "hnfm:seg:*"
    segment_keys = redis_client.keys(pattern)

    # Filter out non-segment keys (like lists, sequences, etc.)
    # Convert bytes to string for filtering
    filtered_keys = []
    for key in segment_keys:
        key_str = key.decode("utf-8") if isinstance(key, bytes) else key
        if not any(suffix in key_str for suffix in [":list", ":seq", ":img:", ":sec:"]):
            filtered_keys.append(key)

    # Sort by creation time (newest first) by checking the segment data
    segments_with_time = []
    for key in filtered_keys:
        try:
            data = redis_client.get(key)
            if data:
                # Decode data if it's bytes
                if isinstance(data, bytes):
                    data = data.decode("utf-8")
                segment = Segment.model_validate_json(data)
                segments_with_time.append((segment.created_at, segment))
        except Exception:
            continue

    # Sort by creation time (newest first)
    segments_with_time.sort(key=lambda x: x[0], reverse=True)

    # Apply pagination
    paginated_segments = segments_with_time[offset : offset + limit]

    return [segment for _, segment in paginated_segments]


def delete_segment(
    item_id: int, run: int, seg: int, *, redis_client: redis.Redis, outputs_root: str
) -> bool:
    """
    Delete segment from Redis and disk.

    Args:
        item_id: Item ID
        run: Run number
        seg: Segment number
        redis_client: Redis client
        outputs_root: Root outputs directory

    Returns:
        True if segment was deleted, False if not found
    """
    key = k_seg(item_id, run, seg)

    # Check if segment exists
    if not redis_client.exists(key):
        return False

    # Delete from Redis
    redis_client.delete(key)

    # Remove from segment list
    list_key = k_seg_list(item_id, run)
    redis_client.lrem(list_key, 0, str(seg))  # Remove all occurrences

    # Delete from disk
    seg_path = seg_dir(outputs_root, item_id, run, seg)
    if os.path.exists(seg_path):
        shutil.rmtree(seg_path)

    return True


def alignment_from_sections(
    item_id: int, run: int, seg: int, *, redis_client: redis.Redis
) -> Optional[List[tuple[int, int]]]:
    """
    If narration sections exist: compute [(start_ms, duration_ms), ...] in index order.
    start_ms is cumulative sum of previous durations.
    Return None if sections missing.
    """
    try:
        from ..audio.audio_utils import k_sec_list

        # Get all section keys for this segment
        list_key = k_sec_list(item_id, run, seg)
        section_keys = redis_client.lrange(list_key, 0, -1)

        if not section_keys:
            return None

        alignments = []
        cumulative_start = 0

        for section_key in section_keys:
            section_data = redis_client.get(section_key)
            if not section_data:
                continue

            try:
                from ..web.models import SegmentSection

                section = SegmentSection.model_validate_json(section_data)

                if section.duration_ms is not None:
                    alignments.append((cumulative_start, section.duration_ms))
                    cumulative_start += section.duration_ms
                else:
                    # If duration is missing, skip this section
                    continue

            except Exception:
                continue

        return alignments if alignments else None

    except Exception:
        return None


def generate_image_prompt_v1(line_text: str, run_summary: str, theme=None, shot_hint: str = "") -> str:
    """Write a vivid SCENE for one line, then apply the take's visual THEME.

    The LLM invents the scene (subject/action/composition/shot) but does NOT pick
    an art style — the theme's style block is appended deterministically so every
    shot in a take is stylistically cohesive while scenes stay varied. `theme` is
    an `art_direction.Theme` (or None for a neutral look). Returns a plain string.
    """
    try:
        from ..content.llm_service import LLMService
        from ..content.art_direction import compose_prompt
        from ..utils.config import config_manager

        llm_config = config_manager.get("llm", {})
        if llm_config.get("enabled", False):
            llm_service = LLMService(
                base_url=llm_config.get("base_url"),
                model=llm_config.get("model", "gpt-oss"),
            )
        else:
            llm_service = LLMService()

        system_prompt = (
            "You are a cinematic art director writing ONE image prompt to illustrate a "
            "line of a tech podcast. Invent a striking, SPECIFIC scene: a clear subject "
            "doing something, a concrete setting, evocative props, and a deliberate shot "
            "(vary it — wide establishing, macro detail, overhead, dramatic portrait, "
            "over-the-shoulder, conceptual metaphor). Be visually surprising and avoid "
            "clichés (no generic 'person looking at a laptop/phone' unless truly apt). "
            "Describe ONLY the scene and composition — do NOT mention art style, medium, "
            "or rendering (that is added separately). 1-2 sentences, no preamble, no quotes."
        )
        user_prompt = (
            f"Episode context:\n{run_summary}\n\n"
            f"Line to illustrate:\n{line_text}\n\n"
            f"{('Shot direction: ' + shot_hint + chr(10)) if shot_hint else ''}"
            f"Write the scene now."
        )

        response = llm_service.generate_content(f"{system_prompt}\n\n{user_prompt}")
        if not response:
            raise RuntimeError("LLM returned empty response")

        scene = response.strip()
        if scene.startswith('"') and scene.endswith('"'):
            scene = scene[1:-1]

        return compose_prompt(scene, theme)

    except Exception as e:
        raise RuntimeError(f"Failed to generate image prompt: {e}")


def generate_image_from_prompt(prompt: str, out_path: str, width=None, height=None) -> None:
    """
    Use video/image scripts you have (image_generator.py) or service.
    Must write a PNG to out_path. Overwrite if exists.
    """
    try:
        from ..image.image_service_factory import ImageServiceFactory

        # Create output directory if it doesn't exist
        Path(out_path).parent.mkdir(parents=True, exist_ok=True)

        # Generate and save image using the configured service
        service = ImageServiceFactory.create_image_service()
        kwargs = {}
        if width:
            kwargs["width"] = width
        if height:
            kwargs["height"] = height
        service.generate_and_save_image(prompt, out_path, "image.png", **kwargs)

    except Exception as e:
        raise RuntimeError(f"Failed to generate image: {e}")


def save_segment_image(
    si: "SegmentImage", *, redis_client: redis.Redis, outputs_root: str
) -> None:
    """Save segment image to Redis and disk"""
    from ..web.models import SegmentImage

    # Save to Redis
    redis_client.set(si.key, si.model_dump_json())

    # Add to image list if not already present
    list_key = k_img_list(si.item_id, si.run, si.seg)
    if not redis_client.lrange(list_key, 0, -1) or str(si.index) not in [
        x.decode() if isinstance(x, bytes) else x
        for x in redis_client.lrange(list_key, 0, -1)
    ]:
        redis_client.rpush(list_key, str(si.index))

    # Write meta.json
    meta_path = img_meta_path(outputs_root, si.item_id, si.run, si.seg, si.index)
    # Use model_dump_json() to handle datetime serialization properly
    with open(meta_path, "w", encoding="utf-8") as f:
        f.write(si.model_dump_json())


def get_segment_image(
    item_id: int, run: int, seg: int, index: int, *, redis_client: redis.Redis
) -> Optional["SegmentImage"]:
    """Get segment image from Redis"""
    from ..web.models import SegmentImage

    key = k_img(item_id, run, seg, index)
    data = redis_client.get(key)

    if not data:
        return None

    try:
        return SegmentImage.model_validate_json(data)
    except Exception:
        return None


def list_segment_images(
    item_id: int, run: int, seg: int, *, redis_client: redis.Redis
) -> List[int]:
    """List segment image indexes in order"""
    list_key = k_img_list(item_id, run, seg)
    indexes = redis_client.lrange(list_key, 0, -1)
    return [int(idx) for idx in indexes]


def update_segment_images_status(
    item_id: int,
    run: int,
    seg: int,
    total: int,
    ready: bool,
    *,
    redis_client: redis.Redis,
    outputs_root: str,
) -> None:
    """Update segment image status"""
    # Load Segment
    segment = get_segment(item_id, run, seg, redis_client=redis_client)
    if not segment:
        raise RuntimeError(f"Segment not found: {item_id}:{run}:{seg}")

    # Update image fields
    segment.images_total = total
    segment.images_ready = ready

    # Re-save to Redis and disk
    save_segment(segment, redis_client=redis_client, outputs_root=outputs_root)


def list_section_numbers(
    item_id: int, run: int, seg: int, *, redis_client: redis.Redis
) -> List[int]:
    """Get ordered section indices for a segment"""
    from ..audio.audio_utils import k_sec_list

    list_key = k_sec_list(item_id, run, seg)
    section_strings = redis_client.lrange(list_key, 0, -1)
    return [int(section_str) for section_str in section_strings]


def load_section_and_image(
    item_id: int, run: int, seg: int, index: int, *, redis_client: redis.Redis
) -> dict:
    """
    Load section and image data for a specific index.

    Returns:
        {
            "index": index,
            "duration_ms": int,             # from SegmentSection.duration_ms (REQUIRED)
            "image_path": str,              # from SegmentImage.image_path (REQUIRED)
            "text": str                     # from SegmentImage.line_text (for subtitles)
        }
    Raises if any required field is missing or empty.
    """
    from ..audio.audio_utils import get_section_meta

    # Load section data
    section = get_section_meta(item_id, run, seg, index, redis_client=redis_client)
    if not section or section.duration_ms is None:
        raise RuntimeError(f"Section {index} missing or duration_ms is None")

    # Load image data
    image = get_segment_image(item_id, run, seg, index, redis_client=redis_client)
    if not image or not image.image_path:
        raise RuntimeError(f"Image {index} missing or image_path is None")

    return {
        "index": index,
        "duration_ms": section.duration_ms,
        "image_path": image.image_path,
        "text": image.line_text,
    }


def build_timeline(
    item_id: int, run: int, seg: int, *, redis_client: redis.Redis
) -> List[dict]:
    """
    Build timeline for video generation from sections and images.
    Includes intro, title page, main content, and outro.

    Returns:
        List of dicts with:
        {
            "index": int,
            "image_path": str,
            "start_ms": int,
            "duration_ms": int,
            "text": str,
            "type": str  # "intro", "title", "content", "outro"
        }
    """
    from ..utils.run_utils import get_run
    from pathlib import Path

    # Get run data for title and emojis
    run_data = get_run(item_id, run, redis_client=redis_client)
    if not run_data:
        raise RuntimeError(f"Run data not found for item {item_id}, run {run}")

    timeline = []
    cumulative_start = 0

    # Add intro sequence (4 seconds)
    intro_audio_path = Path(__file__).parent.parent / "video" / "media" / "intro.wav"
    intro_image_path = (
        Path(__file__).parent.parent / "video" / "media" / "hnfm_square.png"
    )

    if intro_audio_path.exists() and intro_image_path.exists():
        timeline.append(
            {
                "index": -3,  # Special index for intro
                "image_path": str(intro_image_path),
                "start_ms": cumulative_start,
                "duration_ms": 4000,  # 4 seconds
                "text": "Intro",
                "type": "intro",
            }
        )
        cumulative_start += 4000

    # Add main content from sections and images
    section_numbers = list_section_numbers(item_id, run, seg, redis_client=redis_client)

    for index in section_numbers:
        data = load_section_and_image(
            item_id, run, seg, index, redis_client=redis_client
        )

        total = int(data["duration_ms"] or 0)
        # Expand an image sequence (root + edits) across this section's slot so
        # the visuals change in quick cadence. Falls back to a single image.
        si = get_segment_image(item_id, run, seg, index, redis_client=redis_client)
        frames = [
            p for p in (getattr(si, "sequence_paths", None) or []) if p
        ] or [data["image_path"]]
        n = max(1, len(frames))
        per = max(500, total // n) if total else 0

        for k, fp in enumerate(frames):
            d = (total - per * (n - 1)) if k == n - 1 else per
            if d <= 0:
                d = per or total
            timeline.append(
                {
                    "index": data["index"],
                    "image_path": fp,
                    "start_ms": cumulative_start,
                    "duration_ms": d,
                    "text": data["text"],
                    "type": "content",
                }
            )
            cumulative_start += d

    # Add outro sequence (4 seconds)
    outro_image_path = (
        Path(__file__).parent.parent / "video" / "media" / "hnfm_square.png"
    )

    if outro_image_path.exists():
        timeline.append(
            {
                "index": -1,  # Special index for outro
                "image_path": str(outro_image_path),
                "start_ms": cumulative_start,
                "duration_ms": 4000,  # 4 seconds
                "text": "Outro",
                "type": "outro",
            }
        )

    return timeline


def write_vtt_from_timeline(timeline: List[dict], out_path: str) -> None:
    """
    Create WebVTT subtitles from timeline data.

    Args:
        timeline: List of dicts with start_ms, duration_ms, text
        out_path: Output VTT file path
    """
    from pathlib import Path

    # Ensure output directory exists
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)

    with open(out_path, "w", encoding="utf-8") as f:
        f.write("WEBVTT\n\n")

        for item in timeline:
            start_ms = item["start_ms"]
            duration_ms = item["duration_ms"]
            end_ms = start_ms + duration_ms
            text = item["text"]

            # Convert to VTT time format (HH:MM:SS.mmm)
            start_time = _ms_to_vtt_time(start_ms)
            end_time = _ms_to_vtt_time(end_ms)

            f.write(f"{start_time} --> {end_time}\n")
            f.write(f"{text}\n\n")


def write_ass_from_asr(asr_data: dict, out_path: str, width: int = 1280, height: int = 720) -> None:
    """Animated karaoke captions (ASS) from ASR word timings, via pysubs2.

    Each caption line highlights word-by-word as it is spoken (smooth ``\\kf``
    fill synced to the actual word times). Times are offset by the 4s intro.
    Falls back to a flat single line if only flat words are present.
    """
    import pysubs2
    from pathlib import Path

    INTRO_OFFSET = 4.0
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)

    segments = asr_data.get("segments") or []
    if not segments and asr_data.get("words"):
        segments = [{"words": asr_data["words"]}]

    subs = pysubs2.SSAFile()
    subs.info["Title"] = "hn.fm captions"
    subs.info["PlayResX"] = str(width)
    subs.info["PlayResY"] = str(height)
    subs.info["ScaledBorderAndShadow"] = "yes"

    style = pysubs2.SSAStyle()
    style.fontname = "DejaVu Sans"
    style.fontsize = 44
    style.bold = True
    style.primarycolor = pysubs2.Color(80, 230, 255)      # active word = cyan
    style.secondarycolor = pysubs2.Color(255, 255, 255)   # upcoming = white
    style.outlinecolor = pysubs2.Color(0, 0, 0)
    style.backcolor = pysubs2.Color(0, 0, 0, 160)
    style.outline = 3.5
    style.shadow = 1.5
    style.alignment = pysubs2.Alignment.BOTTOM_CENTER
    style.marginl = 80
    style.marginr = 80
    style.marginv = 60
    subs.styles["Caption"] = style

    for seg in segments:
        words = [w for w in (seg.get("words") or []) if (w.get("word") or "").strip()]
        if not words:
            continue
        seg_start = float(words[0].get("start", 0)) + INTRO_OFFSET
        seg_end = float(words[-1].get("end", 0)) + INTRO_OFFSET
        if seg_end <= seg_start:
            seg_end = seg_start + 0.6

        parts = []
        for i, w in enumerate(words):
            w_start = float(w.get("start", 0))
            nxt = float(words[i + 1].get("start", 0)) if i + 1 < len(words) else float(w.get("end", w_start))
            dur_cs = max(1, round((nxt - w_start) * 100))
            token = (w.get("word") or "").strip().replace("{", "(").replace("}", ")")
            parts.append("{\\kf%d}%s " % (dur_cs, token))

        text = "{\\fad(120,80)}" + "".join(parts).strip()
        subs.append(
            pysubs2.SSAEvent(
                start=int(seg_start * 1000),
                end=int(seg_end * 1000),
                style="Caption",
                text=text,
            )
        )

    subs.save(out_path)


def _seconds_to_ass_time(seconds: float) -> str:
    """Convert seconds to ASS time format (H:MM:SS.cc)."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    centiseconds = int((seconds % 1) * 100)

    return f"{hours}:{minutes:02d}:{secs:02d}.{centiseconds:02d}"


def _ms_to_vtt_time(ms: int) -> str:
    """Convert milliseconds to VTT time format (HH:MM:SS.mmm)"""
    seconds = ms // 1000
    milliseconds = ms % 1000
    minutes = seconds // 60
    seconds = seconds % 60
    hours = minutes // 60
    minutes = minutes % 60

    return f"{hours:02d}:{minutes:02d}:{seconds:02d}.{milliseconds:03d}"


def update_segment_video_fields(
    item_id: int,
    run: int,
    seg: int,
    *,
    redis_client: redis.Redis,
    outputs_root: str,
    video_path_str: str | None,
    subtitles_path_str: str | None,
    video_ready: bool,
) -> None:
    """
    Update segment video fields in Redis and on disk.

    Args:
        item_id: Item ID
        run: Run number
        seg: Segment number
        redis_client: Redis client
        outputs_root: Root outputs directory
        video_path_str: Path to video file (optional)
        subtitles_path_str: Path to subtitles file (optional)
        video_ready: Whether video is ready
    """
    # Load existing segment
    segment = get_segment(item_id, run, seg, redis_client=redis_client)
    if not segment:
        raise RuntimeError(f"Segment not found: {item_id}:{run}:{seg}")

    # Update video fields
    segment.video_path = video_path_str
    segment.subtitles_path = subtitles_path_str
    segment.video_ready = video_ready

    # Re-save to Redis and disk
    save_segment(segment, redis_client=redis_client, outputs_root=outputs_root)
