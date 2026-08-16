"""Agentic meta-sequencer — the 'director' that decides, per section, HOW to
tell it: a dynamic image sequence, an LTX motion clip, or a HyperFrames
structured-text clip. Balanced + critic:

  1. PLAN   — an LLM assigns each section a template (+ recipe/content for
              hyperframes), choosing from generated and source images.
  2. GUARD  — deterministic guardrails enforce variety (no two special clips
              back-to-back, sane caps, image-sequence stays the default).
  3. CRITIC — a second LLM pass scores the plan on the taste rubric
              (interesting / educational / funny / unexpected / original) and
              revises weak or repetitive spots.

The output is a list of per-section plans the pipeline executes. The rubric is
seeded from the user's own words; tune it on real outputs.
"""

import os
import json
import logging
import re

logger = logging.getLogger(__name__)

TEMPLATES = ("image_sequence", "video", "hyperframe")
HYPERFRAME_RECIPES = ("keypoints", "bigstat", "quote", "compare")

# Prompts live in prompts/media_plan.*.yaml; shapes are enforced by
# llm_schemas.MediaPlan / CriticVerdict (plans/08).
PLAN_PROMPT = "media_plan.plan"
CRITIC_PROMPT = "media_plan.critic"

# The taste rubric and the director's instructions now live in
# prompts/media_plan.plan.yaml and prompts/media_plan.critic.yaml, versioned
# alongside every other prompt (plans/08). They were duplicated here as module
# constants; keeping both copies guaranteed they would drift.


def _llm(task):
    from .llm_service import LLMService

    return LLMService(task=task)


def _llm_plan(sections, summary, theme_name, source_images):
    from .llm_schemas import MediaPlan
    from .prompts import render

    listing = "\n".join(f"{i + 1}: {s[:200]}" for i, s in enumerate(sections))
    src = ""
    if source_images:
        src = "\n\nReal source images available (you may reference them):\n" + "\n".join(
            f"- {im.get('description') or im.get('alt')}" for im in source_images[:6]
        )
    prompt = render(
        PLAN_PROMPT,
        theme_name=theme_name,
        summary=summary[:600],
        n_sections=len(sections),
        listing=listing,
        source_images=src,
    )
    try:
        plan = _llm(PLAN_PROMPT).generate_structured(
            prompt,
            MediaPlan,
            max_attempts=int(os.getenv("META_PLAN_RETRIES", "2")) + 1,
        )
        return [entry.model_dump() for entry in plan.plan]
    except Exception as e:
        # Non-fatal by design: a missing plan falls through to the deterministic
        # fallback below, which still yields a watchable (if plainer) video.
        logger.warning(f"meta plan failed, using deterministic fallback: {e}")
        return None


def _apply_guardrails(plan, n_sections, max_video=2, max_hyper=2):
    """Enforce variety: valid templates, caps, no two special clips adjacent,
    image_sequence as the default. Mutates a normalized copy."""
    # normalize to one entry per section
    by_idx = {}
    for p in (plan or []):
        try:
            by_idx[int(p.get("index"))] = p
        except Exception:
            continue
    out = []
    n_video = n_hyper = 0
    prev_special = False
    for i in range(1, n_sections + 1):
        p = by_idx.get(i, {}) or {}
        t = p.get("template") if p.get("template") in TEMPLATES else "image_sequence"
        # cap + no-adjacent-special
        if t == "video":
            if prev_special or n_video >= max_video:
                t = "image_sequence"
        elif t == "hyperframe":
            recipe = p.get("recipe") if p.get("recipe") in HYPERFRAME_RECIPES else "keypoints"
            content = p.get("content") or {}
            if prev_special or n_hyper >= max_hyper or not content:
                t = "image_sequence"
        entry = {"index": i, "template": t, "why": p.get("why", "")}
        if t == "hyperframe":
            entry["recipe"] = p.get("recipe") if p.get("recipe") in HYPERFRAME_RECIPES else "keypoints"
            entry["content"] = p.get("content") or {}
            n_hyper += 1
        elif t == "video":
            n_video += 1
        prev_special = t != "image_sequence"
        out.append(entry)
    return out


def _critic_revise(plan, sections, summary):
    """LLM critic scores the plan and may revise; deterministic guardrails win."""
    from .llm_schemas import CriticVerdict
    from .prompts import render

    compact = [{"index": p["index"], "template": p["template"]} for p in plan]
    prompt = render(CRITIC_PROMPT, plan=json.dumps(compact))
    try:
        verdict = _llm(CRITIC_PROMPT).generate_structured(prompt, CriticVerdict)
        logger.info(
            f"🎬 meta-plan critic score={verdict.score} issues={verdict.issues[:3]}"
        )
        # Apply simple template suggestions (e.g. "3->image_sequence")
        for suggestion in verdict.suggest:
            mm = re.match(r"\s*(\d+)\s*->\s*(\w+)", str(suggestion))
            if not mm:
                continue
            idx, t = int(mm.group(1)), mm.group(2)
            if t in TEMPLATES and 1 <= idx <= len(plan):
                plan[idx - 1]["template"] = t
                if t != "hyperframe":
                    plan[idx - 1].pop("recipe", None)
                    plan[idx - 1].pop("content", None)
    except Exception as e:
        # The plan is already valid and guardrailed; losing the critique costs
        # polish, not correctness.
        logger.warning(f"meta critic skipped: {e}")
    return plan


def _fallback_plan(sections):
    """Deterministic plan when the LLM is unavailable — never all-static.

    Add one LTX 'video' on the wordiest section (most to animate) so a failed
    plan still has variety. Hyperframes need LLM-authored content, so we skip
    them here rather than invent text.
    """
    n = len(sections)
    if n == 0:
        return []
    longest = max(range(n), key=lambda i: len(sections[i].split()))
    plan = [{"index": i + 1, "template": "image_sequence", "why": "fallback"} for i in range(n)]
    if n >= 2:
        plan[longest]["template"] = "video"
    logger.warning(f"meta plan: LLM unavailable → deterministic fallback (video on §{longest+1})")
    return plan


def plan_segment(sections, summary, theme_name, source_images=None,
                 max_video=2, max_hyper=2):
    """Full plan: LLM → guardrails → critic → guardrails again (critic-safe)."""
    raw = _llm_plan(sections, summary, theme_name, source_images)
    if not raw:
        return _apply_guardrails(_fallback_plan(sections), len(sections), max_video, max_hyper)
    plan = _apply_guardrails(raw, len(sections), max_video, max_hyper)
    plan = _critic_revise(plan, sections, summary)
    plan = _apply_guardrails(plan, len(sections), max_video, max_hyper)
    counts = {t: sum(1 for p in plan if p["template"] == t) for t in TEMPLATES}
    logger.info(f"🎬 meta-sequence plan: {counts}")
    return plan
