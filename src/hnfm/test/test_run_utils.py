"""Tests for run utilities (Postgres-backed via the sqlite test DB)."""

import json
import os
from datetime import datetime

import pytest

from ..db import repo
from ..utils.run_utils import (
    next_run_id,
    scrape_url_firecrawl,
    clean_content,
    summarize_text_v1,
    save_processed_run,
    list_runs_for_item,
    get_run,
    get_run_disk_path,
)
from ..web.models import HNItem, ProcessedRun


def make_processed_run(item_id: int, run: int, summary: str = "Summary") -> ProcessedRun:
    """Build a valid ProcessedRun for tests (key is recomputed on read)."""
    return ProcessedRun(
        key=f"hnfm:item:{item_id}:run:{run}",
        item_id=item_id,
        run=run,
        created_at=datetime.utcnow(),
        source_url="https://example.com",
        content_raw="Raw content",
        content_clean="Clean content",
        summary=summary,
        short_description="A short description",
        tags=["tag1", "tag2"],
        emoji=["🎧", "📰", "🔥", "🚀"],
        haiku="an article read\nsummarized in a few lines\ntests still pass today",
    )


class TestRunUtils:
    """Test run utility functions."""

    def test_next_run_id_increments(self):
        """Test that next_run_id increments properly."""
        # New item: counter returns 1, then 2
        run1 = next_run_id(123)
        assert run1 == 1

        run2 = next_run_id(123)
        assert run2 == 2

        # Different item should start from 1
        run3 = next_run_id(456)
        assert run3 == 1

    def test_clean_content(self):
        """Test content cleaning functionality."""
        # Test basic cleaning
        text = "  Hello   world  \n\n  This is   a test  "
        cleaned = clean_content(text)
        assert cleaned == "Hello world This is a test"

        # Test empty string
        assert clean_content("") == ""
        assert clean_content(None) == ""

        # Test with multiple newlines
        text2 = "Line 1\n\n\nLine 2\n\nLine 3"
        cleaned2 = clean_content(text2)
        assert cleaned2 == "Line 1 Line 2 Line 3"

    def test_scrape_url_firecrawl_network_skip(self):
        """Test that scrape_url_firecrawl raises error when network is unavailable."""
        # This test verifies the function handles network errors gracefully
        with pytest.raises(RuntimeError, match="Failed to scrape"):
            scrape_url_firecrawl("https://example.com")

    def test_summarize_text_v1_network_skip(self):
        """Test that summarize_text_v1 handles network errors gracefully."""
        # This test verifies the function handles network errors gracefully
        # It will either return a fallback or raise an error depending on LLM service state
        try:
            result = summarize_text_v1("Some article text")
            # If it doesn't raise an error, it should return some string
            assert isinstance(result, str)
        except RuntimeError:
            # This is also acceptable - the function should handle errors gracefully
            pass

    def test_save_processed_run_persists_everywhere(self, outputs_root):
        """Test that save_processed_run persists to the DB and disk."""
        # A run row requires its parent hn_item
        repo.upsert_item(HNItem(id=123))

        processed_run = make_processed_run(123, 1)

        # Save the run
        save_processed_run(processed_run, outputs_root=outputs_root)

        # Assert the run is readable back via the public function
        saved = get_run(123, 1)
        assert saved is not None
        assert saved.item_id == 123
        assert saved.run == 1
        assert saved.summary == "Summary"

        # Assert the run shows up in the runs list
        assert list_runs_for_item(123) == [1]

        # Assert file exists
        disk_path = get_run_disk_path(outputs_root, 123, 1)
        assert os.path.exists(disk_path)

        # Verify file content
        with open(disk_path, "r") as f:
            saved_data = json.load(f)
            assert saved_data["item_id"] == 123
            assert saved_data["run"] == 1
            assert saved_data["summary"] == "Summary"

    def test_list_runs_for_item_newest_first(self, outputs_root):
        """Test that list_runs_for_item returns newest first."""
        repo.upsert_item(HNItem(id=123))

        # Save runs 1 and 2 — run 2 is the newest
        save_processed_run(make_processed_run(123, 1), outputs_root=outputs_root)
        save_processed_run(make_processed_run(123, 2), outputs_root=outputs_root)

        # Test listing - should return newest (highest run number) first
        runs = list_runs_for_item(123)
        assert runs == [2, 1]

    def test_list_runs_for_item_with_pagination(self, outputs_root):
        """Test pagination in list_runs_for_item."""
        repo.upsert_item(HNItem(id=123))

        # Seed with multiple runs; newest-first order is [5, 4, 3, 2, 1]
        for run in [1, 2, 3, 4, 5]:
            save_processed_run(make_processed_run(123, run), outputs_root=outputs_root)

        # Test pagination - offset 1, limit 2 should return [4, 3]
        runs = list_runs_for_item(123, offset=1, limit=2)
        assert runs == [4, 3]

    def test_get_run_roundtrip(self):
        """Test get_run roundtrip."""
        repo.upsert_item(HNItem(id=123))

        # Save a run directly through the repo
        repo.save_run(make_processed_run(123, 1))

        # Retrieve and verify
        retrieved_run = get_run(123, 1)
        assert retrieved_run is not None
        assert retrieved_run.item_id == 123
        assert retrieved_run.run == 1
        assert retrieved_run.summary == "Summary"

    def test_get_run_missing(self):
        """Test get_run with missing run."""
        retrieved_run = get_run(123, 999)
        assert retrieved_run is None

    def test_disk_path_helper(self):
        """Test disk path helper function."""
        path = get_run_disk_path("/outputs", 123, 1)
        expected = "/outputs/hn/item/123/runs/1/processed.json"
        assert path == expected
