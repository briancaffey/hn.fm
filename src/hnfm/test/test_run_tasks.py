"""Tests for run processing tasks (called directly against the test DB)."""

from unittest.mock import patch

import pytest

from ..db import repo
from ..web import tasks
from ..web.tasks import process_hn_item_run
from ..web.models import HNItem


def _mock_metadata():
    """Patch the cosmetic metadata generators (LLM call sites)."""
    return (
        patch.object(tasks, "generate_short_description", return_value="Short"),
        patch.object(tasks, "generate_tags", return_value=["tech"]),
        patch.object(tasks, "generate_emoji", return_value=["📰", "✨", "🔥", "💡"]),
        patch.object(tasks, "generate_haiku", return_value="Test haiku"),
    )


class TestRunTasks:
    """Test run processing tasks."""

    def test_process_hn_item_run_missing_item_raises(self):
        """Test that missing item raises exception."""
        # No item stored in the database

        with pytest.raises(RuntimeError, match="Item 123 not found"):
            process_hn_item_run(123, 1)

    def test_process_hn_item_run_missing_url_raises(self):
        """Test that item without URL raises exception."""
        # Seed item data without URL
        repo.upsert_item(HNItem(id=123, title="Test Article"))

        with pytest.raises(RuntimeError, match="Item 123 has no URL"):
            process_hn_item_run(123, 1)

    def test_process_hn_item_run_scrape_failure_falls_back(self):
        """Scrape failure is non-fatal: content degrades to the HN title/text."""
        repo.upsert_item(
            HNItem(id=123, title="Test Article", url="https://example.com")
        )

        p_desc, p_tags, p_emoji, p_haiku = _mock_metadata()
        with (
            patch.object(
                tasks,
                "scrape_url_with_source",
                side_effect=RuntimeError("Failed to scrape"),
            ),
            patch.object(tasks, "summarize_text_v1", return_value="Summary") as mock_sum,
            p_desc,
            p_tags,
            p_emoji,
            p_haiku,
        ):
            result = process_hn_item_run(123, 1)

        assert result == {"status": "ok", "item_id": 123, "run": 1}

        # The run was saved with fallback content built from the HN title
        processed_run = repo.get_run(123, 1)
        assert processed_run is not None
        assert "Test Article" in processed_run.content_raw
        assert processed_run.summary == "Summary"
        mock_sum.assert_called_once()

    def test_process_hn_item_run_summarize_failure_raises(self):
        """Test that a summarization failure fails the task."""
        repo.upsert_item(
            HNItem(id=123, title="Test Article", url="https://example.com")
        )

        with (
            patch.object(
                tasks,
                "scrape_url_with_source",
                return_value=("Scraped article body", "firecrawl"),
            ),
            patch.object(
                tasks,
                "summarize_text_v1",
                side_effect=RuntimeError("Failed to summarize"),
            ),
        ):
            with pytest.raises(RuntimeError, match="Failed to summarize"):
                process_hn_item_run(123, 1)

    def test_process_hn_item_run_success_persists_run(self):
        """Happy path: scraped + summarized content is saved to the run row."""
        repo.upsert_item(
            HNItem(id=123, title="Test Article", url="https://example.com")
        )

        p_desc, p_tags, p_emoji, p_haiku = _mock_metadata()
        with (
            patch.object(
                tasks,
                "scrape_url_with_source",
                return_value=("  Scraped   article body  ", "firecrawl"),
            ),
            patch.object(tasks, "summarize_text_v1", return_value="Summary"),
            p_desc,
            p_tags,
            p_emoji,
            p_haiku,
        ):
            result = process_hn_item_run(123, 1)

        assert result == {"status": "ok", "item_id": 123, "run": 1}

        processed_run = repo.get_run(123, 1)
        assert processed_run is not None
        assert processed_run.source_url == "https://example.com"
        assert processed_run.content_clean == "Scraped article body"
        assert processed_run.summary == "Summary"
        assert processed_run.tags == ["tech"]
