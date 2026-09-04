"""Story Brief gating and dispatch (issues #4 and #5).

The old gate was `verdict != "unsuitable"`, which skipped 3 of 132 scored
stories — 98% paid for two LLM calls and ~30s each. And the brief ran inline
inside score_run, holding one worker slot for triage-plus-brief as a unit.
"""

from unittest import mock

import pytest

from ..content import triage


class TestDeservesBrief:
    def _score(self, verdict="good", rank=90.0):
        return {"verdict": verdict, "rank_score": rank}

    def test_high_rank_earns_a_brief(self):
        assert triage.deserves_brief(self._score(rank=90.0)) is True

    def test_low_rank_does_not(self):
        assert triage.deserves_brief(self._score(rank=12.0)) is False

    def test_unsuitable_is_an_absolute_veto(self):
        """The observed corpus has an 'unsuitable' story ranking 84.9. When the
        model is confident there is nothing there, rank must not rescue it."""
        assert triage.deserves_brief(self._score("unsuitable", rank=84.9)) is False

    def test_a_high_ranking_marginal_still_qualifies(self):
        """Verdict and rank disagree; marginals reach 121 in the corpus and the
        digest draws from them."""
        assert triage.deserves_brief(self._score("marginal", rank=121.0)) is True

    def test_threshold_comes_from_config(self):
        with mock.patch.object(triage, "brief_min_rank", return_value=200.0):
            assert triage.deserves_brief(self._score(rank=150.0)) is False

    def test_missing_rank_is_treated_as_zero(self):
        assert triage.deserves_brief({"verdict": "good"}) is False

    def test_observed_verdict_minimums_clear_the_default(self):
        """`great` and `good` bottom out at 63.7 and 64.8 in the corpus; the
        default threshold must not drop them."""
        assert triage.brief_min_rank() <= 63.7


class TestBriefIsDispatched:
    def test_brief_is_queued_not_run_inline(self):
        """Inline, the brief ran inside score_run's 600s budget on the same
        worker slot."""
        from ..web import tasks

        with (
            mock.patch.object(tasks.build_story_brief, "apply_async") as queued,
            mock.patch.object(tasks.build_story_brief, "run") as ran,
        ):
            if triage.deserves_brief({"verdict": "great", "rank_score": 99.0}):
                tasks.build_story_brief.apply_async(args=[1, 1])
            queued.assert_called_once_with(args=[1, 1])
            ran.assert_not_called()

    def test_score_run_does_not_call_the_brief_synchronously(self):
        """Guards the regression directly: the call site must be apply_async."""
        import inspect

        from ..web import tasks

        src = inspect.getsource(tasks.score_run)
        assert "build_story_brief.apply_async" in src
        assert "build_story_brief(item_id, run)" not in src
