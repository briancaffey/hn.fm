"""Utilities for processing HN item runs."""

import os
import json
import re
import logging
from datetime import datetime
from typing import Optional, List
import redis
import requests

from ..web.models import ProcessedRun

logger = logging.getLogger(__name__)


# Redis key patterns
def get_run_key(item_id: int, run: int) -> str:
    """Get Redis key for a specific run."""
    return f"hnfm:item:{item_id}:run:{run}"


def get_run_seq_key(item_id: int) -> str:
    """Get Redis key for run sequence counter."""
    return f"hnfm:item:{item_id}:run_seq"


def get_runs_list_key(item_id: int) -> str:
    """Get Redis key for runs list."""
    return f"hnfm:item:{item_id}:runs"


# Disk path helpers
def get_run_disk_path(outputs_root: str, item_id: int, run: int) -> str:
    """Get disk path for a run's processed.json file."""
    return os.path.join(
        outputs_root, "hn", "item", str(item_id), "runs", str(run), "processed.json"
    )


def ensure_parent_dirs(file_path: str) -> None:
    """Ensure parent directories exist for a file path."""
    parent_dir = os.path.dirname(file_path)
    if parent_dir:
        os.makedirs(parent_dir, exist_ok=True)


# Utility functions
def next_run_id(item_id: int, *, redis_client: redis.Redis) -> int:
    """Get the next run ID for an item by incrementing the sequence counter."""
    key = get_run_seq_key(item_id)
    return redis_client.incr(key)


def scrape_url_firecrawl(url: str) -> str:
    """
    Use requests.post to your Firecrawl endpoint and return the raw text/markdown.
    If non-200 or empty payload, raise an exception.
    """
    try:
        # Use the existing ContentScraper logic
        from ..scraper.content_scraper import ContentScraper

        scraper = ContentScraper()
        scraped = scraper.scrape_url(url)

        if not scraped.success:
            raise RuntimeError(f"Failed to scrape {url}: {scraped.error}")

        return scraped.content

    except Exception as e:
        logger.error(f"Failed to scrape {url}: {e}")
        raise RuntimeError(f"Failed to scrape {url}: {e}")


def clean_content(text: str) -> str:
    """
    Simple deterministic cleanup:
    - Strip leading/trailing whitespace
    - Collapse consecutive whitespace/newlines
    Return cleaned string.
    """
    if not text:
        return ""

    # Strip leading/trailing whitespace
    text = text.strip()

    # Collapse consecutive whitespace/newlines
    text = re.sub(r"\s+", " ", text)  # Replace multiple whitespace with single space
    text = re.sub(r"\n\s*\n", "\n\n", text)  # Preserve paragraph breaks

    return text


def summarize_text_v1(text: str) -> str:
    """
    Use requests.post to your LLM summary endpoint.
    Prompt: 'Summarize the article in 5-7 sentences. Be specific and factual.'
    Return the summary string.
    If non-200 or empty, raise an exception.
    """
    try:
        # Use the existing LLMService
        from ..content.llm_service import LLMService

        llm_service = LLMService()
        prompt = (
            "Summarize the article in 5-7 sentences. Be specific and factual.\n\nArticle:\n"
            + text
        )

        summary = llm_service.generate_content(prompt)

        if not summary:
            raise RuntimeError("LLM service returned empty summary")

        return summary.strip()

    except Exception as e:
        logger.error(f"Failed to summarize text: {e}")
        raise RuntimeError(f"Failed to summarize text: {e}")


def save_processed_run(
    pr: ProcessedRun, *, redis_client: redis.Redis, outputs_root: str
) -> None:
    """
    - SET hnfm:item:{item_id}:run:{run} with JSON(pr)
    - LPUSH hnfm:item:{item_id}:runs the run number
    - Write to outputs/hn/item/{item_id}/runs/{run}/processed.json
    """
    try:
        # Serialize to JSON
        pr_json = pr.model_dump_json()

        # Save to Redis
        run_key = get_run_key(pr.item_id, pr.run)
        redis_client.set(run_key, pr_json)

        # Add to runs list (newest first)
        runs_list_key = get_runs_list_key(pr.item_id)
        redis_client.lpush(runs_list_key, str(pr.run))

        # Save to disk
        disk_path = get_run_disk_path(outputs_root, pr.item_id, pr.run)
        ensure_parent_dirs(disk_path)

        with open(disk_path, "w", encoding="utf-8") as f:
            f.write(pr_json)

        logger.info(f"Saved run {pr.run} for item {pr.item_id} to Redis and disk")

    except Exception as e:
        logger.error(f"Failed to save processed run: {e}")
        raise


def list_runs_for_item(
    item_id: int, *, redis_client: redis.Redis, offset: int = 0, limit: int = 20
) -> List[int]:
    """
    Use LRANGE on hnfm:item:{item_id}:runs (it's newest-first because we LPUSH).
    Slice with offset/limit and return a list of run ints.
    """
    try:
        runs_list_key = get_runs_list_key(item_id)

        # Get all runs (newest first due to LPUSH)
        all_runs = redis_client.lrange(runs_list_key, 0, -1)

        # Convert to integers and apply pagination
        # Handle both bytes and string responses (fakeredis vs real redis)
        run_ints = []
        for run in all_runs:
            if isinstance(run, bytes):
                run_ints.append(int(run.decode()))
            else:
                run_ints.append(int(run))

        # Apply offset and limit
        start = offset
        end = offset + limit
        return run_ints[start:end]

    except Exception as e:
        logger.error(f"Failed to list runs for item {item_id}: {e}")
        return []


def get_run(
    item_id: int, run: int, *, redis_client: redis.Redis
) -> Optional[ProcessedRun]:
    """
    GET hnfm:item:{item_id}:run:{run} and parse to ProcessedRun. Return None if missing.
    """
    try:
        run_key = get_run_key(item_id, run)
        run_json = redis_client.get(run_key)

        if not run_json:
            return None

        # Parse JSON and create ProcessedRun
        run_data = json.loads(run_json)
        return ProcessedRun(**run_data)

    except Exception as e:
        logger.error(f"Failed to get run {run} for item {item_id}: {e}")
        return None


def delete_run(
    item_id: int, run: int, *, redis_client: redis.Redis, outputs_root: str
) -> bool:
    """Delete a run completely - removes Redis keys and disk files.

    Args:
        item_id: Hacker News item ID
        run: Run number to delete
        redis_client: Redis client instance
        outputs_root: Root directory for outputs

    Returns:
        bool: True if deletion was successful, False otherwise
    """
    try:
        # Get run data first to verify it exists
        run_data = get_run(item_id, run, redis_client=redis_client)
        if not run_data:
            logger.warning(f"Run {run} for item {item_id} not found, nothing to delete")
            return False

        # Delete Redis keys
        run_key = get_run_key(item_id, run)
        runs_list_key = get_runs_list_key(item_id)

        # Remove from Redis
        redis_client.delete(run_key)
        redis_client.lrem(runs_list_key, 0, str(run).encode())

        # Delete disk files and folder
        run_disk_path = get_run_disk_path(outputs_root, item_id, run)
        run_folder = os.path.dirname(run_disk_path)

        if os.path.exists(run_folder):
            import shutil

            shutil.rmtree(run_folder)
            logger.info(f"Deleted run folder: {run_folder}")

        logger.info(f"Successfully deleted run {run} for item {item_id}")
        return True

    except Exception as e:
        logger.error(f"Failed to delete run {run} for item {item_id}: {e}")
        return False
