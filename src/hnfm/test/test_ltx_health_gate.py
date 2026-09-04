"""Health-gating the render path (issue #19).

`/api/services/status` already reported LTX offline while the pipeline queued
motion clips against it anyway. Each attempt burned three retries; one run
recorded four `media_plan/clip_*` errors that way.
"""

from unittest.mock import patch

import pytest

from ..content import meta_sequencer


def _plan(n=6, template="video"):
    return [{"index": i, "template": template, "why": ""} for i in range(1, n + 1)]


class TestGuardrailsRespectBackendHealth:
    def test_clips_are_not_planned_when_ltx_is_down(self):
        with patch.object(meta_sequencer, "_video_backend_available", return_value=False):
            out = meta_sequencer._apply_guardrails(_plan(), 6, max_video=2)
        assert [p["template"] for p in out].count("video") == 0

    def test_clips_are_planned_when_ltx_is_up(self):
        with patch.object(meta_sequencer, "_video_backend_available", return_value=True):
            out = meta_sequencer._apply_guardrails(_plan(), 6, max_video=2)
        assert [p["template"] for p in out].count("video") > 0

    def test_every_section_still_gets_a_template(self):
        """Dropping clips must not drop sections."""
        with patch.object(meta_sequencer, "_video_backend_available", return_value=False):
            out = meta_sequencer._apply_guardrails(_plan(8), 8, max_video=2)
        assert [p["index"] for p in out] == list(range(1, 9))
        assert all(p["template"] for p in out)

    def test_a_broken_probe_does_not_disable_clips(self):
        """Unknown health must read as available — the existing soft_fail path
        already handles a backend that turns out to be down."""
        with patch(
            "hnfm.video.ltx_service.is_available", side_effect=RuntimeError("boom")
        ):
            assert meta_sequencer._video_backend_available() is True

    def test_the_probe_is_not_consulted_when_no_clips_were_wanted(self):
        with patch.object(meta_sequencer, "_video_backend_available") as probe:
            meta_sequencer._apply_guardrails(_plan(template="image_sequence"), 6, max_video=0)
        probe.assert_not_called()


class TestHealthCache:
    def test_the_probe_result_is_cached(self):
        from ..video import ltx_service

        ltx_service._health_cache.update(checked_at=0.0, ok=None)
        with patch.dict("os.environ", {"LTX_BASE_URL": "http://ltx.invalid"}):
            with patch("requests.get", side_effect=RuntimeError("down")) as get:
                assert ltx_service.is_available() is False
                assert ltx_service.is_available() is False
        assert get.call_count == 1
