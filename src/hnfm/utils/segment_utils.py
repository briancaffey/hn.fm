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


def seg_dir(outputs_root: str, item_id: int, run: int, seg: int) -> str:
    """Generate disk directory path for a segment"""
    return f"{outputs_root}/hn/item/{item_id}/runs/{run}/segments/{seg}"


def asr_json_path(outputs_root: str, item_id: int, run: int, seg: int) -> str:
    """Generate path for ASR JSON file"""
    return f"{outputs_root}/hn/item/{item_id}/runs/{run}/segments/{seg}/audio/asr.json"


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

    # Add to segment list (newest-first)
    redis_client.lpush(k_seg_list(seg_obj.item_id, seg_obj.run), str(seg_obj.seg))

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
