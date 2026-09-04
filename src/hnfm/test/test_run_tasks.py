"""Tests for run processing tasks (called directly against the test DB)."""

from unittest.mock import patch

import pytest

from ..db import repo, steps
from ..web import tasks
from ..web.tasks import process_hn_item_run
from ..web.models import HNItem

# The scrape-time gate (issue #6) drops runs whose scrape yields under 400
# characters, so fixtures standing in for a real article have to look like
# one. `_ARTICLE` is the shortest body that is unambiguously an article.
_ARTICLE = (
    "Scraped article body. The port took four months of evenings and the "
    "hardest part was timing. "
) * 6


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

    def test_process_hn_item_run_no_url_and_no_text_raises(self):
        """An item with neither a URL nor text has nothing to process."""
        repo.upsert_item(HNItem(id=123, title="Test Article"))

        with pytest.raises(RuntimeError, match="Item 123 has no URL and no text"):
            process_hn_item_run(123, 1)

    def test_process_hn_item_run_self_post_uses_hn_text(self):
        """Ask HN / Show HN posts carry no URL — item.text IS the article.

        It must not be marked `fallback`, because that caps producibility at 15
        and would bury every self-post regardless of quality.
        """
        repo.upsert_item(
            HNItem(
                id=123,
                title="Ask HN: How do you test Celery chains?",
                text="We run a pipeline of chained tasks and " * 20,
            )
        )

        p_desc, p_tags, p_emoji, p_haiku = _mock_metadata()
        with (
            patch.object(tasks, "scrape_url_with_source") as mock_scrape,
            patch.object(tasks, "summarize_text_v1", return_value="Summary"),
            p_desc,
            p_tags,
            p_emoji,
            p_haiku,
        ):
            result = process_hn_item_run(123, 1)

        assert result["status"] == "ok"
        mock_scrape.assert_not_called()

        scrape_steps = [
            s for s in steps.list_steps(123, 1) if s["step_key"] == "scrape"
        ]
        assert len(scrape_steps) == 1
        outputs = scrape_steps[0]["outputs"] or {}
        assert outputs["source"] == "hn_text"
        assert outputs["fallback"] is False
        assert outputs["signals"]["chars"] > 100

    def test_process_hn_item_run_scrape_failure_falls_back(self):
        """Scrape failure is non-fatal: the run is still saved from the HN
        title/text, and the deterministic gate stops it there.

        A bare title is not an article. The fallback keeps the story visible;
        the scrape-time gate (issue #6) is what stops it costing five LLM
        calls to discover there is nothing to say about it.
        """
        repo.upsert_item(
            HNItem(id=123, title="Test Article", url="https://example.com")
        )

        with (
            patch.object(
                tasks,
                "scrape_url_with_source",
                side_effect=RuntimeError("Failed to scrape"),
            ),
            patch.object(tasks, "summarize_text_v1") as mock_sum,
        ):
            result = process_hn_item_run(123, 1)

        assert result["status"] == "gated"
        mock_sum.assert_not_called()

        # The run was still saved with fallback content built from the HN title
        processed_run = repo.get_run(123, 1)
        assert processed_run is not None
        assert "Test Article" in processed_run.content_raw

        # And it is scored, so it shows up in the UI with a reason.
        score = repo.get_triage_score(123, 1)
        assert score["verdict"] == "unsuitable"

    def test_scrape_failure_with_substantial_hn_text_still_proceeds(self):
        """The fallback is only worthless when the HN text is too. A failed
        scrape on a post with a real body must still run the pipeline."""
        repo.upsert_item(
            HNItem(
                id=124,
                title="Test Article",
                url="https://example.com",
                text="A genuinely substantial discussion post. " * 20,
            )
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
            result = process_hn_item_run(124, 1)

        assert result["status"] == "ok"
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
                return_value=(_ARTICLE, "firecrawl"),
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
                return_value=(f"  {_ARTICLE}  ", "firecrawl"),
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
        assert processed_run.content_clean == _ARTICLE.strip()
        assert processed_run.summary == "Summary"
        assert processed_run.tags == ["tech"]
