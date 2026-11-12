"""Production: a planned block becomes files (issues #30-#33).

The planner says what the block is. This makes it: for every item, find
the material, have it written and edited, record it, check it, and write
down on the item itself what was made — the words, the file, the scores.
When it is done the sheet is complete in the plain sense: every item
either names a file or says why it has none, and the director can serve
the block without asking anything else.

    produce(sheet)   fill in a planned sheet; returns what it made and cost
"""

import logging
import os
import time
from typing import List, Optional

from . import booth, log, material, radio_root, writers
from .format import show as show_by_key
from .library import pick_from_bank
from .segments import segment

logger = logging.getLogger(__name__)


def block_dir(sheet_id: str) -> str:
    d = os.path.join(radio_root(), "blocks", sheet_id)
    os.makedirs(d, exist_ok=True)
    return d


def _bed(show_key: str, used: List[str]) -> Optional[dict]:
    """A bed from the show's palette that this block has not used yet."""
    b = pick_from_bank("music", avoid_ids=used, show=show_key)
    if b:
        used.insert(0, b["id"])
    return b


def _stock(kind: str, show_key: str, used: List[str]) -> Optional[dict]:
    b = pick_from_bank(kind, avoid_ids=used, show=show_key)
    if b:
        used.insert(0, b["id"])
    return b


def _ident(show_key: str, used: List[str]) -> Optional[dict]:
    """A sung jingle for the show if the shelf has one, else a spoken ID."""
    for kind in ("jingle", "station_id"):
        b = pick_from_bank(kind, avoid_ids=used, show=show_key, strict=True) \
            or pick_from_bank(kind, avoid_ids=used, show=show_key)
        if b:
            used.insert(0, b["id"])
            return b
    return None


def _skip(item: dict, why: str) -> None:
    item.update(status="skipped", reason=why)
    log("booth", f"item {item['n'] + 1} ({item['segment']}) skipped: {why}", kind=item["kind"])


def _song(item: dict, sh, out_dir: str, usage: dict) -> bool:
    """The song of the hour: lyrics from the lyricist, sung by the music
    model, introduced by the anchor."""
    from ..content.llm_service import LLMService
    from ..content.prompts import render
    from . import mix
    from .music import make_song
    from .schemas import Lyrics
    from .voice import say

    mat = material.story(item["story"], item.get("angle"))
    if not mat:
        return False
    svc = LLMService(task="radio.lyrics")
    try:
        ly = svc.generate_structured(render("radio.lyrics", song_style=sh.song_style,
                                            angle=item.get("angle") or "(none)", material=mat), Lyrics)
    except Exception as e:
        logger.warning(f"radio: lyricist failed ({e})")
        return False
    finally:
        writers._add_usage(usage, svc)
    from .copy import singable

    ly.lyrics = singable(ly.lyrics)
    seconds = int(os.getenv("RADIO_SONG_SECONDS", "75"))
    song = make_song(f"{sh.song_style}, {ly.style}"[:300], ly.lyrics, seconds,
                     os.path.join(out_dir, f"{item['n']:02d}-song-only.mp3"))
    if not song:
        return False
    intro_text = f"The song of the hour. This one is called {ly.title.strip().rstrip('.')}."
    intro = say(intro_text, sh.anchor, os.path.join(out_dir, f"{item['n']:02d}-song-intro.mp3"))
    out = os.path.join(out_dir, f"{item['n']:02d}-song.mp3")
    if not (intro and mix.after(intro, song, out)):
        os.replace(song, out)
    item.update(status="ready", path=out, title=f"Song of the hour: {ly.title.strip()}",
                text=[{"speaker": sh.anchor, "mood": "default", "text": intro_text}],
                lyrics=ly.lyrics, music_style=ly.style, seconds=(mix.measure(out) or {}).get("seconds"))
    return True


