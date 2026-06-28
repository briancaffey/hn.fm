"""Vision-driven image-sequence planner.

The old approach cycled a fixed list of directives ("camera push-in", "lighting
shifts warmer"…) — so every sequence looked the same (the classic
normal→blurry→sunset). This instead does what inference-club-studio's SEQ.md does:
look at the ACTUAL root frame with Nemotron vision and plan a short progression of
image-to-image edits that MEANINGFULLY ADVANCE the content — pose, action, new
elements, camera, the moment unfolding — each frame continuing from the last, so a
sequence feels like a living moment rather than a filter swap.

`plan_sequence_edits` returns one edit instruction per follow-on frame. Primary
path is the vision call; the fallback is still varied (seeded per section) so two
sections never get the identical recipe.
"""

import os
import re
import json
import base64
import logging

logger = logging.getLogger(__name__)

# Content-oriented fallbacks (NOT lighting). Selected with a per-section offset so
# different sections get different progressions even when vision is unavailable.
_FALLBACK = [
    "the main subject shifts pose and turns toward a new focal point in the scene",
    "a new relevant object enters the frame and becomes the center of attention",
    "the camera pushes to a tighter angle, isolating a key detail up close",
    "the moment advances — the subject's action progresses to its next beat",
    "pull back to reveal more of the surroundings and the wider context",
    "a second figure or element appears and interacts with the main subject",
    "the composition reframes from a bold new angle, emphasizing movement",
    "the subject reacts — expression, gesture and posture visibly change",
    "the scene transforms as the central idea takes a more dramatic form",
    "focus shifts to the background, where something new is happening",
]

VISION_SYSTEM = (
    "You are a film director planning a short visual sequence. You are shown the "
    "OPENING frame and the line it illustrates. Plan the next frames as image-to-"
    "image edits that each CONTINUE from the previous frame (same place, subjects "
    "and style) but MEANINGFULLY ADVANCE the moment: change the subject's pose or "
    "action, move or introduce objects, shift the camera angle or distance, reveal "
    "more of the scene, or progress time. Make it feel like a living moment "
    "unfolding — like frames of a real video. Do NOT merely change lighting, color "
    "or focus; that is forbidden as the main change. Keep continuity and the same "
    "visual style. Return ONLY a JSON array of concise edit instructions (one per "
    "frame), each describing the NEW state of that frame."
)


def _fallback(n_edits, seed):
    off = seed % len(_FALLBACK)
    return [_FALLBACK[(off + i) % len(_FALLBACK)] for i in range(n_edits)]


def plan_sequence_edits(root_image_path, section_text, theme_name, n_edits, seed=0):
    """Return up to `n_edits` content-evolving image-to-image instructions."""
    if n_edits <= 0:
        return []
    base = os.getenv("LLM_BASE_URL")
    if not base or not os.path.exists(root_image_path):
        return _fallback(n_edits, seed)
    if not base.endswith("/v1"):
        base = base.rstrip("/") + "/v1"
    try:
        import openai
        from ..utils import metrics

        client = openai.OpenAI(base_url=base, api_key=os.getenv("OPENAI_API_KEY") or "x")
        b64 = base64.b64encode(open(root_image_path, "rb").read()).decode()
        user = (
            f"The line: \"{section_text[:240]}\".\n"
            f"Plan exactly {n_edits} follow-on frames in the {theme_name} style. "
            f"JSON array of {n_edits} strings only."
        )
        r = client.chat.completions.create(
            model=os.getenv("LLM_MODEL", "nemotron-omni"),
            messages=[{"role": "user", "content": [
                {"type": "text", "text": VISION_SYSTEM + "\n\n" + user},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
            ]}],
            max_tokens=500,
            temperature=float(os.getenv("SEQ_TEMPERATURE", "0.85")),
            extra_body={"chat_template_kwargs": {"enable_thinking": False}},
        )
        try:
            u = getattr(r, "usage", None)
            if u:
                metrics.record_tokens(getattr(u, "prompt_tokens", 0), getattr(u, "completion_tokens", 0))
        except Exception:
            pass
        msg = r.choices[0].message
        text = (msg.content or getattr(msg, "reasoning_content", "") or "").strip()
        m = re.search(r"\[.*\]", text, re.S)
        if m:
            arr = json.loads(m.group(0))
            edits = [str(x).strip() for x in arr if str(x).strip()]
            if edits:
                # right-size to n_edits (pad from fallback if the model gave fewer)
                if len(edits) < n_edits:
                    edits += _fallback(n_edits - len(edits), seed + 7)
                return edits[:n_edits]
        logger.warning("seq planner: unparseable vision plan, using fallback")
    except Exception as e:
        logger.warning(f"seq planner vision failed (non-fatal): {e}")
    return _fallback(n_edits, seed)
