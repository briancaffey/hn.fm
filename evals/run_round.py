#!/usr/bin/env python3
"""One evaluation round: regenerate scripts + image prompts, score, record.

Deliberately does NOT render audio, images or video. The thing under
improvement is the prompts, and a script plus its image prompts exposes every
metric that matters at a fraction of the time and GPU. Full renders happen once
at the end to prove the improvements survive the whole pipeline.

Usage: python evals/run_round.py <round-label> <item_id> [<item_id> ...]
"""

import json
import os
import sys
import time
from datetime import datetime

sys.path.insert(0, "/app")

from src.hnfm.db import repo  # noqa: E402
from src.hnfm.evals import image_set_report, script_report  # noqa: E402
from src.hnfm.utils.segment_utils import generate_script  # noqa: E402

OUT = "/app/outputs/evals"


def run_one(item_id: int) -> dict:
    run = repo.latest_run_for_item(item_id) if hasattr(repo, "latest_run_for_item") else None
    pr = None
    for r in range(1, 6):
        pr = repo.get_run(item_id, r)
        if pr:
            break
    if not pr:
        return {"item_id": item_id, "error": "no run"}

    t0 = time.time()
    notes = {}
    script = generate_script(pr.content_clean or "", pr.summary or "", notes=notes)
    seconds = round(time.time() - t0, 1)

    sections = [
        {"speaker": s.speaker, "text": s.text, "beat": s.beat,
         "visual_intent": s.visual_intent}
        for s in script.sections
    ]
    intents = [s["visual_intent"] for s in sections]

    return {
        "item_id": item_id,
        "title": script.title,
        "seconds": seconds,
        "notes": notes,
        "script": script_report(sections),
        "intents": image_set_report(intents),
        "sections": sections,
    }


def main() -> int:
    label = sys.argv[1]
    ids = [int(x) for x in sys.argv[2:]]
    os.makedirs(OUT, exist_ok=True)

    results = []
    for iid in ids:
        try:
            results.append(run_one(iid))
        except Exception as e:
            results.append({"item_id": iid, "error": str(e)[:200]})

    ok = [r for r in results if "script" in r]
    summary = {}
    if ok:
        def mean(path, sub):
            vals = [r[path][sub] for r in ok if r.get(path)]
            return round(sum(vals) / len(vals), 3) if vals else None
        summary = {
            "stories": len(ok),
            "switch_rate": mean("script", "speaker_switch_rate"),
            "repeated_openings": mean("script", "repeated_openings"),
            "script_lex": mean("script", "lexical_diversity"),
            "length_variation": mean("script", "length_variation"),
            "intent_overlap": mean("intents", "subject_overlap"),
            "intent_maxpair": mean("intents", "max_pair_overlap"),
            "intent_dupes": mean("intents", "near_duplicate_pairs"),
            "intent_lex": mean("intents", "lexical_diversity"),
            "mean_seconds": mean("script", "sections") and round(
                sum(r["seconds"] for r in ok) / len(ok), 1),
        }

    payload = {"label": label, "at": datetime.utcnow().isoformat(),
               "summary": summary, "results": results}
    path = os.path.join(OUT, f"{label}.json")
    with open(path, "w") as f:
        json.dump(payload, f, indent=2)

    print(f"\n=== {label} ===")
    for k, v in summary.items():
        print(f"  {k:20} {v}")
    for r in results:
        if "error" in r:
            print(f"  !! {r['item_id']}: {r['error']}")
    print(f"  written: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
