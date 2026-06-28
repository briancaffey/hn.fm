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

# The taste rubric — in the user's own framing. Drives both planning and critique.
TASTE = (
    "Great videos here are INTERESTING, EDUCATIONAL, FUNNY, UNEXPECTED, and cool "
    "in an original way. Avoid monotony and avoid generic 'AI slop' structure. "
    "Most sections should be dynamic image sequences (the visual default). "
    "Sprinkle in at most a couple of LTX 'video' moments (a single strong visual "
    "that benefits from motion) and at most a couple of HyperFrames 'hyperframe' "
    "clips (when a section presents STRUCTURED info worth rendering as beautiful "
    "kinetic text: key points, a striking number, a quote, or an A-vs-B compare). "
    "Never put two non-image_sequence clips back to back. Surprise the viewer; "
    "don't repeat the same device."
)

PLAN_SYSTEM = (
    "You are the director of a short AI-generated video about a tech story. For "
    "each narration section, choose how to present it.\n\n" + TASTE + "\n\n"
    "Templates:\n"
    "- image_sequence: evolving generated images (the default, most sections).\n"
    "- video: an LTX motion clip from the section's image (a hero visual moment).\n"
    "- hyperframe: a HyperFrames kinetic-text clip. Pick a recipe and write its "
    "content:\n"
    "    keypoints {kicker, title, points:[2-4 short phrases]}\n"
    "    bigstat   {stat, label, sub?}  (only if the section has a real number)\n"
    "    quote     {quote, attribution?}\n"
    "    compare   {title?, left:{label,text}, right:{label,text}}\n\n"
    "Return ONLY JSON: a list with one object per section, in order:\n"
    '[{"index":1,"template":"image_sequence","why":"..."},'
    '{"index":2,"template":"hyperframe","recipe":"keypoints",'
    '"content":{"kicker":"...","title":"...","points":["...","..."]},"why":"..."}]\n'
    "Keep hyperframe text tight and punchy (it must read in ~2s)."
)


def _llm():
    from .llm_service import LLMService
    return LLMService()


def _parse_json_list(text: str):
    if not text:
        return None
    m = re.search(r"\[.*\]", text, re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except Exception:
        return None


def _llm_plan(sections, summary, theme_name, source_images):
    listing = "\n".join(f"{i + 1}: {s[:200]}" for i, s in enumerate(sections))
    src = ""
    if source_images:
        src = "\n\nReal source images available (you may reference them):\n" + "\n".join(
            f"- {im.get('description') or im.get('alt')}" for im in source_images[:6]
        )
    user = (
        f"Theme: {theme_name}\nStory summary: {summary[:600]}\n\n"
        f"Sections ({len(sections)}):\n{listing}{src}\n\n"
        f"Plan every section. JSON only."
    )
    # Retry — nemotron occasionally returns nothing/unparseable; a bad plan would
    # silently collapse every section to the default.
    for attempt in range(int(os.getenv("META_PLAN_RETRIES", "2")) + 1):
        try:
            out = _llm().generate_content(PLAN_SYSTEM + "\n\n" + user)
            plan = _parse_json_list(out)
            if plan:
                return plan
            logger.warning(f"meta plan attempt {attempt + 1}: unparseable")
        except Exception as e:
            logger.warning(f"meta plan attempt {attempt + 1} failed: {e}")
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
    compact = [{"index": p["index"], "template": p["template"]} for p in plan]
    prompt = (
        "Critique this video plan for taste. " + TASTE + "\n\n"
        f"Plan: {json.dumps(compact)}\n\n"
        "Score it 1-10 for overall interest/originality and flag problems "
        "(repetitive, chaotic, boring, or a special clip wasted on a weak section). "
        'Return ONLY JSON: {"score":N,"issues":["..."],"suggest":["index->template", ...]}'
    )
    try:
        out = _llm().generate_content(prompt) or ""
        m = re.search(r"\{.*\}", out, re.S)
        verdict = json.loads(m.group(0)) if m else {}
        score = verdict.get("score")
        issues = verdict.get("issues") or []
        logger.info(f"🎬 meta-plan critic score={score} issues={issues[:3]}")
        # Apply simple template suggestions (e.g. "3->image_sequence")
        for s in (verdict.get("suggest") or []):
            mm = re.match(r"\s*(\d+)\s*->\s*(\w+)", str(s))
            if not mm:
                continue
            idx, t = int(mm.group(1)), mm.group(2)
            if t in TEMPLATES and 1 <= idx <= len(plan):
                plan[idx - 1]["template"] = t
                if t != "hyperframe":
                    plan[idx - 1].pop("recipe", None)
                    plan[idx - 1].pop("content", None)
    except Exception as e:
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
