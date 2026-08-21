"""Utilities for processing HN item runs."""

import os
import re
import logging
from typing import Optional, List

from ..db import repo
from ..web.models import ProcessedRun

logger = logging.getLogger(__name__)


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
def next_run_id(item_id: int) -> int:
    """Get the next run ID for an item by incrementing the sequence counter."""
    return repo.next_counter(f"run:{item_id}")


def scrape_url_firecrawl(url: str) -> str:
    """
    Use requests.post to your Firecrawl endpoint and return the raw text/markdown.
    If non-200 or empty payload, raise an exception.
    """
    return scrape_url_with_source(url)[0]


def scrape_url_with_source(url: str) -> tuple:
    """`(content, source)` where source is "firecrawl" or "wayback".

    Which path answered is a `producibility` input (plans/09) — an archived
    copy is materially different material from a live fetch — so the caller
    needs it, not just the text.
    """
    try:
        # Use the existing ContentScraper logic
        from ..scraper.content_scraper import ContentScraper

        scraper = ContentScraper()
        scraped = scraper.scrape_url(url)

        if not scraped.success:
            raise RuntimeError(f"Failed to scrape {url}: {scraped.error}")

        return scraped.content, getattr(scraped, "source", "firecrawl")

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
        from ..content.llm_service import LLMService
        from ..content.prompts import render

        prompt = render("summary.write", text=text)
        summary = LLMService(task="summary").generate_content(prompt)

        if not summary:
            raise RuntimeError("LLM service returned empty summary")

        return summary.strip()

    except Exception as e:
        logger.error(f"Failed to summarize text: {e}")
        raise RuntimeError(f"Failed to summarize text: {e}")


def save_processed_run(pr: ProcessedRun, *, outputs_root: str) -> None:
    """Save the run to Postgres and mirror it to
    outputs/hn/item/{item_id}/runs/{run}/processed.json"""
    try:
        # Save to Postgres
        repo.save_run(pr)

        # Save to disk
        disk_path = get_run_disk_path(outputs_root, pr.item_id, pr.run)
        ensure_parent_dirs(disk_path)

        with open(disk_path, "w", encoding="utf-8") as f:
            f.write(pr.model_dump_json())

        logger.info(f"Saved run {pr.run} for item {pr.item_id} to Postgres and disk")

    except Exception as e:
        logger.error(f"Failed to save processed run: {e}")
        raise


def list_runs_for_item(item_id: int, *, offset: int = 0, limit: int = 20) -> List[int]:
    """Run numbers for an item, newest-first, paginated."""
    try:
        return repo.list_run_numbers(item_id, offset=offset, limit=limit)
    except Exception as e:
        logger.error(f"Failed to list runs for item {item_id}: {e}")
        return []


def get_run(item_id: int, run: int) -> Optional[ProcessedRun]:
    """Load a ProcessedRun. Return None if missing."""
    try:
        return repo.get_run(item_id, run)
    except Exception as e:
        logger.error(f"Failed to get run {run} for item {item_id}: {e}")
        return None


def delete_run(item_id: int, run: int, *, outputs_root: str) -> bool:
    """Delete a run completely — the DB row (segments/sections/images cascade)
    and the run's disk folder.

    Returns:
        bool: True if deletion was successful, False otherwise
    """
    try:
        deleted = repo.delete_run_row(item_id, run)
        if not deleted:
            logger.warning(f"Run {run} for item {item_id} not found, nothing to delete")
            return False

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
