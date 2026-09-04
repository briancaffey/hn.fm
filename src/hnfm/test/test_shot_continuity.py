"""Cross-shot memory for image prompts (issue #14).

`generate_image_prompt_v1` ran once per section in a loop with no reference to
previous shots, so cross-shot continuity was impossible by construction: the
theme kept a take stylistically cohesive while its subjects wandered.
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

    def test_scenes_are_numbered_for_the_director(self):
        out = _prior_scenes_block(["A lone engineer at a CRT.", "A copper list."])
        assert "1. A lone engineer at a CRT." in out
        assert "2. A copper list." in out

    def test_only_the_recent_window_is_sent(self):
        """More would crowd out the beat actually being written."""
        scenes = [f"scene {i}" for i in range(1, 10)]
        out = _prior_scenes_block(scenes)
        assert "scene 9" in out
        assert "scene 1\n" not in out
        assert out.count("\n  ") == PRIOR_SCENE_WINDOW

    def test_a_long_scene_is_truncated(self):
        out = _prior_scenes_block(["x" * 500])
        assert len(out) < 300


class TestPromptThreading:
    def _render_args(self, **kwargs):
        captured = {}

        def fake_render(name, **kw):
            captured.update(kw)
            return "PROMPT"

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

    def test_prior_scenes_reach_the_prompt(self):
        args = self._render_args(prior_scenes=["A lone engineer at a CRT."])
        assert "A lone engineer at a CRT." in args["prior_scenes"]

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
            prior_scenes="\nScenes already shown in this take:\n  1. A CRT.\n",
        )
        assert "A CRT." in str(out)
