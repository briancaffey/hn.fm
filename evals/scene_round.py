#!/usr/bin/env python3
"""Score the intent -> scene step, which is where image variety is lost.

Reuses the scripts captured by run_round.py so the comparison isolates the
art-director prompt: same intents in, different prompt, measure what comes out.
"""
import json, sys, time
sys.path.insert(0, "/app")
from src.hnfm.content.art_direction import pick_theme          # noqa: E402
from src.hnfm.evals import image_set_report                    # noqa: E402
from src.hnfm.utils.segment_utils import generate_image_prompt_v1  # noqa: E402

SHOTS = ["wide establishing shot", "extreme macro detail",
         "high overhead / top-down view", "dramatic low-angle hero shot",
         "over-the-shoulder perspective", "symbolic conceptual metaphor",
         "intimate close-up", "dynamic dutch-angle composition"]


def main():
    src_label, out_label = sys.argv[1], sys.argv[2]
    src = json.load(open(f"/app/outputs/evals/{src_label}.json"))
    out = {"label": out_label, "results": []}
    agg = []
    for r in src["results"]:
        if "sections" not in r:
            continue
        theme = pick_theme(seed=r["item_id"])
        prior, scenes = [], []
        t0 = time.time()
        for i, sec in enumerate(r["sections"], start=1):
            p = generate_image_prompt_v1(
                sec["text"], r["title"], theme=theme,
                shot_hint=SHOTS[(i - 1) % len(SHOTS)],
                visual_intent=sec["visual_intent"],
                prior_scenes=prior, section_index=i,
            )
            prior.append(p)
            scenes.append(p)
        rep = image_set_report(scenes)
        rep["seconds"] = round(time.time() - t0, 1)
        agg.append(rep)
        out["results"].append({"item_id": r["item_id"], "report": rep,
                               "scenes": scenes})

    def mean(k):
        return round(sum(a[k] for a in agg) / len(agg), 3) if agg else None
    out["summary"] = {
        "takes": len(agg),
        "subject_overlap": mean("subject_overlap"),
        "max_pair_overlap": mean("max_pair_overlap"),
        "near_duplicate_pairs": mean("near_duplicate_pairs"),
        "lexical_diversity": mean("lexical_diversity"),
        "shot_coverage": mean("shot_coverage"),
    }
    json.dump(out, open(f"/app/outputs/evals/{out_label}.json", "w"), indent=2)
    print(f"\n=== {out_label} ===")
    for k, v in out["summary"].items():
        print(f"  {k:22} {v}")


if __name__ == "__main__":
    main()
