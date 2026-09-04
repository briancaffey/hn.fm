"""Story triage: score a processed run's suitability for an engaging video.

Runs on the cheap text half of the pipeline (scrape + summary already done),
so every candidate story can be scored before any GPU time is spent. The
rubric and interest profile live in config.yaml (`triage:`) — data, not code.

Models: free LiteLLM routes only. Primary + fallback are configured; the
env var TRIAGE_LLM_MODEL overrides the primary.
"""

import logging
import math
import os
from typing import Optional

logger = logging.getLogger(__name__)

VERDICTS = ("great", "good", "marginal", "unsuitable")

# Deterministic hard flags (found before/without the LLM)
FLAG_SCRAPE_FALLBACK = "scrape_fallback"
FLAG_TOO_SHORT = "too_short"

# The prompt lives in prompts/triage.score.yaml and the response shape is
# enforced by llm_schemas.TriageScore — the old hand-rolled `_extract_json`
# brace-matcher and its silent None path are gone (plans/08).
PROMPT_NAME = "triage.score"


def _triage_config() -> dict:
    from ..utils.config import config_manager

    return config_manager.get("triage", {}) or {}


def primary_model() -> str:
    return os.getenv("TRIAGE_LLM_MODEL") or _triage_config().get(
        "model", "nvidia-nemotron-super"
    )


_VERDICT_DEFAULTS = {
    "unsuitable_producibility": 20,
    "unsuitable_interest": 15,
    "great_interest": 80,
    "great_producibility": 75,
    "good_interest": 60,
    "good_producibility": 50,
}


def verdict_thresholds() -> dict:
    cfg = _triage_config().get("verdict_thresholds") or {}
    return {**_VERDICT_DEFAULTS, **{k: int(v) for k, v in cfg.items()}}


def derive_verdict(interest: int, producibility: int) -> str:
    """Bucket the two axes into a verdict.

    The model used to return the verdict itself, and barely discriminated:
    33% "great", 2.3% "unsuitable". A story that scraped 43 characters of an
    HTTP error page came back "marginal" — enough to earn it a Story Brief.
    The model is good at judging the two axes and bad at bucketing them, so
    the split is now explicit: it judges, this categorises.

    Deterministic bucketing also means the verdict is stable across re-runs
    and tunable in config without touching the prompt.
    """
    t = verdict_thresholds()
    # Legacy rows predate two-axis scoring and carry NULL axes. Treating a
    # missing score as 0 is the safe reading: we cannot claim a story is
    # producible on evidence we do not have.
    interest = int(interest or 0)
    producibility = int(producibility or 0)
    if (
        producibility <= t["unsuitable_producibility"]
        or interest <= t["unsuitable_interest"]
    ):
        return "unsuitable"
    if interest >= t["great_interest"] and producibility >= t["great_producibility"]:
        return "great"
    if interest >= t["good_interest"] and producibility >= t["good_producibility"]:
        return "good"
    return "marginal"


def brief_min_rank() -> float:
    """Minimum rank_score for a story to earn a Story Brief.

    The old gate was `verdict != "unsuitable"`, which skipped 3 of 132 scored
    stories — 98% paid for two LLM calls and ~30s, the largest single cost in
    ingest, for a brief nothing downstream would read.
    """
    return float(_triage_config().get("brief_min_rank", 60))


def deserves_brief(score: dict) -> bool:
    """Is this story worth the two LLM calls a Story Brief costs?

    Rank rather than verdict, because the two disagree badly: an "unsuitable"
    story has scored 84.9 while "marginal" ones reach 121. `unsuitable` is
    still an absolute veto — when the model is confident there is nothing
    there, a high rank does not rescue it.
    """
    verdict = score.get("verdict")
    if verdict == "unsuitable":
        return False
    # A story the axes call `great` or `good` gets a brief regardless of rank.
    # rank_score folds in HN score and topic match, so a genuinely producible
    # story on an unfashionable topic can rank below the cutoff — and refusing
    # it a brief while calling it "good" is incoherent, and leaves the digest
    # skipping stories it wanted.
    if verdict in ("great", "good"):
        return True
    return float(score.get("rank_score") or 0) >= brief_min_rank()


def fallback_model() -> Optional[str]:
    return _triage_config().get("fallback_model", "openrouter-nemotron-ultra")


def _clamp(data: dict) -> dict:
    """Bound list lengths and string sizes before they reach the queue.

    The schema guarantees types, ranges and the verdict enum; it cannot cap how
    many topics an enthusiastic model returns, and the triage UI renders these
    as chips.
    """
    return {
        "interest": data["interest"],
        "producibility": data["producibility"],
        "verdict": data["verdict"],
        "reasons": [str(r)[:300] for r in data["reasons"]][:5],
        "flags": [str(f)[:60] for f in data["flags"]][:10],
        "topics": [str(t).lower()[:60] for t in data["topics"]][:8],
        "visual_potential": data["visual_potential"],
        "narrative_potential": data["narrative_potential"],
    }


