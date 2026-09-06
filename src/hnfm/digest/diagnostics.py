"""What an edition cost, and where the effort went.

Everything here is read back out of `pipeline_steps`, which already records
model, token counts, llm_calls and duration for every step regardless of which
entry point produced it. Nothing new is instrumented — the trail was always
sufficient, it just had no reader.

The phases are the questions worth answering: is the money going on research,
on writing the edition, or on pictures? In practice the answer surprises
people, which is the point of printing it at the back of the digest.
"""

import logging
from typing import List

logger = logging.getLogger(__name__)

# Which pipeline stages roll up into which reported phase.
PHASE_OF = {
    "scrape": "Retrieval",
    "summary": "Research",
    "enrich": "Research",
    "triage": "Scoring",
    "brief": "Story Briefs",
    "task": "Other",
}


def _phase(stage: str) -> str:
    return PHASE_OF.get((stage or "").lower(), "Other")


def collect(digest, illustrations=None, cover=None, edition_seconds=0.0,
            compose_stats=None) -> dict:
    """A diagnostics block for one edition."""
    from ..db import steps as _steps
    from ..utils.config import config_manager

    item_ids = [s.item_id for s in digest.stories]
    per_phase = {}
    per_story = []
    models = {}

    for story in digest.stories:
        story_tokens = 0
        story_steps = 0
        try:
            rows = _steps.list_steps(story.item_id, story.run)
        except Exception as e:
            logger.debug(f"diagnostics: no steps for {story.item_id} ({e})")
            rows = []
        for r in rows:
            if r.get("status") not in ("ok", "superseded"):
                continue
            ph = _phase(r.get("stage"))
            acc = per_phase.setdefault(
                ph, {"phase": ph, "calls": 0, "tokens_in": 0,
                     "tokens_out": 0, "seconds": 0.0}
            )
            acc["calls"] += int(r.get("llm_calls") or 0)
            acc["tokens_in"] += int(r.get("tokens_in") or 0)
            acc["tokens_out"] += int(r.get("tokens_out") or 0)
            acc["seconds"] += float(r.get("seconds") or 0)
            story_tokens += int(r.get("tokens_in") or 0) + int(r.get("tokens_out") or 0)
            story_steps += 1
            if r.get("model"):
                models.setdefault("Research & scoring", r["model"])
        per_story.append({
            "item_id": story.item_id,
            "title": story.title,
            "tokens": story_tokens,
            "steps": story_steps,
        })

    # Composition is the edition's own prose — teaser, quick hits, feature.
    if compose_stats:
        per_phase["Edition prose"] = {
            "phase": "Edition prose",
            "calls": compose_stats.get("calls", 0),
            "tokens_in": compose_stats.get("tokens_in", 0),
            "tokens_out": compose_stats.get("tokens_out", 0),
            "seconds": compose_stats.get("seconds", 0.0),
        }

    order = ["Retrieval", "Research", "Scoring", "Story Briefs",
             "Edition prose", "Other"]
    phases = [per_phase[k] for k in order if k in per_phase]
    for p in phases:
        p["seconds"] = round(p["seconds"], 1)

    totals = {
        "calls": sum(p["calls"] for p in phases),
        "tokens_in": sum(p["tokens_in"] for p in phases),
        "tokens_out": sum(p["tokens_out"] for p in phases),
        "seconds": round(sum(p["seconds"] for p in phases), 1),
    }

    pics = []
    for lst in (illustrations or {}).values():
        pics.extend(lst)
    if cover is not None:
        pics.append(cover)

    images = {}
    if pics:
        from ..digest.illustrate import RENDER_W, RENDER_H, EMBED_W

        counts = {}
        for p in pics:
            counts[p.style.label] = counts.get(p.style.label, 0) + 1
        images = {
            "count": len(pics),
            "model": config_manager.get("image_generation.model", "flux2-klein"),
            "dimensions": f"{RENDER_W}x{RENDER_H} rendered, {EMBED_W}px embedded, greyscale",
            "seconds": round(sum(p.seconds for p in pics), 1),
            "styles": [f"{n}x {label}" for label, n in
                       sorted(counts.items(), key=lambda kv: -kv[1])],
            "mean_ink": round(sum(p.ink for p in pics) / len(pics), 3),
        }
        models["Illustration"] = images["model"]

    return {
        "stories": sorted(per_story, key=lambda r: -r["tokens"]),
        "phases": phases,
        "totals": totals,
        "images": images,
        "models": models,
        "edition_seconds": round(edition_seconds, 1),
        "item_ids": item_ids,
    }


def as_html(diag: dict) -> str:
    """The closing section of the digest."""
    import html as _h

    def esc(x):
        return _h.escape(str(x), quote=True)

    out = ['<hr class="rule"/>', "<h2>Diagnostics</h2>",
           '<p class="meta">What produced this edition, and where the effort '
           "went. Printed here because the answer is rarely where you would "
           "guess.</p>"]

    if diag.get("models"):
        out.append("<h3>Models</h3><ul>")
        for role, model in diag["models"].items():
            out.append(f"<li>{esc(role)} — <code>{esc(model)}</code></li>")
        out.append("</ul>")

    out.append("<h3>Tokens by phase</h3><ul>")
    for p in diag.get("phases") or []:
        out.append(
            f"<li><strong>{esc(p['phase'])}</strong> — {p['calls']} calls, "
            f"{p['tokens_in']:,} in / {p['tokens_out']:,} out, {p['seconds']:.1f}s</li>"
        )
    t = diag.get("totals") or {}
    out.append(
        f"<li><strong>Total</strong> — {t.get('calls', 0)} calls, "
        f"{t.get('tokens_in', 0):,} in / {t.get('tokens_out', 0):,} out, "
        f"{t.get('seconds', 0):.1f}s</li></ul>"
    )

    out.append("<h3>Research per story</h3><ul>")
    for r in diag.get("stories") or []:
        out.append(
            f"<li>{r['tokens']:,} tokens over {r['steps']} steps — "
            f"{esc(r['title'])}</li>"
        )
    out.append("</ul>")

    img = diag.get("images") or {}
    if img:
        out.append("<h3>Images</h3><ul>")
        out.append(
            f"<li>{img['count']} generated by <code>{esc(img['model'])}</code>, "
            f"{esc(img['dimensions'])}, {img['seconds']:.1f}s total, "
            f"mean ink {img['mean_ink']}</li>"
        )
        for st in img.get("styles") or []:
            out.append(f"<li>{esc(st)}</li>")
        out.append("</ul>")
    return "\n".join(out)
