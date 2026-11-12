#!/usr/bin/env python3
"""One evaluation round for the radio's writing (issue #34).

Writes the same stories two ways and measures both:

    old   the station as it was: the digest's punchline prompt asked for
          bullets, and the host read the title and then the bullets
    new   the writers' room: fact sheet, worked example, rules, editor

No audio is made. The thing under test is the copy, and copy is where the
station's quality is decided; the booth's checks are measured in production.

For every piece: its length, what the rules object to (the same rules for
both), and the editor's scores against the same fact sheet. The round also
writes a blinded file of pairs, so that a person or a stronger model can
say which of each pair they would rather hear without knowing which is
which. `--judgements` folds those answers back into the report.

Usage:
    python evals/radio_round.py <label> [--n 12] [--stories id,id,...]
    python evals/radio_round.py <label> --judgements path/to/judgements.json

Reads the database and the model; writes outputs/evals/radio/<label>/.
"""

import argparse
import json
import os
import random
import sys
import time
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from hnfm.radio import material, writers  # noqa: E402
from hnfm.radio.copy import speakable  # noqa: E402
from hnfm.radio.format import show  # noqa: E402
from hnfm.radio.schemas import Copy, Line  # noqa: E402
from hnfm.radio.segments import segment  # noqa: E402
from hnfm.radio.sheets import sheet_for  # noqa: E402

SEG = segment("headline")
SHOW = show("main_thread")
HOSTS = ("sofia", "jason", "aria", "mia", "leo", "ray")


def out_dir(label: str) -> str:
    d = os.path.join(os.getenv("OUTPUTS_DIR", "/app/outputs"), "evals", "radio", label)
    os.makedirs(d, exist_ok=True)
    return d


def pick_stories(n: int) -> list:
    """Stories with a research brief, newest first: the set both writers
    can work from."""
    from sqlalchemy import text

    from hnfm.db.engine import db_session

    with db_session() as s:
        rows = s.execute(text(
            "select item_id from story_briefs group by item_id order by max(created_at) desc limit :n"
        ), {"n": n * 3}).fetchall()
    out = []
    for (iid,) in rows:
        if sheet_for(iid):
            out.append(iid)
        if len(out) >= n:
            break
    return out


def old_piece(item_id: int) -> dict:
    """The brief as the station wrote it before the rebuild: bullets from
    the digest's punchline prompt, read out after the title."""
    import re

    from hnfm.content.llm_service import LLMService
    from hnfm.content.prompts import render
    from hnfm.db import repo
    from hnfm.digest.compose import _punchline_material, parse_bullets, scrub_bullets
    from hnfm.digest.select import _scraped_material

    item = repo.get_item(item_id)
    record = repo.get_latest_story_brief(item_id) or {}
    brief = record.get("brief") or {}
    summary, excerpt = ("", "") if brief.get("thesis") else _scraped_material(repo, item_id, record.get("run") or 1)

    class _S:
        pass

    st = _S()
    st.title, st.url, st.brief, st.summary, st.excerpt = item.title, item.url, brief, summary, excerpt
    st.hn_url = f"https://news.ycombinator.com/item?id={item_id}"
    svc = LLMService(task="digest.punchline")
    t = time.time()
    text = svc.generate_content(render("digest.punchline", title=item.title, url=item.url or st.hn_url,
                                       material=_punchline_material(st)))
    authors = [c.get("author") for c in (brief.get("comment_insights") or [])]
    bullets = scrub_bullets(parse_bullets(text or ""), authors)[:3]
    title = re.sub(r"\s+", " ", item.title).strip().rstrip(".")
    spoken = " ".join([f"{title}."] + [b.strip() + ("" if b.strip()[-1:] in ".!?" else ".") for b in bullets])
    return {"text": speakable(spoken), "seconds": round(time.time() - t, 1),
            "tokens": svc.usage["tokens_in"] + svc.usage["tokens_out"], "calls": svc.usage["calls"]}


