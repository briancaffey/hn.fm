"""Tests for two-axis scoring, scrape signals and the Story Brief (plans/09)."""

from unittest import mock

import pytest

from ..content import scrape_signals, story_brief, triage


class TestScrapeSignals:
    def test_counts_a_real_article(self):
        text = "\n\n".join(
            [
                "This is a substantial paragraph about a technical subject, long "
                "enough to count as prose rather than navigation furniture." * 2
            ]
            * 6
        )
        sig = scrape_signals.extract(text)
        assert sig["chars"] > 1000
        assert sig["paragraphs"] >= 1
        assert sig["fallback"] is False
        assert sig["looks_like_stub"] is False

    def test_stub_needs_both_short_and_wall_shaped(self):
        """Either condition alone produces false positives — a good short post,
        or an article legitimately *about* paywalls."""
        wall = "Please enable JavaScript to continue. Subscribe to read."
        assert scrape_signals.extract(wall)["looks_like_stub"] is True

        # Long article that merely discusses paywalls is not a stub.
        essay = ("An essay on why publishers ask readers to subscribe to continue. " * 60)
        assert scrape_signals.extract(essay)["looks_like_stub"] is False

        # Short but substantive is not a stub either.
        short = "We shipped a new compiler backend today. It is twice as fast."
        assert scrape_signals.extract(short)["looks_like_stub"] is False

    def test_markdown_signals_come_from_raw(self):
        raw = "# Title\n\n![img](a.png)\n\n```py\ncode()\n```\n\n[link](b)"
        sig = scrape_signals.extract("cleaned text", content_raw=raw)
        assert sig["image_count"] == 1
        assert sig["code_blocks"] == 1
        assert sig["heading_count"] == 1
        assert sig["link_count"] == 1

    def test_source_and_fallback_recorded(self):
        sig = scrape_signals.extract("x" * 500, source="wayback")
        assert sig["source"] == "wayback"
        assert "wayback" in scrape_signals.summarize(sig)

        sig = scrape_signals.extract("x" * 500, source="hn_fallback", fallback=True)
        assert "SCRAPE FAILED" in scrape_signals.summarize(sig)


class TestProducibilityCeiling:
    def test_the_fabrication_case_is_capped(self):
        """Item 48747304 had 214 chars and produced an invented institution.
        The ceiling is what keeps that out of the script writer."""
        sig = scrape_signals.extract("For first time, a cell built from scratch grows and divides")
        assert scrape_signals.producibility_ceiling(sig) == 20

    def test_failed_scrape_capped_hardest(self):
        sig = scrape_signals.extract("x" * 5000, fallback=True)
        assert scrape_signals.producibility_ceiling(sig) == 15

    def test_real_article_uncapped(self):
        sig = scrape_signals.extract("word " * 2000)
        assert scrape_signals.producibility_ceiling(sig) is None

    def test_ceiling_overrides_model_optimism(self):
        from ..content.llm_schemas import TriageScore

        scored = TriageScore(
            interest=95, producibility=90, verdict="great", reasons=[],
            flags=[], topics=["ai"], visual_potential=9, narrative_potential=9,
        )
        thin = scrape_signals.extract("A cell built from scratch grows and divides")
        with mock.patch(
            "hnfm.content.llm_service.LLMService.generate_structured", return_value=scored
        ):
            out = triage.score_content("t", "s", "c", signals=thin)
        assert out["interest"] == 95, "interest must NOT be capped — the story is still good"
        assert out["producibility"] == 20
        assert out["verdict"] == "marginal", "a capped story can't stay 'great'"


class TestRankingAndBuckets:
    def test_producibility_multiplies_rather_than_adds(self):
        """An unbuildable story must sink even when interest is maximal — an
        additive weight would let interest paper over an unusable scrape."""
        good = triage.rank_score(90, 0.0, 100, producibility=90)
        unbuildable = triage.rank_score(90, 0.0, 100, producibility=5)
        assert unbuildable < good / 2

    def test_unbuildable_still_ranks_above_zero(self):
        """Ordering, not censorship — Brian's standing position."""
        assert triage.rank_score(90, 0.0, 100, producibility=0) > 0

    def test_needs_better_source_bucket(self):
        assert triage.bucket(80, 20) == triage.NEEDS_BETTER_SOURCE
        assert triage.bucket(80, 90) is None  # buildable — just generate it
        assert triage.bucket(20, 20) is None  # dull AND unbuildable — not worth revisiting


