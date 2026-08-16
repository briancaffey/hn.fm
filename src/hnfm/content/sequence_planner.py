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

PROMPT_NAME = "sequence.plan"


def _fallback(n_edits, seed):
    off = seed % len(_FALLBACK)
    return [_FALLBACK[(off + i) % len(_FALLBACK)] for i in range(n_edits)]


def plan_sequence_edits(root_image_path, section_text, theme_name, n_edits, seed=0):
    """Return up to `n_edits` content-evolving image-to-image instructions.

    Vision-first with a varied deterministic fallback: a missing plan costs
    visual interest, not correctness, so this stays non-fatal by design.
    """
    if n_edits <= 0:
        return []
    if not os.getenv("LLM_BASE_URL") or not os.path.exists(root_image_path):
        return _fallback(n_edits, seed)

    try:
        from .llm_service import LLMService
        from .llm_schemas import SequenceEdits
        from .prompts import render

        prompt = render(
            PROMPT_NAME,
            section_text=section_text[:240],
            n_edits=n_edits,
            theme_name=theme_name,
        )
        b64 = base64.b64encode(open(root_image_path, "rb").read()).decode()

        # The only multimodal call in the pipeline: the image rides alongside
        # the rendered prompt text. It still goes through the shared service so
        # it gets allowlist checks, the task profile and token accounting.
        service = LLMService(task=PROMPT_NAME)
        plan = service.generate_structured_vision(prompt, SequenceEdits, image_b64=b64)
        edits = [e.strip() for e in plan.edits if e and e.strip()]
        if edits:
            # Right-size to n_edits (pad from the fallback if the model gave fewer).
            if len(edits) < n_edits:
                edits += _fallback(n_edits - len(edits), seed + 7)
            return edits[:n_edits]
        logger.warning("seq planner: vision plan was empty, using fallback")
    except Exception as e:
        logger.warning(f"seq planner vision failed (non-fatal): {e}")
    return _fallback(n_edits, seed)