def produce(sheet: dict, save=None, at=None) -> dict:
    """Make every item of a planned sheet. `save(items)` is called after
    each item so the control room can watch the block fill in. `at` is the
    hour the block is for when that is not now: an edition of the morning
    show made at night says it is morning."""
    items = sheet["items"]
    sheet_id = sheet["sheet_id"]
    out_dir = block_dir(sheet_id)
    usage = {"calls": 0, "tokens_in": 0, "tokens_out": 0}
    earlier: List[str] = []
    openers: List[str] = []
    used_stock: List[str] = []
    made = spoken_seconds = 0
    started = time.time()
    story_titles = [i["title"] for i in items if i.get("story") and i.get("title")]
    story_rows = [{"item_id": i["story"], "title": i["title"]} for i in items if i.get("story")
                  and segment(i["segment"]).kind in ("brief", "feature")]

    for item in items:
        seg = segment(item["segment"])
        sh = show_by_key(item["show"])
        try:
            if item["segment"] in ("music", "track"):
                b = _stock("track", sh.key, used_stock) if item["segment"] == "track" else None
                b = b or _bed(sh.key, used_stock)
                if not b:
                    _skip(item, "no bed in stock")
                    continue
                item.update(status="ready", path=b["path"], title=b.get("style") or "music",
                            bank_id=b["id"], seconds=b.get("seconds"))
            elif item["segment"] == "ident":
                b = _ident(sh.key, used_stock)
                if not b:
                    _skip(item, "no ident in stock")
                    continue
                item.update(status="ready", path=b["path"], title=b.get("text") or "H.N.F.M.",
                            bank_id=b["id"], host=b.get("host"), seconds=b.get("seconds"))
            elif item["segment"] == "time_check":
                # Said at the moment it airs (director), so it is right.
                item.update(status="live", host=sh.cohost, title="The time")
            elif item["segment"] == "song":
                if not (item.get("story") and _song(item, sh, out_dir, usage)):
                    b = _bed(sh.key, used_stock)
                    if not b:
                        _skip(item, "no song and no bed")
                        continue
                    item.update(segment="music", kind="music", name="Music", status="ready", path=b["path"],
                                title=b.get("style") or "music", bank_id=b["id"], seconds=b.get("seconds"))
                else:
                    log("booth", f"the jukebox sang: {item['title']}", kind="music", show=sh.key)
            else:
                mat = material.for_segment(
                    seg, story_id=item.get("story"),
                    seed=hash((sheet_id, item["n"])) % 9973, show=sh,
                    next_show=show_by_key(item["next_show"]) if item.get("next_show") else None,
                    stories=story_rows, coming_up=story_titles, now=at,
                )
                if mat is None and seg.fallback and segment(seg.fallback).written:
                    # Nothing to write this from (no front page readings yet,
                    # say): make the segment it falls back to instead.
                    simpler = segment(seg.fallback)
                    mat = material.for_segment(simpler, story_id=item.get("story"),
                                               seed=hash((sheet_id, item["n"])) % 9973, show=sh, now=at)
                    if mat is not None:
                        seg = simpler
                        item.update(segment=seg.key, kind=seg.kind, name=seg.name, demoted_from=item["segment"])
                        if seg.voices == "cast" or len(item.get("speakers") or []) > 1 and seg.voices != "duo":
                            item["speakers"] = (item.get("speakers") or [sh.anchor])[:1]
                if mat is None:
                    _skip(item, "no material")
                    continue
                piece = writers.produce(seg, show=sh, speakers=item["speakers"], material=mat,
                                        earlier=earlier, earlier_openers=openers)
                if piece:
                    for k in usage:
                        usage[k] += piece.usage.get(k, 0)
                # A piece that would not come out right becomes the simpler
                # piece its segment falls back to, on the same story: a
                # two-hander that will not stop echoing is a headline.
                if (not piece or not piece.lines) and seg.fallback and item.get("story"):
                    simpler = segment(seg.fallback)
                    mat2 = material.for_segment(simpler, story_id=item["story"], show=sh)
                    if simpler.written and mat2:
                        log("booth", f"item {item['n'] + 1}: the {seg.name} did not come out; writing a {simpler.name}",
                            kind=simpler.kind, segment=simpler.key)
                        seg = simpler
                        item.update(segment=seg.key, kind=seg.kind, name=seg.name,
                                    speakers=item["speakers"][:1], demoted_from=item["segment"])
                        piece = writers.produce(seg, show=sh, speakers=item["speakers"], material=mat2,
                                                earlier=earlier, earlier_openers=openers)
                        if piece:
                            for k in usage:
                                usage[k] += piece.usage.get(k, 0)
                if not piece or not piece.lines:
                    _skip(item, "the writers had nothing")
                    continue
                bed = _bed(sh.key, used_stock) if seg.mix in ("bed", "phone", "sting") else None
                sting = _ident(sh.key, used_stock) if seg.mix == "sting" else None
                if sting and sting["kind"] != "jingle":
                    sting = None  # a spoken ID in front of a spoken open is two IDs
                rec = booth.record(piece.lines, seg, os.path.join(out_dir, f"{item['n']:02d}-{seg.key}.mp3"),
                                   bed=bed["path"] if bed else None, sting=sting["path"] if sting else None,
                                   seed=hash(sheet_id) % 97)
                if not rec or not rec.get("path"):
                    item["qa"] = (rec or {}).get("qa")
                    _skip(item, "it did not pass the listen-back" if rec else "the voice was away")
                    continue
                item.update(
                    status="ready", path=rec["path"], seconds=rec.get("seconds"), text=piece.lines,
                    title=item.get("title") or f"{seg.name}: {piece.lines[0]['text'][:70]}",
                    host=piece.lines[0]["speaker"], review=piece.review, qa=rec["qa"], plan=piece.plan,
                    attempts=piece.attempts, lint=piece.lint, prompt_version=piece.prompt_version,
                )
                earlier.append(" ".join(l["text"] for l in piece.lines))
                openers.append(writers.opener(piece.lines[0]["text"]))
                spoken_seconds += rec.get("seconds") or 0
                log("booth", f"{', '.join(item['speakers'][:2])} recorded {seg.name}"
                    + (f": {item['title'][:50]}" if item.get("story") else ""),
                    kind=seg.kind, sheet_id=sheet_id, segment=seg.key,
                    match=(rec["qa"] or {}).get("match"), attempts=piece.attempts)
            made += 1
        except Exception as e:  # one bad item must not lose the block
            logger.exception(f"radio: item {item['n']} ({item['segment']}) failed")
            _skip(item, f"error: {str(e)[:80]}")
        finally:
            if save:
                try:
                    save(items)
                except Exception:
                    pass

    stats = {"made": made, "skipped": sum(1 for i in items if i.get("status") == "skipped"),
             "spoken_seconds": round(spoken_seconds), "seconds": round(sum(i.get("seconds") or 0 for i in items)),
             "wall_seconds": round(time.time() - started), **usage}
    log("producer", f"block {sheet_id}: {made} of {len(items)} items made, "
        f"{stats['seconds'] // 60} min of air for {usage['tokens_in'] + usage['tokens_out']} tokens "
        f"in {stats['wall_seconds']} s", sheet_id=sheet_id, **stats)
    return stats