class TestStoryBrief:
    def _framing(self):
        from ..content.llm_schemas import StoryFraming

        return StoryFraming(
            thesis="t", why_now="w", stakes="s", angle="a", tension="x",
            visual_affordances=["a lab bench"], unknowns=["who funded it"],
        )

    def _evidence(self, quote):
        from ..content.llm_schemas import StoryEvidence, KeyFact

        return StoryEvidence(
            key_facts=[KeyFact(claim="c", source="article", quote=quote)],
            entities=[], numbers=[],
        )

    def test_assembles_both_halves(self):
        article = "The team reported a doubling of throughput."
        with mock.patch(
            "hnfm.content.llm_service.LLMService.generate_structured",
            side_effect=[self._framing(), self._evidence("a doubling of throughput")],
        ):
            brief = story_brief.build("T", "S", article)
        assert brief["thesis"] == "t"
        assert brief["unknowns"] == ["who funded it"]
        assert len(brief["key_facts"]) == 1
        assert "partial" not in brief

    def test_fabricated_quote_is_dropped(self):
        """Everything downstream treats key_facts as ground truth — the script
        writer is explicitly told it may rely on them."""
        article = "The team reported a doubling of throughput."
        with mock.patch(
            "hnfm.content.llm_service.LLMService.generate_structured",
            side_effect=[self._framing(), self._evidence("a tenfold speedup at MIT")],
        ):
            brief = story_brief.build("T", "S", article)
        assert brief["key_facts"] == []

    def test_quote_matching_ignores_whitespace_and_smart_quotes(self):
        article = 'He said "we shipped it"   on Tuesday.'
        with mock.patch(
            "hnfm.content.llm_service.LLMService.generate_structured",
            side_effect=[self._framing(), self._evidence('He said “we shipped it” on Tuesday.')],
        ):
            brief = story_brief.build("T", "S", article)
        assert len(brief["key_facts"]) == 1

    def test_partial_brief_survives_one_half_failing(self):
        with mock.patch(
            "hnfm.content.llm_service.LLMService.generate_structured",
            side_effect=[self._framing(), RuntimeError("gateway down")],
        ):
            brief = story_brief.build("T", "S", "content")
        assert brief["thesis"] == "t"
        assert brief["key_facts"] == []
        assert "evidence" in str(brief["partial"])

    def test_total_failure_raises(self):
        with mock.patch(
            "hnfm.content.llm_service.LLMService.generate_structured",
            side_effect=RuntimeError("gateway down"),
        ):
            with pytest.raises(RuntimeError, match="story brief failed entirely"):
                story_brief.build("T", "S", "content")


class TestNeedsBetterSourceBucket:
    """The bucket end-to-end: scored rows -> API filter -> UI view."""

    def _seed(self, item_id, interest, producibility):
        from datetime import datetime
        from ..db import repo
        from ..web.models import HNItem, ProcessedRun

        repo.upsert_item(
            HNItem(id=item_id, title=f"Story {item_id}", url=f"http://x/{item_id}",
                   score=100, descendants=10, time=1_700_000_000)
        )
        repo.save_run(ProcessedRun(
            key="k", item_id=item_id, run=1, created_at=datetime.utcnow(),
            source_url="http://x", content_raw="raw", content_clean="c" * 500,
            summary="s", short_description="sd", tags=[], emoji=[], haiku="h",
        ))
        repo.save_triage_score(item_id, 1, {
            "interest": interest, "producibility": producibility,
            "verdict": "marginal", "reasons": [], "flags": [], "topics": [],
            "visual_potential": 5, "narrative_potential": 5,
            "interest_match": 0.0,
            "rank_score": triage.rank_score(interest, 0.0, 100,
                                            producibility=producibility),
            "model": "test",
        })

    def test_filter_selects_only_worth_it_but_unbuildable(self):
        from fastapi.testclient import TestClient
        from ..web.api import app

        self._seed(801, interest=85, producibility=15)  # worth it, bad scrape
        self._seed(802, interest=85, producibility=90)  # worth it, good scrape
        self._seed(803, interest=20, producibility=15)  # dull and unbuildable

        client = TestClient(app)
        ids = [r["item_id"] for r in
               client.get("/api/triage?bucket=needs_better_source").json()["items"]]
        assert ids == [801]

    def test_unfiltered_queue_ranks_buildable_first(self):
        """Same interest, different producibility — the buildable one wins."""
        from fastapi.testclient import TestClient
        from ..web.api import app

        self._seed(811, interest=85, producibility=15)
        self._seed(812, interest=85, producibility=90)

        client = TestClient(app)
        ids = [r["item_id"] for r in client.get("/api/triage").json()["items"]]
        assert ids.index(812) < ids.index(811)
