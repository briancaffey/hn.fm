"""Transient LLM retry (issue #15).

18 of 24 recorded step errors were one line: "all models failed — spark-omni:
Connection error." The box was briefly unreachable, and with no fallback
configured that threw away the run.
"""

from unittest.mock import patch

import pytest

from ..content.llm_service import (
    TRANSIENT_RETRIES,
    LLMError,
    LLMService,
    _is_transient,
)


class TestTransientClassification:
    @pytest.mark.parametrize(
        "message",
        [
            "Connection error.",
            "connection refused",
            "Read timed out",
            "503 Service Unavailable",
            "502 Bad Gateway",
        ],
    )
    def test_transport_failures_are_transient(self, message):
        assert _is_transient(RuntimeError(message)) is True

    @pytest.mark.parametrize(
        "message",
        [
            "Error code: 400 - invalid request",
            "spark-omni returned empty content",
            "spark-omni returned no choices",
            "410 Gone",
        ],
    )
    def test_real_answers_are_not_retried(self, message):
        """A 400 or an empty completion is identical the second time; retrying
        just triples the cost of a deterministic failure."""
        assert _is_transient(RuntimeError(message)) is False


class TestRetryBehaviour:
    def _service(self):
        with patch.object(LLMService, "__init__", return_value=None):
            svc = LLMService()
        svc.model = "spark-omni"
        svc.fallback_model = None
        return svc

    def test_a_connection_error_is_retried_on_the_same_model(self):
        svc = self._service()
        with (
            patch.object(
                svc, "_call",
                side_effect=[RuntimeError("Connection error."), "recovered"],
            ) as call,
            patch("time.sleep"),
        ):
            assert svc._call_with_retry("spark-omni", "p") == "recovered"
        assert call.call_count == 2

    def test_it_gives_up_after_the_configured_attempts(self):
        svc = self._service()
        with (
            patch.object(
                svc, "_call", side_effect=RuntimeError("Connection error.")
            ) as call,
            patch("time.sleep"),
        ):
            with pytest.raises(RuntimeError, match="Connection error"):
                svc._call_with_retry("spark-omni", "p")
        assert call.call_count == TRANSIENT_RETRIES

    def test_a_non_transient_error_fails_immediately(self):
        svc = self._service()
        with (
            patch.object(
                svc, "_call", side_effect=RuntimeError("Error code: 400")
            ) as call,
            patch("time.sleep"),
        ):
            with pytest.raises(RuntimeError, match="400"):
                svc._call_with_retry("spark-omni", "p")
        assert call.call_count == 1

    def test_backoff_grows_between_attempts(self):
        svc = self._service()
        with (
            patch.object(
                svc, "_call", side_effect=RuntimeError("Connection error.")
            ),
            patch("time.sleep") as sleep,
        ):
            with pytest.raises(RuntimeError):
                svc._call_with_retry("spark-omni", "p")
        delays = [c.args[0] for c in sleep.call_args_list]
        assert delays == sorted(delays) and len(set(delays)) > 1

    def test_generate_content_survives_a_blip(self):
        svc = self._service()
        with (
            patch.object(
                svc, "_call",
                side_effect=[RuntimeError("Connection error."), "the summary"],
            ),
            patch("time.sleep"),
        ):
            assert svc.generate_content("p") == "the summary"
