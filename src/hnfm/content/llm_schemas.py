"""Pydantic schemas for structured LLM output (plans/08-llm-foundation.md).

Every LLM call that returns data (rather than prose) declares its shape here.
Before this, three modules each carried their own tolerant JSON scraper —
`triage._extract_json`, `meta_sequencer._parse_json_list`, and a bare
`re.search(r"\\[.*\\]")` in `sequence_planner` — each with an independent silent
failure path. A malformed response degraded into a default that looked like a
real answer.

`to_strict_schema()` converts these models into the JSON Schema dialect the
OpenAI-compatible `response_format` expects. Verified against the LiteLLM
gateway's `nvidia-nemotron-super` route on 2026-08-16: it returns clean JSON
with no fences or reasoning preamble, and honours enum constraints across
samples at temperature 0.8.
"""

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Strict-schema conversion
# ---------------------------------------------------------------------------


def to_strict_schema(model: type[BaseModel]) -> Dict[str, Any]:
    """Pydantic model -> strict JSON Schema.

    Strict mode requires every property to appear in `required` and every
    object to set `additionalProperties: false`. Pydantic omits fields that
    have defaults, so we walk the tree and tighten it. Optional fields are
    already emitted as `anyOf: [T, null]`, which keeps them expressible.
    """
    schema = model.model_json_schema()
    _tighten(schema)
    for definition in (schema.get("$defs") or {}).values():
        _tighten(definition)
    return schema


def _tighten(node: Any) -> None:
    if not isinstance(node, dict):
        return
    if node.get("type") == "object" and "properties" in node:
        node["additionalProperties"] = False
        node["required"] = list(node["properties"].keys())
        for child in node["properties"].values():
            _tighten(child)
    for key in ("items", "not"):
        if key in node:
            _tighten(node[key])
    for key in ("anyOf", "oneOf", "allOf", "prefixItems"):
        for child in node.get(key) or []:
            _tighten(child)


# ---------------------------------------------------------------------------
# Triage (content/triage.py)
# ---------------------------------------------------------------------------


class TriageScore(BaseModel):
    suitability: int = Field(ge=0, le=100)
    verdict: Literal["great", "good", "marginal", "unsuitable"]
    reasons: List[str]
    flags: List[str]
    topics: List[str]
    visual_potential: int = Field(ge=0, le=10)
    narrative_potential: int = Field(ge=0, le=10)


# ---------------------------------------------------------------------------
# Script (utils/segment_utils.py)
# ---------------------------------------------------------------------------

# A section is the atomic unit of BOTH narration and visuals: one TTS call and
# one image. Letting the writer choose the boundaries is the whole point of the
# structured script — the old `split_script_into_sections` chunked every two
# lines, so visual pacing was set by a line counter.
BeatType = Literal[
    "cold_open",  # the hook; earns the next 30 seconds
    "context",  # what the viewer needs to follow it
    "detail",  # the substance
    "turn",  # the surprise, tension or complication
    "implication",  # why it matters
    "close",  # the landing
]


class ScriptSection(BaseModel):
    index: int = Field(ge=1)
    speaker: Literal["S1", "S2"]
    beat: BeatType
    text: str = Field(description="Spoken words only. No tags, no markdown.")
    visual_intent: str = Field(
        description="What this beat should SHOW — feeds the image prompt."
    )


class Script(BaseModel):
    title: str
    sections: List[ScriptSection]

    def to_tts_sections(self) -> List[str]:
        """`["[S1] ...", "[S2] ..."]` — the exact wire format the rest of the
        pipeline already consumes, so nothing downstream has to change."""
        return [f"[{s.speaker}] {s.text.strip()}" for s in self.sections]

    def to_script_text(self) -> str:
        """The flat script kept on `Segment.script` for the UI, the ASR QA
        comparison, and anything still reading plain text."""
        return "\n".join(self.to_tts_sections())


# ---------------------------------------------------------------------------
# Meta-sequencer (content/meta_sequencer.py)
# ---------------------------------------------------------------------------


class MediaPlanEntry(BaseModel):
    index: int = Field(ge=1)
    template: Literal["image_sequence", "video", "hyperframe"]
    why: str
    recipe: Optional[Literal["keypoints", "bigstat", "quote", "compare"]] = None
    # Free-form: each recipe has a different shape (see prompts/media_plan.plan.yaml).
    content: Optional[Dict[str, Any]] = None


class MediaPlan(BaseModel):
    plan: List[MediaPlanEntry]


class CriticVerdict(BaseModel):
    score: int = Field(ge=1, le=10)
    issues: List[str]
    suggest: List[str] = Field(
        description='Template changes as "index->template", e.g. "3->image_sequence".'
    )


# ---------------------------------------------------------------------------
# Sequence planner (content/sequence_planner.py)
# ---------------------------------------------------------------------------


class SequenceEdits(BaseModel):
    edits: List[str] = Field(
        description="One image-to-image instruction per follow-on frame."
    )
