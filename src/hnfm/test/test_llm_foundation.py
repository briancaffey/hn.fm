"""Tests for the LLM foundation (plans/08-llm-foundation.md).

Covers the four guarantees the rest of the content work is built on: calls
cannot reach a route outside the policy, failures raise instead of returning
placeholder content, structured output is validated, and prompts are versioned
data whose provenance reaches the audit trail.
"""

from datetime import datetime
from unittest import mock

import pytest
from pydantic import BaseModel

from ..content import model_policy
from ..content.llm_schemas import Script, ScriptSection, TriageScore, to_strict_schema
from ..content.llm_service import LLMError, LLMService
from ..content.prompts import PromptNotFound, PromptRegistry, registry
from ..utils import segment_utils
from ..web.models import Segment


class TestModelPolicy:
    def test_free_routes_allowed(self):
        for model in ("nvidia-nemotron-super", "openrouter-nemotron-ultra"):
            model_policy.check_request(model)

    def test_groq_denied(self):
        """Brian's standing rule; the gateway exposes a groq route."""
        with pytest.raises(model_policy.ModelNotAllowed, match="denied"):
            model_policy.check_request("groq-llama-3.3-70b")

    def test_paid_passthrough_denied(self):
        """The gateway advertises ~200 `lmstudio/*` OpenAI-catalog routes."""
        for model in ("lmstudio/gpt-5.6", "lmstudio/o3-pro", "lmstudio/sora-2"):
            with pytest.raises(
                model_policy.ModelNotAllowed, match="not in the allowlist"
            ):
                model_policy.check_request(model)

    def test_empty_model_denied(self):
        with pytest.raises(model_policy.ModelNotAllowed):
            model_policy.check_request("")

    def test_deny_beats_allow(self):
        """A broad allow pattern must not re-admit an explicitly denied route."""
        with mock.patch.object(model_policy, "allowed_patterns", lambda: ["*"]):
            assert model_policy.is_allowed("nvidia-nemotron-super")
            assert not model_policy.is_allowed("groq-llama-3.3-70b")

    def test_response_substitution_is_loud(self, caplog):
        """Server-side failover to an unlisted route must not pass silently."""
        model_policy.check_response("nemotron-omni", "groq-llama-3.3-70b")
        assert "MODEL SUBSTITUTION" in caplog.text

    def test_response_substitution_can_be_fatal(self, monkeypatch):
        monkeypatch.setenv("LLM_STRICT_MODEL", "1")
        with pytest.raises(model_policy.ModelNotAllowed):
            model_policy.check_response("nemotron-omni", "groq-llama-3.3-70b")

    def test_matching_response_is_quiet(self, caplog):
        model_policy.check_response("nvidia-nemotron-super", "nvidia-nemotron-super")
        assert "SUBSTITUTION" not in caplog.text

    def test_service_refuses_denied_model_before_calling(self, monkeypatch):
        monkeypatch.setenv("LLM_BASE_URL", "http://gateway.invalid")
        with pytest.raises(model_policy.ModelNotAllowed):
            LLMService(model="groq-llama-3.3-70b")


