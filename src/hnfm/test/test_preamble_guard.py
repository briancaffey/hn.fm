"""Model preamble must never reach TTS (issue #16).

A recorded step error reads: `Failed to generate speech for text: Since the
actual article content was provided in the second attempt, I'll ...`. That is
the model narrating its own task, handed to text-to-speech. It was caught only
because TTS choked on the length — a shorter preamble would have been spoken
aloud in the finished video.
"""

import pytest

from ..content.llm_schemas import Script, ScriptSection
from ..utils.segment_utils import preamble_sections


def _script(texts):
    return Script(
        title="T",
        sections=[
            ScriptSection(
                index=i + 1,
                speaker="S1" if i % 2 == 0 else "S2",
                beat="cold_open" if i == 0 else ("close" if i == len(texts) - 1 else "detail"),
                text=t,
                visual_intent="a desk",
            )
            for i, t in enumerate(texts)
        ],
    )


class TestPreambleDetection:
    @pytest.mark.parametrize(
        "text",
        [
            "Since the actual article content was provided in the second attempt, I'll write the script.",
            "Here's the script you asked for.",
            "Sure, let me walk through the port.",
            "As an AI language model, I should note the port took months.",
            "Below is a two-host conversation about the Amiga port.",
            "The user asked for a cold open, so this starts on the 50 Hz bug.",
        ],
    )
    def test_preamble_is_detected(self, text):
        assert preamble_sections(_script(["a", text, "c"])) == [2]

    @pytest.mark.parametrize(
        "text",
        [
            "The port took four months of evenings.",
            "Fifty hertz and sixty hertz in the same game.",
            "I'd never seen a copper list rewritten per frame.",
            "Let me be clear about the timing bug — actually, look at the numbers.",
        ],
    )
    def test_real_narration_is_not_flagged(self, text):
        """A false positive fails a perfectly good run, so the markers have to
        be specific to the model addressing its task."""
        assert preamble_sections(_script(["a", text, "c"])) == []

    def test_clean_script_has_no_flags(self):
        assert preamble_sections(
            _script([
                "Fifty hertz and sixty hertz in the same game.",
                "The original ran on 512 kilobytes of RAM.",
                "That is the whole story.",
            ])
        ) == []

    def test_multiple_leaks_are_all_reported(self):
        found = preamble_sections(
            _script([
                "Here's the script.",
                "A real line.",
                "As an AI language model I should add a caveat.",
            ])
        )
        assert found == [1, 3]

    def test_a_host_saying_ill_wrap_up_is_narration(self):
        """"I'll wrap up now" is something a host says. Only the task-directed
        forms ("I'll write the script") are preamble."""
        assert preamble_sections(_script(["a", "I'll wrap up now.", "c"])) == []
        assert preamble_sections(_script(["a", "I'll write the script.", "c"])) == [2]

    def test_only_the_opening_of_a_line_is_examined(self):
        """A line that merely contains the phrase mid-sentence is narration."""
        long_line = (
            "The compiler rewrote the level tables, and the developer said the "
            "hardest part came later when I'll admit the timing surprised him."
        )
        assert preamble_sections(_script(["a", long_line, "c"])) == []


class TestGenerationRejectsPreamble:
    def test_generate_script_raises_rather_than_narrating_it(self):
        from unittest.mock import patch

        from ..utils import segment_utils

        bad = _script([
            "Here's the script you asked for.",
            "The port took four months.",
            "That is the whole story.",
        ])
        with patch(
            "hnfm.content.llm_service.LLMService.generate_structured", return_value=bad
        ):
            with pytest.raises(RuntimeError, match="model preamble"):
                segment_utils.generate_script("content " * 100, "summary")
