"""Cross-shot memory for image prompts.

Originally the loop had no reference to previous shots at all, so a take held
its style but not its world. Passing the previous *scenes* fixed that and
created the opposite failure — measured, the model simply continued the prose
and sixteen distinct visual intents became one repeated tableau.

What is passed now is the previous SUBJECTS, framed as things to avoid. These
tests pin that contract, because the natural-looking version (send the scenes)
is the one that was wrong.
"""

from unittest.mock import patch

import pytest

from ..utils import segment_utils
from ..utils.segment_utils import PRIOR_SCENE_WINDOW, _prior_scenes_block


class TestPriorScenesBlock:
    def test_empty_history_adds_nothing(self):
        assert _prior_scenes_block(None) == ""
        assert _prior_scenes_block([]) == ""
        assert _prior_scenes_block(["", None]) == ""

    def test_subjects_are_extracted_not_the_prose(self):
        """Passing the scenes themselves made the model continue them."""
        out = _prior_scenes_block(["A lone engineer at a CRT.", "A copper list."])
        assert "engineer" in out and "crt" in out and "copper" in out
        # The cinematography words carry no subject and would only add noise.
        assert "A lone engineer at a CRT." not in out

    def test_framed_as_things_to_avoid(self):
        out = _prior_scenes_block(["A lone engineer at a CRT."])
        assert "do NOT build on these" in out

    def test_only_the_recent_window_is_sent(self):
        """More would crowd out the beat actually being written."""
        scenes = [f"a kestrel numbered {i}" for i in range(1, 10)]
        out = _prior_scenes_block(scenes)
        assert out.count("\n  - ") == PRIOR_SCENE_WINDOW

    def test_a_long_scene_cannot_flood_the_block(self):
        """One unbroken 500-character token used to land in the prompt whole."""
        out = _prior_scenes_block(["x" * 500])
        assert len(out) < 200


class TestPromptThreading:
    def _render_args(self, **kwargs):
        captured = {}

        def fake_render(name, **kw):
            captured.update(kw)
            return "PROMPT"

        kwargs.setdefault("section_index", 1)
        with (
            patch("hnfm.content.prompts.render", side_effect=fake_render),
            patch(
                "hnfm.content.llm_service.LLMService.generate_content",
                return_value="a scene",
            ),
            patch("hnfm.content.art_direction.compose_prompt", side_effect=lambda s, t: s),
        ):
            segment_utils.generate_image_prompt_v1("line", "summary", **kwargs)
        return captured

    def test_prior_subjects_reach_the_prompt(self):
        args = self._render_args(prior_scenes=["A lone engineer at a CRT."])
        assert "engineer" in args["prior_scenes"]

    def test_absent_history_renders_an_empty_slot(self):
        """The template always interpolates the key, so it must exist."""
        args = self._render_args()
        assert args["prior_scenes"] == ""

    def test_the_first_shot_of_a_take_has_no_history(self):
        args = self._render_args(prior_scenes=[])
        assert args["prior_scenes"] == ""


class TestPromptTemplate:
    def test_the_template_declares_the_slot(self):
        from ..content.prompts import render

        out = render(
            "image.scene",
            run_summary="s",
            line_text="l",
            visual_intent="",
            shot_hint="",
            prior_scenes="\nSubjects already used in this take:\n  - crt\n",
            register="REGISTER FOR THIS BEAT (binding): mechanism\n",
        )
        assert "crt" in str(out)
        assert "mechanism" in str(out)


class TestVisualRegisters:
    """Registers rotate what is IN frame, which is the axis that failed.

    Camera angle was never the problem: shot coverage measured 0.64 while
    subjects repeated, so a take could show eight angles of one desk.
    """

    def test_registers_rotate_rather_than_repeat(self):
        from ..utils.segment_utils import VISUAL_REGISTERS, _register_block

        seen = [_register_block(i) for i in range(1, len(VISUAL_REGISTERS) + 1)]
        assert len(set(seen)) == len(VISUAL_REGISTERS)

    def test_the_cycle_wraps(self):
        from ..utils.segment_utils import VISUAL_REGISTERS, _register_block

        n = len(VISUAL_REGISTERS)
        assert _register_block(1) == _register_block(n + 1)

    def test_register_is_marked_binding(self):
        """Advisory phrasing was ignored; the model needs it as a constraint."""
        from ..utils.segment_utils import _register_block

        assert "binding" in _register_block(1).lower()

    def test_registers_cover_more_than_one_kind_of_frame(self):
        from ..utils.segment_utils import VISUAL_REGISTERS

        joined = " ".join(VISUAL_REGISTERS).lower()
        for axis in ("human", "material", "architectural", "mechanism", "landscape"):
            assert axis in joined


class TestNarrationChunking:
    """Magpie's gRPC response cap is 4 MB — roughly 95 seconds of audio, about
    350 words — and a longer request fails outright. Script lines never reach
    it; digest sections are 350-500 words and reach it every time."""

    def test_long_prose_is_split(self):
        from ..audio.digest_audio import MAX_WORDS_PER_CALL, chunk_for_tts

        text = "This is a sentence about porting an old game. " * 40
        chunks = chunk_for_tts(text)
        assert len(chunks) > 1
        assert all(len(c.split()) <= MAX_WORDS_PER_CALL for c in chunks)

    def test_sentences_are_never_cut(self):
        """A mid-sentence split is audible: the voice drops its intonation."""
        from ..audio.digest_audio import chunk_for_tts

        text = "One sentence here. " * 60
        assert all(c.rstrip().endswith(".") for c in chunk_for_tts(text))

    def test_short_prose_is_left_alone(self):
        from ..audio.digest_audio import chunk_for_tts

        assert chunk_for_tts("Just the one line.") == ["Just the one line."]

    def test_no_content_is_dropped(self):
        from ..audio.digest_audio import chunk_for_tts

        text = "Alpha beta. Gamma delta. " * 30
        joined = " ".join(chunk_for_tts(text))
        assert joined.split() == text.split()

    def test_empty_input_does_not_crash(self):
        from ..audio.digest_audio import chunk_for_tts

        assert chunk_for_tts("") == []