def score_content(title: str, summary: str, content_clean: str,
                  hn_score: int = 0, comments: int = 0,
                  signals: Optional[dict] = None) -> dict:
    """Two-axis score (interest x producibility), schema-enforced.

    `signals` is the deterministic retrieval report from `scrape_signals`. It
    is shown to the model AND used to cap `producibility` afterwards — the cap
    is what stops a 214-character stub scoring well because its headline
    sounds exciting.

    Raises RuntimeError if no model produces a valid score — a triage score
    that silently defaulted to "marginal" would quietly mis-rank the queue.
    """
    from . import scrape_signals as _sig
    from .llm_service import LLMService, LLMError
    from .llm_schemas import TriageScore
    from .prompts import render

    cfg = _triage_config()
    prompt = render(
        PROMPT_NAME,
        rubric=(cfg.get("rubric") or "Favor engaging, visual, comprehensible stories."),
        title=title or "(untitled)",
        hn_score=hn_score or 0,
        comments=comments or 0,
        summary=(summary or "")[:2000],
        excerpt=(content_clean or "")[:3000],
        signals=_sig.summarize(signals) if signals else "no retrieval report available",
    )

    model = primary_model()
    service = LLMService(model=model, task=PROMPT_NAME)
    # config profiles carry the fallback, but an explicit TRIAGE_LLM_MODEL
    # override must still get the configured fallback behind it.
    service.fallback_model = service.fallback_model or fallback_model()

    try:
        scored = service.generate_structured(prompt, TriageScore)
    except LLMError as e:
        raise RuntimeError(f"triage scoring failed: {e}") from e

    result = _clamp(scored.model_dump())
    result["model"] = service.model

    # Deterministic ceiling wins over the model's optimism. The signals are
    # ground truth about what we hold; the score is an opinion about it.
    ceiling = _sig.producibility_ceiling(signals or {})
    if ceiling is not None and result["producibility"] > ceiling:
        logger.info(
            f"producibility {result['producibility']} -> {ceiling} "
            f"(capped by retrieval signals)"
        )
        result["producibility"] = ceiling

    # Derived from the axes, not taken from the model — see derive_verdict.
    # Kept for comparison so a drifting model stays visible.
    result["model_verdict"] = result["verdict"]
    result["verdict"] = derive_verdict(
        result["interest"], result["producibility"]
    )
    if result["verdict"] != result["model_verdict"]:
        logger.info(
            f"verdict {result['model_verdict']} -> {result['verdict']} "
            f"(derived from interest={result['interest']}, "
            f"producibility={result['producibility']})"
        )
    return result


def interest_match(topics: list, title: str = "") -> float:
    """Weighted overlap between story topics and the configured interest
    profile, squashed to [-1, 1]."""
    profile = _triage_config().get("interest_profile") or {}
    if not profile:
        return 0.0
    haystacks = [t.lower() for t in (topics or [])] + [(title or "").lower()]
    total = 0.0
    for keyword, weight in profile.items():
        kw = str(keyword).lower()
        if any(kw in h for h in haystacks):
            total += float(weight)
    return math.tanh(total / 3.0)


def rank_score(interest: int, interest_match: float, hn_score: int,
               producibility: int = 100) -> float:
    """Blend both axes into one queue order.

    `producibility` enters as a MULTIPLIER, not another additive term: a story
    we cannot actually build should sink regardless of how well it scores
    elsewhere, and an additive weight lets a high interest score paper over an
    unusable scrape. `interest_match` is the topic-profile overlap in [-1, 1].
    """
    weights = _triage_config().get("weights") or {}
    w_int = float(weights.get("interest", 1.0))
    w_profile = float(weights.get("interest_match", 0.6))
    w_hn = float(weights.get("hn_score", 0.4))
    floor = float(weights.get("producibility_floor", 0.15))

    base = (
        w_int * interest
        + w_profile * interest_match * 100.0
        + w_hn * math.log10((hn_score or 0) + 1) * 25.0
    )
    # Scaled to [floor, 1] so an unbuildable story sinks but never vanishes —
    # Brian's standing position is that this is ordering, not censorship.
    multiplier = floor + (1.0 - floor) * (max(0, min(100, producibility)) / 100.0)
    return round(base * multiplier, 2)


NEEDS_BETTER_SOURCE = "needs_better_source"


def bucket(interest: int, producibility: int) -> Optional[str]:
    """The "worth it, needs a better source" bucket (plans/09).

    A high-interest / low-producibility story is a fix-the-scrape signal, not a
    reject: re-run it against a better source and it may be a great video.
    """
    thresholds = _triage_config().get("buckets") or {}
    min_interest = int(thresholds.get("needs_source_min_interest", 65))
    max_prod = int(thresholds.get("needs_source_max_producibility", 45))
    if interest >= min_interest and producibility <= max_prod:
        return NEEDS_BETTER_SOURCE
    return None


def hard_flags(content_clean: str, scrape_fallback: bool) -> list:
    flags = []
    if scrape_fallback:
        flags.append(FLAG_SCRAPE_FALLBACK)
    if len(content_clean or "") < 400:
        flags.append(FLAG_TOO_SHORT)
    return flags