class TestNoSilentFallback:
    """The regression that motivated plans/08: a dead LLM used to yield the
    string "[S1] This is a fallback, error generating script" and a
    *successful* run, which then spent GPU time rendering it."""

    def test_fallback_helper_is_gone(self):
        assert not hasattr(LLMService, "_generate_fallback_content")

    def test_generate_content_raises_when_all_models_fail(self, monkeypatch):
        monkeypatch.setenv("LLM_BASE_URL", "http://gateway.invalid")
        service = LLMService(model="nvidia-nemotron-super")
        with mock.patch.object(service, "_call", side_effect=RuntimeError("boom")):
            with pytest.raises(LLMError, match="all models failed"):
                service.generate_content("hello")

    def test_no_llm_configured_raises(self, monkeypatch):
        monkeypatch.delenv("LLM_BASE_URL", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        with pytest.raises(LLMError, match="No LLM configured"):
            LLMService(model="nvidia-nemotron-super")

    def test_script_generation_raises_rather_than_returning_placeholder(self):
        with mock.patch(
            "hnfm.content.llm_service.LLMService.generate_structured",
            side_effect=LLMError("gateway down"),
        ):
            with pytest.raises(RuntimeError, match="Failed to generate script"):
                segment_utils.generate_script("content", "summary")


class TestStrictSchema:
    def test_all_properties_required_and_closed(self):
        schema = to_strict_schema(TriageScore)
        assert schema["additionalProperties"] is False
        assert set(schema["required"]) == set(schema["properties"])

    def test_nested_definitions_tightened(self):
        schema = to_strict_schema(Script)
        section = schema["$defs"]["ScriptSection"]
        assert section["additionalProperties"] is False
        assert set(section["required"]) == set(section["properties"])

    def test_optional_fields_stay_expressible(self):
        """Optionals must be required-but-nullable, not dropped."""
        from ..content.llm_schemas import MediaPlanEntry

        entry = to_strict_schema(MediaPlanEntry)
        assert "recipe" in entry["required"]
        assert "null" in str(entry["properties"]["recipe"])

    def test_structured_retries_on_validation_error(self, monkeypatch):
        monkeypatch.setenv("LLM_BASE_URL", "http://gateway.invalid")

        class Tiny(BaseModel):
            n: int

        service = LLMService(model="nvidia-nemotron-super")
        replies = ['{"n": "not a number"}', '{"n": 7}']
        with mock.patch.object(service, "_call", side_effect=replies) as call:
            assert service.generate_structured("go", Tiny).n == 7
        assert call.call_count == 2
        # The retry must tell the model what was wrong.
        assert "did not match the required schema" in call.call_args[0][1]


class TestPromptRegistry:
    def test_every_prompt_loads_and_is_versioned(self):
        found = registry().list_prompts()
        assert found, "no prompts found on disk"
        for name, version in found.items():
            assert version != "?", f"{name} has no version"
            registry().load(name)

    def test_render_carries_provenance(self):
        rendered = registry().render("summary.write", text="an article about badgers")
        assert rendered.name == "summary.write"
        assert rendered.version
        assert "badgers" in rendered.text

    def test_missing_variable_raises_rather_than_leaking_placeholder(self):
        with pytest.raises(KeyError):
            registry().render("summary.write")

    def test_unknown_prompt_raises(self):
        with pytest.raises(PromptNotFound):
            PromptRegistry().load("no.such.prompt")

    def test_prompt_version_reaches_the_step_record(self):
        """What makes plan 14's evals able to attribute a score change."""
        from ..db import steps

        recorded = {}
        with mock.patch.object(
            steps, "record_llm", side_effect=lambda **kw: recorded.update(kw)
        ):
            service = LLMService.__new__(LLMService)  # no network, no config
            response = mock.Mock(
                usage=mock.Mock(prompt_tokens=10, completion_tokens=20)
            )
            service._record_usage(
                response,
                "nvidia-nemotron-super",
                registry().render("summary.write", text="x"),
            )
        assert recorded["prompt_name"] == "summary.write"
        assert recorded["prompt_version"]
        assert recorded["model"] == "nvidia-nemotron-super"


def _segment(script="", script_json=None) -> Segment:
    return Segment(
        key="k",
        item_id=1,
        run=1,
        seg=1,
        created_at=datetime.utcnow(),
        processed_run_key="pr",
        script=script,
        script_json=script_json,
    )


class TestSectionBoundaries:
    def _script(self):
        return Script(
            title="T",
            sections=[
                ScriptSection(
                    index=1,
                    speaker="S1",
                    beat="cold_open",
                    text="One.",
                    visual_intent="a lit window",
                ),
                ScriptSection(
                    index=2,
                    speaker="S1",
                    beat="detail",
                    text="Two.",
                    visual_intent="a screenshot of a website",
                ),
                ScriptSection(
                    index=3,
                    speaker="S2",
                    beat="close",
                    text="Three.",
                    visual_intent="a closing door",
                ),
            ],
        )

    def test_structured_script_drives_sections(self):
        segment = _segment(script="ignored", script_json=self._script().model_dump())
        assert segment_utils.sections_for_segment(segment) == [
            "[S1] One.",
            "[S1] Two.",
            "[S2] Three.",
        ]

    def test_legacy_segment_falls_back_to_line_pairs(self):
        """Segments written before plans/08 have no script_json and must keep
        working unchanged."""
        segment = _segment(script="[S1] a\n[S2] b\n[S1] c\n[S2] d")
        assert segment_utils.sections_for_segment(segment) == [
            "[S1] a\n[S2] b",
            "[S1] c\n[S2] d",
        ]

    def test_malformed_script_json_falls_back(self):
        segment = _segment(script="[S1] a\n[S2] b", script_json={"garbage": True})
        assert segment_utils.sections_for_segment(segment) == ["[S1] a\n[S2] b"]

    def test_undepictable_visual_intent_is_dropped(self):
        """A screenshot intent is worse than none: it steers the art director
        toward something the image model cannot draw."""
        segment = _segment(script="x", script_json=self._script().model_dump())
        assert segment_utils.visual_intents_for_segment(segment) == [
            "a lit window",
            "",
            "a closing door",
        ]

    def test_legacy_segment_intents_align_with_sections(self):
        segment = _segment(script="[S1] a\n[S2] b\n[S1] c\n[S2] d")
        assert len(segment_utils.visual_intents_for_segment(segment)) == len(
            segment_utils.sections_for_segment(segment)
        )


class TestScriptHygiene:
    def test_beats_normalized(self):
        """The enum can't express "exactly one close, and it's last" — a live
        run produced three, two of them mid-script."""
        script = Script(
            title="T",
            sections=[
                ScriptSection(
                    index=1, speaker="S1", beat="detail", text="a", visual_intent="x"
                ),
                ScriptSection(
                    index=2, speaker="S2", beat="close", text="b", visual_intent="x"
                ),
                ScriptSection(
                    index=3, speaker="S1", beat="detail", text="c", visual_intent="x"
                ),
            ],
        )
        segment_utils._normalize_beats(script)
        assert [s.beat for s in script.sections] == ["cold_open", "detail", "close"]

    def test_markdown_stripped_for_tts(self):
        """`**` is narrated as "asterisk asterisk"; a live run emitted
        `**[S1]**`, which also broke the speaker-tag parser."""
        cleaned = segment_utils._clean_script_for_tts("**bold** and # header")
        assert "*" not in cleaned and "#" not in cleaned

    def test_quality_flags_detect_gap_narration(self):
        script = Script(
            title="T",
            sections=[
                ScriptSection(
                    index=1,
                    speaker="S1",
                    beat="cold_open",
                    text="The institution is not disclosed.",
                    visual_intent="a bench",
                ),
                ScriptSection(
                    index=2,
                    speaker="S2",
                    beat="close",
                    text="Fine.",
                    visual_intent="a door",
                ),
            ],
        )
        flags = {f["flag"] for f in segment_utils.script_quality_flags(script)}
        assert "gap_narration" in flags

    def test_quality_flags_detect_strict_alternation(self):
        script = Script(
            title="T",
            sections=[
                ScriptSection(
                    index=i,
                    speaker="S1" if i % 2 else "S2",
                    beat="detail",
                    text=f"line {i}",
                    visual_intent="a bench",
                )
                for i in range(1, 8)
            ],
        )
        found = {
            f["flag"]: f for f in segment_utils.script_quality_flags(script)
        }
        # Renamed from `strict_alternation`: the flag is now a measured switch
        # rate rather than an all-or-nothing check, because the all-or-nothing
        # version missed the 97%-ping-pong scripts the corpus is full of.
        assert "speaker_ping_pong" in found
        assert found["speaker_ping_pong"]["switch_rate"] == 1.0

    def test_clean_script_passes_quality_flags(self):
        script = Script(
            title="T",
            sections=[
                ScriptSection(
                    index=1,
                    speaker="S1",
                    beat="cold_open",
                    text="A surprising fact.",
                    visual_intent="a lit window",
                ),
                ScriptSection(
                    index=2,
                    speaker="S1",
                    beat="detail",
                    text="Here is why.",
                    visual_intent="hands on a lathe",
                ),
                ScriptSection(
                    index=3,
                    speaker="S2",
                    beat="close",
                    text="That is the story.",
                    visual_intent="a closing door",
                ),
            ],
        )
        assert segment_utils.script_quality_flags(script) == []
