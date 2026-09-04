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


class Tags(BaseModel):
    """Article tags. Schema-enforced because the free-text version failed on
    real output with "Could not parse tags as JSON array" and fell back to the
    default silently."""

    tags: List[str] = Field(
        min_length=2,
        max_length=6,
        description="2-6 lowercase alphanumeric tags, single words or acronyms.",
    )


class Emoji(BaseModel):
    """Exactly four emoji describing the article."""

    emoji: List[str] = Field(min_length=4, max_length=4)


class TriageScore(BaseModel):
    """Two axes, not one (plans/09).

    `suitability` used to blend "is this interesting?" with "can we make
    something of it?" — and those come apart constantly: a fascinating
    paywalled story scored low for the wrong reason, a thin but well-scraped
    post scored high for the wrong reason. Splitting them also yields a
    "worth it, needs a better source" bucket, which is a fix-the-scrape signal
    rather than a reject.
    """

    interest: int = Field(
        ge=0, le=100,
        description="Is this intrinsically worth an audience's attention?",
    )
    producibility: int = Field(
        ge=0, le=100,
        description="Given what we RETRIEVED, can we build a good video?",
    )
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


# ---------------------------------------------------------------------------
# Story Brief (content/story_brief.py) — plans/09
# ---------------------------------------------------------------------------

# The brief is the cheap half's output artifact and the input to the script
# room (plan 11) and the art direction (plans 12/13). Before it, the script
# prompt got `content_clean` + `summary` and the image prompt got
# `run_summary` + one line — neither had the whole picture.


class KeyFact(BaseModel):
    claim: str = Field(description="The fact, stated plainly in our own words.")
    source: Literal["article", "comment"]
    quote: str = Field(description="Verbatim span from the source supporting it.")
    # Populated by plan 10 for comment-sourced facts; empty string for article.
    hn_user: str = ""
    comment_id: int = 0


class Entity(BaseModel):
    name: str
    kind: Literal["person", "org", "product", "place", "technology"]
    role: str = Field(description="What this entity does in THIS story.")


class Number(BaseModel):
    # Two forms because the brief now feeds two very different outputs. The
    # narrator needs "forty percent"; the Kindle page needs "40%". Writing one
    # and deriving the other is lossy in both directions, so ask for both.
    value: str = Field(description='As WRITTEN, e.g. "40%", "1,208", "$2.3M".')
    spoken: str = Field(description='As SPOKEN aloud, e.g. "forty percent".')
    of: str = Field(description="What the number measures.")
    context: str = Field(description="What makes it meaningful.")


class CommentInsight(BaseModel):
    """A point worth carrying from the Hacker News discussion.

    `comment_id` is required and checked against the ids actually retrieved —
    the whole reason the thread is now fetched rather than summarised from a
    count. See content/comments.verify_comment_facts.
    """

    comment_id: int = Field(description="The id of the comment, exactly as given.")
    author: str = Field(description="The commenter's username.")
    insight: str = Field(description="The point, in your own words, one sentence.")
    quote: str = Field(description="A verbatim span from that comment.")
    kind: Literal["correction", "context", "expertise", "dissent", "anecdote"] = Field(
        description="What this contributes that the article does not."
    )


class StoryFraming(BaseModel):
    """The editorial half of the brief: what this story IS."""

    thesis: str = Field(description="One sentence: what this story actually is.")
    why_now: str = Field(description="Why it is on the front page today.")
    stakes: str = Field(description="Who is affected, and how much.")
    angle: str = Field(
        description="The framing that makes this a video rather than a summary."
    )
    tension: str = Field(description="The disagreement, risk, or open question.")
    visual_affordances: List[str] = Field(
        description="Things in this story that can literally be SHOWN."
    )
    unknowns: List[str] = Field(
        description=(
            "What the source does NOT establish. Load-bearing: the script "
            "fact-checker uses this to refuse to let the writer invent."
        )
    )


class StoryEvidence(BaseModel):
    """The extractive half of the brief: what the source actually says."""

    key_facts: List[KeyFact]
    entities: List[Entity]
    numbers: List[Number]


class DiscussionEvidence(BaseModel):
    """What the thread adds. Extracted separately from the article evidence so
    a story with a rich discussion and a thin article still yields something."""

    comment_insights: List[CommentInsight]


class StoryBrief(BaseModel):
    """Framing + evidence + scores. Assembled from two LLM calls; see
    `content/story_brief.py` for why it is not requested in one."""

    thesis: str
    why_now: str
    stakes: str
    angle: str
    tension: str
    visual_affordances: List[str]
    unknowns: List[str]
    key_facts: List[KeyFact]
    entities: List[Entity]
    numbers: List[Number]
    comment_insights: List[dict] = Field(default_factory=list)