def new_piece(item_id: int, host: str) -> dict:
    mat = material.story(item_id)
    t = time.time()
    p = writers.produce(SEG, show=SHOW, speakers=[host], material=mat)
    if not p:
        return {"text": "", "seconds": round(time.time() - t, 1), "tokens": 0, "calls": 0, "failed": True}
    return {"text": p.text(), "seconds": round(time.time() - t, 1), "attempts": p.attempts,
            "tokens": p.usage["tokens_in"] + p.usage["tokens_out"], "calls": p.usage["calls"],
            "repaired": p.repaired}


def measure(text: str, mat: str, host: str) -> dict:
    """The same yardstick for both: the rules, then the editor."""
    if not text:
        return {"words": 0, "lint": ["nothing was written"], "review": None}
    copy = Copy(lines=[Line(speaker=host, mood="default", text=text)])
    rev = writers.review(SEG, mat, copy)
    return {"words": copy.words(), "lint": writers.lint(SEG, copy, [host]),
            "review": None if rev is None else {**rev.scores(), "passes": rev.passes(),
                                                "unsupported": rev.unsupported[:3]}}


def run(label: str, stories: list) -> dict:
    rows, pairs = [], []
    rng = random.Random(label)
    for n, iid in enumerate(stories):
        host = HOSTS[n % len(HOSTS)]
        sheet = sheet_for(iid)
        mat = material.story(iid)
        row = {"item_id": iid, "title": sheet["title"], "host": host}
        for which, make in (("old", lambda: old_piece(iid)), ("new", lambda: new_piece(iid, host))):
            try:
                piece = make()
            except Exception as e:
                piece = {"text": "", "error": str(e)[:160]}
            piece.update(measure(piece.get("text") or "", mat, host))
            row[which] = piece
        rows.append(row)
        order = ["old", "new"]
        rng.shuffle(order)
        pairs.append({"pair": n + 1, "item_id": iid, "title": sheet["title"], "facts": mat,
                      "A": row[order[0]]["text"], "B": row[order[1]]["text"], "_key": {"A": order[0], "B": order[1]}})
        print(f"[{n + 1}/{len(stories)}] {sheet['title'][:60]}", flush=True)

    report = {"label": label, "at": datetime.utcnow().isoformat(), "segment": SEG.key,
              "prompts": {"old": "digest.punchline (title, then bullets)", "new": "radio.facts + radio.write + radio.edit"},
              "rows": rows, "summary": summarise(rows)}
    d = out_dir(label)
    with open(os.path.join(d, "report.json"), "w") as f:
        json.dump(report, f, indent=1)
    # The judge sees no key: which is old and which is new is kept apart.
    with open(os.path.join(d, "pairs.json"), "w") as f:
        json.dump([{k: v for k, v in p.items() if k != "_key"} for p in pairs], f, indent=1)
    with open(os.path.join(d, "key.json"), "w") as f:
        json.dump({p["pair"]: p["_key"] for p in pairs}, f)
    with open(os.path.join(d, "report.md"), "w") as f:
        f.write(markdown(report))
    return report


def summarise(rows: list) -> dict:
    out = {}
    for which in ("old", "new"):
        ps = [r[which] for r in rows]
        scored = [p["review"] for p in ps if p.get("review")]
        n = max(1, len(ps))
        out[which] = {
            "pieces": len(ps),
            "failed": sum(1 for p in ps if not p.get("text")),
            "words_mean": round(sum(p["words"] for p in ps) / n, 1),
            "clean_of_rule_notes": sum(1 for p in ps if p.get("text") and not p["lint"]),
            "opens_on_title_or_recites": sum(1 for p in ps if any("instructions" in x for x in p["lint"])),
            "too_long_or_short": sum(1 for p in ps if any(x.startswith("Too ") for x in p["lint"])),
            "editor_pass": sum(1 for s in scored if s["passes"]),
            "editor_mean": {k: round(sum(s[k] for s in scored) / max(1, len(scored)), 2)
                            for k in ("hook", "clarity", "faithful", "speakable", "voice")},
            "seconds_mean": round(sum(p.get("seconds") or 0 for p in ps) / n, 1),
            "tokens_mean": round(sum(p.get("tokens") or 0 for p in ps) / n),
        }
    return out


