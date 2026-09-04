"""Verdict derivation (issue #11).

The model used to return the verdict itself and barely discriminated: 33%
"great", 2.3% "unsuitable" across 207 scored stories. A story that scraped 43
characters of an HTTP error page came back "marginal" — enough to earn it a
Story Brief. The model judges the two axes; code buckets them.
"""

from unittest import mock

import pytest

from ..content import triage


class TestDeriveVerdict:
    @pytest.mark.parametrize(
        "interest,producibility,expected",
        [
            (95, 90, "great"),
            (80, 75, "great"),      # exactly on the boundary
            (79, 90, "good"),       # interest just under
            (95, 74, "good"),       # producibility just under
            (60, 50, "good"),
            (59, 50, "marginal"),
            (70, 40, "marginal"),
            (10, 5, "unsuitable"),
            (90, 20, "unsuitable"),  # nothing to make of it, however interesting
            (15, 90, "unsuitable"),  # producible but nobody cares
        ],
    )
    def test_buckets(self, interest, producibility, expected):
        assert triage.derive_verdict(interest, producibility) == expected

    def test_the_43_char_error_page_is_now_unsuitable(self):
        """The concrete case from item 49558610: interest=10, producibility=5,
        rank 2.84 — and the model called it 'marginal'."""
        assert triage.derive_verdict(10, 5) == "unsuitable"

    def test_the_zero_interest_case_is_unsuitable(self):
        """Item 49554643: 'no content retrieved - only error message visible'."""
        assert triage.derive_verdict(0, 15) == "unsuitable"

    def test_thresholds_are_configurable(self):
        with mock.patch.object(
            triage, "verdict_thresholds",
            return_value={**triage._VERDICT_DEFAULTS, "great_interest": 99},
        ):
            assert triage.derive_verdict(95, 90) == "good"

    def test_unsuitable_wins_over_great(self):
        """The floor is a veto, not a tiebreak."""
        t = triage.verdict_thresholds()
        assert triage.derive_verdict(100, t["unsuitable_producibility"]) == "unsuitable"

    def test_every_verdict_is_a_valid_enum_value(self):
        valid = {"great", "good", "marginal", "unsuitable"}
        for i in range(0, 101, 5):
            for p in range(0, 101, 5):
                assert triage.derive_verdict(i, p) in valid

    def test_monotonic_in_both_axes(self):
        """Raising a score must never make the verdict worse."""
        rank = {"unsuitable": 0, "marginal": 1, "good": 2, "great": 3}
        for i in range(0, 100, 10):
            for p in range(0, 100, 10):
                base = rank[triage.derive_verdict(i, p)]
                assert rank[triage.derive_verdict(i + 10, p)] >= base
                assert rank[triage.derive_verdict(i, p + 10)] >= base


class TestLegacyRows:
    """Rows written before two-axis scoring carry NULL axes."""

    def test_none_axes_are_unsuitable_not_a_crash(self):
        assert triage.derive_verdict(None, None) == "unsuitable"
        assert triage.derive_verdict(90, None) == "unsuitable"
        assert triage.derive_verdict(None, 90) == "unsuitable"
