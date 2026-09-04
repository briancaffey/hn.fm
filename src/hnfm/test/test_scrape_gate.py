"""Deterministic scrape-time gate (issue #6).

`producibility_ceiling` already knew, for free, that a scrape had nothing in
it — but it was only consulted inside triage, five LLM calls downstream. A
43-character HTTP error page paid for a summary, four enrichment calls and a
triage call before anything concluded there was no story.
"""

from unittest.mock import patch

import pytest

from ..db import repo, steps
from ..web import tasks
from ..web.tasks import process_hn_item_run
from ..web.models import HNItem


def _mock_metadata():
    return (
        patch.object(tasks, "generate_short_description", return_value="d"),
        patch.object(tasks, "generate_tags", return_value=["t"]),
        patch.object(tasks, "generate_emoji", return_value=["a", "b", "c", "d"]),
        patch.object(tasks, "generate_haiku", return_value="h"),
    )


class TestScrapeGate:
    def test_an_empty_scrape_costs_no_llm_calls(self):
        """The concrete case: a Wayback copy of an HTTP status page."""
        repo.upsert_item(HNItem(id=555, title="Dead link", url="https://x.example"))

        with (
            patch.object(
                tasks, "scrape_url_with_source", return_value=("404 Not Found", "wayback")
            ),
            patch.object(tasks, "summarize_text_v1") as summarize,
            patch.object(tasks, "generate_tags") as tags,
        ):
            result = process_hn_item_run(555, 1)

        assert result["status"] == "gated"
        summarize.assert_not_called()
        tags.assert_not_called()

    def test_the_story_is_still_visible_with_a_reason(self):
        """Gated is not deleted — it must appear in the UI, scored, with why."""
        repo.upsert_item(HNItem(id=556, title="Dead link", url="https://x.example"))

        with patch.object(
            tasks, "scrape_url_with_source", return_value=("404", "wayback")
        ):
            process_hn_item_run(556, 1)

        run = repo.get_run(556, 1)
        assert run is not None

        score = repo.get_triage_score(556, 1)
        assert score["verdict"] == "unsuitable"
        assert "no_content" in score["flags"]
        assert score["model"] == "deterministic/scrape_signals"
        assert "nothing to build a story from" in score["reasons"][0]

    def test_the_gate_is_recorded_as_a_step(self):
        repo.upsert_item(HNItem(id=557, title="Dead link", url="https://x.example"))
        with patch.object(
            tasks, "scrape_url_with_source", return_value=("404", "wayback")
        ):
            process_hn_item_run(557, 1)

        keys = [s["step_key"] for s in steps.list_steps(557, 1)]
        assert "scrape" in keys
        assert "triage/score" in keys
        assert "summary" not in keys
        assert "enrich" not in keys

    def test_a_real_article_passes_the_gate(self):
        """The gate must only fire where there is demonstrably no text."""
        repo.upsert_item(HNItem(id=558, title="Real", url="https://x.example"))
        article = "This is a real article. " * 200

        p_desc, p_tags, p_emoji, p_haiku = _mock_metadata()
        with (
            patch.object(
                tasks, "scrape_url_with_source", return_value=(article, "firecrawl")
            ),
            patch.object(tasks, "summarize_text_v1", return_value="S") as summarize,
            p_desc, p_tags, p_emoji, p_haiku,
        ):
            result = process_hn_item_run(558, 1)

        assert result["status"] == "ok"
        summarize.assert_called_once()

    def test_a_self_post_with_real_text_passes(self):
        """Self-posts must not be caught by a gate aimed at empty scrapes."""
        repo.upsert_item(
            HNItem(id=559, title="Ask HN: something", text="A real question. " * 100)
        )

        p_desc, p_tags, p_emoji, p_haiku = _mock_metadata()
        with (
            patch.object(tasks, "summarize_text_v1", return_value="S"),
            p_desc, p_tags, p_emoji, p_haiku,
        ):
            result = process_hn_item_run(559, 1)

        assert result["status"] == "ok"