def markdown(report: dict) -> str:
    s = report["summary"]
    lines = [f"# Radio writing round: {report['label']}", "",
             f"{len(report['rows'])} stories, one headline each, written two ways. "
             f"Old: {report['prompts']['old']}. New: {report['prompts']['new']}.", "",
             "| | old | new |", "|---|---|---|"]
    for key, name in (("words_mean", "Mean length (words; the slot wants about 70)"),
                      ("clean_of_rule_notes", "Pieces the rules have no notes on"),
                      ("too_long_or_short", "Outside the length band"),
                      ("failed", "Nothing written"),
                      ("editor_pass", "Passed by the editor prompt"),
                      ("seconds_mean", "Seconds per piece"),
                      ("tokens_mean", "Tokens per piece")):
        lines.append(f"| {name} | {s['old'][key]} | {s['new'][key]} |")
    for k in ("hook", "clarity", "faithful", "speakable", "voice"):
        lines.append(f"| Editor: {k} (1 to 5) | {s['old']['editor_mean'][k]} | {s['new']['editor_mean'][k]} |")
    j = report.get("judgements")
    if j:
        lines += ["", f"## Blind preference ({j['judge']})", "",
                  f"Of {j['pairs']} pairs: new preferred in {j['new']}, old in {j['old']}, no preference in {j['tie']}.", ""]
        if j.get("unfaithful"):
            lines.append(f"Pieces the judge marked as saying something the facts do not: "
                         f"old {j['unfaithful'].get('old', 0)}, new {j['unfaithful'].get('new', 0)}.")
    lines += ["", "## The pieces", ""]
    for r in report["rows"]:
        lines += [f"### {r['title']}", "", f"**Old** ({r['old']['words']} words): {r['old']['text']}", "",
                  f"**New** ({r['new']['words']} words, {r['host']}): {r['new']['text']}", ""]
    return "\n".join(lines) + "\n"


def fold_judgements(label: str, path: str) -> dict:
    """judgements.json: {"judge": "...", "pairs": [{"pair": 1, "prefer": "A"|"B"|"tie",
    "unfaithful": ["A"], "why": "..."}]}"""
    d = out_dir(label)
    report = json.load(open(os.path.join(d, "report.json")))
    key = json.load(open(os.path.join(d, "key.json")))
    given = json.load(open(path))
    tally = {"old": 0, "new": 0, "tie": 0}
    unfaithful = {"old": 0, "new": 0}
    for p in given["pairs"]:
        k = key[str(p["pair"])]
        tally[k[p["prefer"]] if p["prefer"] in ("A", "B") else "tie"] += 1
        for side in p.get("unfaithful") or []:
            unfaithful[k[side]] += 1
    report["judgements"] = {"judge": given.get("judge", "unknown"), "pairs": len(given["pairs"]), **tally,
                            "unfaithful": unfaithful, "detail": given["pairs"]}
    json.dump(report, open(os.path.join(d, "report.json"), "w"), indent=1)
    open(os.path.join(d, "report.md"), "w").write(markdown(report))
    return report["judgements"]


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("label")
    ap.add_argument("--n", type=int, default=12)
    ap.add_argument("--stories", default="")
    ap.add_argument("--judgements", default="")
    a = ap.parse_args()
    if a.judgements:
        print(json.dumps(fold_judgements(a.label, a.judgements), indent=1))
    else:
        ids = [int(x) for x in a.stories.split(",") if x.strip()] or pick_stories(a.n)
        rep = run(a.label, ids)
        print(json.dumps(rep["summary"], indent=1))
