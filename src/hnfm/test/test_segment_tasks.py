"""Tests for segment Celery tasks (called directly against the test DB)."""

from datetime import datetime
from unittest.mock import patch

import pytest

from ..db import repo
from ..web import tasks
from ..web.tasks import generate_segment
from ..web.models import HNItem, ProcessedRun


def _seed_run(
    content_clean: str = "Clean content for script generation",
    summary: str = "Article summary",
) -> None:
    """Create the hn item + processed run rows the task loads."""
    repo.upsert_item(HNItem(id=123))
    repo.save_run(
        ProcessedRun(
            key="hnfm:item:123:run:1",
            item_id=123,
            run=1,
            created_at=datetime.utcnow(),
            source_url="https://example.com",
            content_raw="Raw content",
            content_clean=content_clean,
            summary=summary,
            short_description="Short description",
            tags=["tech", "ai"],
            emoji=["🤖", "💻", "🚀", "⚡"],
            haiku="Technology grows\nArtificial intelligence\nFuture is bright",
        )
    )


class TestGenerateSegmentTask:
    """Test the generate_segment Celery task"""

    def test_generate_segment_function_exists(self):
        """Test that generate_segment function exists and is callable"""
        assert callable(generate_segment)

    def test_generate_segment_missing_run_raises(self):
        """Test segment generation when processed run is missing"""
        # No processed run stored in the database

        # Call the task and expect exception
        with pytest.raises(
            RuntimeError,
            match="ProcessedRun 123:1 not found in database",
        ):
            generate_segment(123, 1, 1)

    def test_generate_segment_empty_fields_raises(self):
        """Test segment generation when processed run has empty content_clean or summary"""
        # Store processed run with empty content_clean
        _seed_run(content_clean="")

        # Call the task and expect exception
        with pytest.raises(
            RuntimeError,
            match="ProcessedRun 123:1 missing content_clean or summary",
        ):
            generate_segment(123, 1, 1)

    def test_generate_segment_saves_script(self, outputs_root):
        """Test the happy path with the LLM script generation mocked"""
        _seed_run()

        script = "[S1] Hey there!\n[S2] Welcome to the show."
        with patch.object(tasks, "generate_script_v1", return_value=script) as mock_llm:
            result = generate_segment(123, 1, 1)

        assert result == {"status": "ok", "item_id": 123, "run": 1, "seg": 1}
        mock_llm.assert_called_once_with(
            "Clean content for script generation", "Article summary"
        )

        segment = repo.get_segment(123, 1, 1)
        assert segment is not None
        assert segment.script == script

    def test_generate_segment_imports_work(self):
        """Test that all required imports work for the task"""
        # Test that we can import the task function
        from ..web.tasks import generate_segment

        assert callable(generate_segment)
