"""The writers' room: draft, check, edit, rewrite (issue #30).

A piece of copy is written once, checked by rules that cost nothing, read
by an editor prompt against a rubric, and rewritten once if it falls
short. What comes out is a `Piece`: the lines, the scores, and what it
cost. Nothing here speaks or mixes; that is the booth.

    produce(seg, ...)   the whole loop, or None if nothing airable came out
    lint(seg, copy)     the rules, as a list of notes for the writer
"""

import logging
import os
import re
from dataclasses import dataclass, field
from typing import List, Optional, Sequence

from .copy import bleeped, speakable
from .cast import briefing, mood_or_default, sheets
from .schemas import CALLERS, Copy, Line, Review, copy_schema
from .segments import SEGMENTS, Segment

logger = logging.getLogger(__name__)

# Phrases the station does not say. The prompt asks; this checks.
BANNED = (
    "dive in", "deep dive", "delve", "game changer", "game-changer", "buckle up", "stay tuned",
    "let's unpack", "fast-paced world", "it turns out", "time will tell", "the future of",
    "revolutionary", "folks", "welcome back", "without further ado", "in a recent post",
    "in conclusion", "at the end of the day",
)
# The assignment read out on air: the commonest way the local model fails.
RECITED = (
    "the story is about", "this story is about", "the headline", "the hook", "the tension",
    "the catch is", "the one detail", "the detail a curious", "a mock sponsor", "the product nobody sells",
    "the material", "the discussion notes", "the discussion also", "a commenter notes", "a commenter reflects",
    "not established", "does not name", "old-time radio", "the assignment", "the producer's angle",
    # Notes about the input, said to the listener.
    "the source does not", "by the source", "the article does not specify", "a caller might",
    "a caller could", "remains unspecified", "remain unspecified", "the objection from", "a correspondent reports", "here is the doubt",
    "is not specified", "are not specified", "not disclosed", "does not establish", "the mystery remains", "the editor sent",
)
# Notes that keep a piece off the air if they still stand after repair.
HARD = ("You read your instructions", "Only these speakers", "You reused the example",
        "The second speaker only repeats", "The piece is empty", "This is a piece for more than one",
        "The host opens", "The correspondent has the facts", "No caller speaks", "Too short")
# Pieces that are meant to sound the same every time.
FORMULAIC = ("theme", "handoff", "bulletin")
MAX_SENTENCE_WORDS = 32
# A piece may run this far under or over its target before it is sent back.
LENGTH_BAND = (0.55, 1.45)


def editor_on() -> bool:
    return os.getenv("RADIO_EDITOR", "true").strip().lower() != "false"


@dataclass
class Piece:
    segment: str
    lines: List[dict]                      # [{speaker, mood, text}] — text is speakable
    review: Optional[dict] = None          # scores, passes, what was unsupported, notes
    plan: Optional[dict] = None            # the writer's hook, facts and ending
    repaired: bool = False                 # True if sentences were cut by the rules
    attempts: int = 1
    lint: List[str] = field(default_factory=list)   # what the rules still object to
    usage: dict = field(default_factory=lambda: {"calls": 0, "tokens_in": 0, "tokens_out": 0})
    prompt_version: Optional[str] = None

    def text(self) -> str:
        return " ".join(l["text"] for l in self.lines)

    def words(self) -> int:
        return len(self.text().split())


def opener(text: str, n: int = 3) -> str:
    """The first few words, lower-cased: how two pieces are told to start
    differently."""
    return " ".join(re.sub(r"[^a-z' ]", " ", (text or "").lower()).split()[:n])


def lint(seg: Segment, copy: Copy, speakers: Sequence[str], earlier_openers: Sequence[str] = ()) -> List[str]:
    """What the rules object to, phrased as notes to the writer. Empty is a pass."""
    notes: List[str] = []
    lines = [l for l in copy.lines if (l.text or "").strip()]
    if not lines:
        return ["The piece is empty. Write it."]

    strangers = sorted({l.speaker for l in lines if l.speaker not in speakers})
    if strangers:
        notes.append(f"Only these speakers may talk: {', '.join(speakers)}. Remove {', '.join(strangers)}.")

    words = sum(len(l.text.split()) for l in lines)
    lo, hi = int(seg.words * LENGTH_BAND[0]), int(seg.words * LENGTH_BAND[1])
    if words < lo:
        notes.append(f"Too short: {words} words, the slot wants about {seg.words}. Add the detail, not padding.")
    if words > hi:
        notes.append(f"Too long: {words} words, the slot wants about {seg.words}. Cut the weakest sentence.")

    whole = " ".join(l.text for l in lines).lower()
    said = [b for b in BANNED if b in whole]
    if said:
        notes.append("Do not use: " + ", ".join(f'"{b}"' for b in said) + ".")

    recited = [r for r in RECITED if r in whole]
    if recited:
        notes.append("You read your instructions out loud. Never say: "
                     + ", ".join(f'"{r}"' for r in recited[:3]) + ". Just tell the listener the thing.")

    # Formulaic pieces share their shape with the example on purpose.
    copied = None if seg.key in FORMULAIC else copied_from_examples(seg.key, " ".join(l.text for l in lines))
    if copied:
        notes.append(f'You reused the example\'s words ("{copied}"). Write your own line there.')

    for sentence in _sentences(" ".join(l.text for l in lines)):
        if len(sentence.split()) > MAX_SENTENCE_WORDS:
            notes.append(f'Break up the long sentence starting "{" ".join(sentence.split()[:6])}…".')
            break

    first = opener(lines[0].text)
    if first and first in set(earlier_openers):
        notes.append(f'Another item this hour already opened with "{first}". Open differently.')

    echoes = echo_count(lines)
    if seg.voices == "duo" and echoes >= 2:
        notes.append("The second speaker only repeats what the first just said. Give them their own lines: "
                     "a doubt, a dry remark, a question the first speaker has to answer.")

    if seg.voices in ("duo", "callers") and len({l.speaker for l in lines}) < 2:
        notes.append("This is a piece for more than one voice. Give the other speaker their lines.")
    if seg.voices == "correspondent" and len(speakers) > 1:
        host, reporter = speakers[0], speakers[1]
        if lines[0].speaker != host:
            notes.append(f"The host opens. {host} says what the story is in one sentence; "
                         f"then {reporter} reports.")
        elif sum(1 for l in lines if l.speaker == reporter) < 2:
            notes.append(f"The correspondent has the facts. Give {reporter} at least three turns.")
    if seg.voices == "callers" and not any(l.speaker in CALLERS for l in lines):
        notes.append("No caller speaks. The callers make the points; the host reacts.")
    if re.search(r"[\[\]<>*_#]|https?://", " ".join(l.text for l in lines)):
        notes.append("Remove brackets, markup, stage directions and links: only spoken words.")
    return notes


_ACRONYM_END = re.compile(r"(?:\b[A-Za-z]\.){2,}$")


def _sentences(text: str) -> List[str]:
    """Sentences, without breaking inside a spelled acronym. "The L.L.M.
    inference cost varies" is one sentence: a split after "L.L.M." once
    left a piece ending on half of one."""
    out: List[str] = []
    for part in re.split(r"(?<=[.!?])\s+", (text or "").strip()):
        if not part:
            continue
        if out and _ACRONYM_END.search(out[-1]) and not part[:1].isupper():
            out[-1] += " " + part
        else:
            out.append(part)
    return out


def _grams(text: str, n: int = 4) -> set:
    w = _norm(text)
    return {" ".join(w[i:i + n]) for i in range(len(w) - n + 1)}


DUO_TURNS = 8
_TAG = re.compile(r"^that is the \w+\.?$", re.I)


def repair(seg: Segment, lines: List[dict], said_before: Sequence[str] = (),
           never: Sequence[str] = ()) -> List[dict]:
    """What the rules can fix without the writer: a sentence that reads
    the notes aloud is cut, a sentence said twice is said once, and a
    piece that runs long loses sentences from the end until it fits.
    The last guard before the booth; a prompt asks, this removes."""
    # A sentence another piece in this block already said is cut too: shown
    # what aired earlier, the model lifted whole sentences from it.
    seen = {" ".join(_norm(x)) for text in said_before for x in _sentences(text)}
    seen = {k for k in seen if len(k.split()) > 3}
    # `never` is direction the writer was given and must not say: the
    # show's tone ("Opinionated, and fond of an argument...") was read out
    # as if it were copy. A sentence sharing four words in a row with it goes.
    direction = set().union(*[_grams(t) for t in never]) if never else set()
    out = []
    for l in lines:
        kept = []
        for sent in _sentences(l["text"]):
            low = sent.lower()
            key = " ".join(_norm(sent))
            if any(r in low for r in RECITED) or (key in seen and len(key.split()) > 3):
                continue
            if direction and _grams(sent) & direction:
                continue
            # A sentence lifted from the worked example belongs to another
            # story. Asked to write its own, the model often hands the
            # example back again, so the sentence is cut here.
            if seg.key not in FORMULAIC and copied_from_examples(seg.key, sent):
                continue
            seen.add(key)
            kept.append(sent)
        if kept:
            out.append({**l, "text": " ".join(kept)})
    # A two-hander is eight turns. Left alone the model goes on for
    # thirteen, the second voice labelling each fact ("That is the catch.",
    # "That is the surface.", "That is the polish."). Those tags are cut,
    # and the piece keeps its first seven turns and its last.
    if seg.voices == "duo" and len(out) > 2:
        second = out[1]["speaker"]
        for l in out:
            if l["speaker"] == second:
                kept = [x for x in _sentences(l["text"]) if not _TAG.match(x.strip())]
                l["text"] = " ".join(kept) or l["text"]
        if len(out) > DUO_TURNS:
            out = out[:DUO_TURNS - 1] + out[-1:]
    # Too long: drop whole sentences from the end, never the last line of a
    # dialogue (that is the punchline) and never below two sentences.
    limit = int(seg.words * LENGTH_BAND[1])
    while sum(len(l["text"].split()) for l in out) > limit:
        idx = len(out) - 1 if seg.voices not in ("duo", "callers") else max(0, len(out) - 2)
        sents = _sentences(out[idx]["text"])
        if len(sents) > 1:
            out[idx] = {**out[idx], "text": " ".join(sents[:-1])}
        elif len(out) > 2:
            out.pop(idx)
        else:
            break
    return out


HANDOVERS = ("{name} has been looking at it.", "{name} is on the line.", "Over to {name}.",
             "{name} has the details.")
THANKS = ("Thanks, {name}.", "{name}, thank you.", "Thank you, {name}.")


def dress_correspondent(lines: List[dict], host: str, reporter: str, seed: int = 0) -> List[dict]:
    """The handover and the thank-you around a correspondent's report.
    The writer is asked for the report only: asked for the whole exchange
    it had hosts handing over to themselves and thanking nobody, so the
    courtesies are the station's, in one of a few forms."""
    from .cast import character

    name = (character(reporter).name if character(reporter) else reporter.capitalize())
    said = lambda l: l["text"].lower()  # noqa: E731
    # Whatever courtesies the writer added anyway.
    body = [l for l in lines if not (l["speaker"] == host and len(l["text"].split()) <= 5
                                     and ("thank" in said(l) or name.lower() in said(l)))]
    if not body or body[0]["speaker"] != host or not any(l["speaker"] == reporter for l in body):
        return lines
    # After the opening the report is the correspondent's; a host line in
    # the middle stays only if it is a question.
    body = [body[0]] + [l for l in body[1:] if l["speaker"] == reporter or l["text"].rstrip().endswith("?")]
    while body[-1]["speaker"] == host and len(body) > 1:
        body.pop()
    first = {**body[0], "text": body[0]["text"].rstrip() + " " + HANDOVERS[seed % len(HANDOVERS)].format(name=name)}
    return [first, *body[1:], {"speaker": host, "mood": "default",
                               "text": THANKS[seed % len(THANKS)].format(name=name)}]


def _clean(copy: Copy, speakers: Sequence[str]) -> List[dict]:
    """The lines as the booth will speak them: known speakers, known moods,
    text made speakable. A stranger's line is dropped rather than given to
    a host who did not say it."""
    out = []
    for l in copy.lines:
        text = bleeped(speakable(" ".join((l.text or "").split())))
        if not text or l.speaker not in speakers:
            continue
        # A mood the speaker's voice does not have is the plain voice.
        out.append({"speaker": l.speaker, "mood": mood_or_default(l.speaker, l.mood), "text": text})
    return out


def _render_piece(lines: Sequence[Line]) -> str:
    return "\n".join(f"{l.speaker} ({l.mood}): {l.text}" for l in lines)


def _add_usage(total: dict, svc) -> None:
    for k in ("calls", "tokens_in", "tokens_out"):
        total[k] = total.get(k, 0) + int(svc.usage.get(k) or 0)


_STOP = frozenset("a an the and or but of to in on at for with by is are was were be been it its this that "
                  "as from not no so".split())


def echo_count(lines) -> int:
    """How many turns do nothing but hand the previous speaker's words
    back ("Seven years promised." after a sentence about seven years)."""
    n = 0
    for prev, cur in zip(lines, lines[1:]):
        if prev.speaker == cur.speaker:
            continue
        # Compared by the first five letters, so "promised" is "promises"
        # and "Pixels" is "Pixel".
        mine = [w[:5] for w in _norm(cur.text) if w not in _STOP]
        theirs = {w[:5] for w in _norm(prev.text)}
        if 0 < len(mine) <= 12 and sum(1 for w in mine if w in theirs) / len(mine) >= 0.7:
            n += 1
    return n


_EXAMPLES: Optional[dict] = None


def _examples() -> dict:
    global _EXAMPLES
    if _EXAMPLES is None or os.getenv("PROMPTS_NO_CACHE", "").lower() in ("1", "true", "yes"):
        import yaml

        from ..content.prompts import prompts_dir

        try:
            _EXAMPLES = yaml.safe_load((prompts_dir() / "examples" / "radio.yaml").read_text(encoding="utf-8")) or {}
        except Exception as e:
            logger.warning(f"radio: no examples file ({e})")
            _EXAMPLES = {}
    return _EXAMPLES


def _norm(text: str) -> List[str]:
    return re.sub(r"[^a-z' ]", " ", (text or "").lower()).split()


def copied_from_examples(key: str, text: str, run: int = 5) -> Optional[str]:
    """The first run of `run` words the piece shares with its example, if
    any. Station furniture ("this is H.N.F.M.", "the lines are open") is
    exempt: those are meant to recur."""
    run = min(run, 4) if key in ("joke", "sketch") else run
    furniture = _norm("this is h n f m and this is. h n f m is brought to you by nobody. the lines are open "
                      "line one. line two go ahead. line three go ahead. thank you both. this is the bulletin. "
                      "that is the bulletin on h n f m. the front page forecast. the word of the hour is. but if it "
                      "were it would be. good "
                      "morning good afternoon good evening")
    ours = {" ".join(furniture[i:i + 3]) for i in range(len(furniture) - 2)}
    theirs = set()
    for ex in _examples().get(key) or []:
        w = _norm(" ".join(l["text"] for l in ex.get("lines") or []))
        theirs |= {" ".join(w[i:i + run]) for i in range(len(w) - run + 1)}
    w = _norm(text)
    for i in range(len(w) - run + 1):
        gram = w[i:i + run]
        if " ".join(gram) not in theirs:
            continue
        # Shares three words in a row with the station's furniture: allowed.
        if any(" ".join(gram[k:k + 3]) in ours for k in range(run - 2)):
            continue
        return " ".join(gram)
    return None


def examples_for(key: str, limit: int = 1) -> str:
    """The worked example for a segment, as the writer prompt shows it."""
    pieces = (_examples().get(key) or [])[:limit]
    if not pieces:
        return "(no example for this kind of piece; follow the form)"
    import json

    out = []
    for ex in pieces:
        answer = {"plan": ex.get("plan") or {}, "lines": ex.get("lines") or []}
        out.append("EXAMPLE MATERIAL:\n" + (ex.get("material") or "").strip()
                   + "\nEXAMPLE ANSWER:\n" + json.dumps(answer, ensure_ascii=False))
    return "\n\n".join(out)


def draft(seg: Segment, *, show, speakers: Sequence[str], material: str,
          notes: Sequence[str] = (), usage: Optional[dict] = None):
    """One call to the writer. Returns (Copy, prompt version)."""
    from ..content.llm_service import LLMService
    from ..content.prompts import render

    note_block = ""
    if notes:
        note_block = "\nTHE EDITOR SENT YOUR LAST DRAFT BACK. Fix exactly these:\n" + \
            "\n".join(f"- {n}" for n in notes) + "\n"
    prompt = render(
        "radio.write", show_name=show.name, show_tone=show.tone, segment_name=seg.name,
        brief=seg.brief, form=seg.form, speakers=", ".join(speakers), words=seg.words,
        cast=briefing(speakers),
        material=(material or "(none)")[:6000],
        notes=note_block, examples=examples_for(seg.key),
    )
    svc = LLMService(task="radio.write")
    try:
        made = svc.generate_structured(prompt, copy_schema(speakers))
        return Copy.model_validate(made.model_dump()), prompt.version
    finally:
        if usage is not None:
            _add_usage(usage, svc)


def review(seg: Segment, material: str, copy: Copy, usage: Optional[dict] = None) -> Optional[Review]:
    """The editor's read, or None if the editor is away (the piece then
    stands on the rules alone)."""
    from ..content.llm_service import LLMService
    from ..content.prompts import render

    svc = LLMService(task="radio.edit")
    try:
        return svc.generate_structured(render(
            "radio.edit", segment_name=seg.name, brief=seg.brief, form=seg.form, words=seg.words,
            written=copy.words(), material=(material or "(none)")[:6000],
            piece=_render_piece(copy.lines),
        ), Review)
    except Exception as e:
        logger.warning(f"radio editor unavailable for {seg.key}: {e}")
        return None
    finally:
        if usage is not None:
            _add_usage(usage, svc)


def produce(seg: Segment, *, show, speakers: Sequence[str], material: str,
            earlier: Sequence[str] = (), earlier_openers: Sequence[str] = (),
            max_rewrites: int = 1) -> Optional[Piece]:
    # `earlier` is the full text of the pieces already made for this block.
    # It is never shown to the writer (it copied from it); it is what the
    # repair pass checks against.
    """Draft, check, edit, and rewrite at most `max_rewrites` times.

    A piece airs if the rules pass and the editor passes it (or is away).
    After the last rewrite a piece that still breaks only soft rules airs
    with its notes recorded; one with no usable lines does not.
    """
    usage = {"calls": 0, "tokens_in": 0, "tokens_out": 0}
    notes: List[str] = []
    drafts: List[Piece] = []
    never = [show.tone, *sheets(speakers)]
    for attempt in range(1, max_rewrites + 2):
        try:
            copy, version = draft(seg, show=show, speakers=speakers, material=material,
                                  notes=notes, usage=usage)
        except Exception as e:
            logger.warning(f"radio writer failed on {seg.key} (attempt {attempt}): {e}")
            break
        problems = lint(seg, copy, speakers, earlier_openers)
        rev = None
        if not problems and editor_on():
            rev = review(seg, material, copy, usage=usage)
        lines = _clean(copy, speakers)
        if lines:
            drafts.append(Piece(segment=seg.key, lines=lines, attempts=attempt, lint=problems, usage=usage,
                                review=None if rev is None else {
                                    **rev.scores(), "passes": rev.passes(), "heard": rev.heard,
                                    "unsupported": rev.unsupported[:3], "notes": rev.to_notes()},
                                plan=copy.plan.model_dump() if copy.plan else None,
                                prompt_version=version))
        if lines and not problems and (rev is None or rev.passes()):
            piece = drafts[-1]
            piece.lines = repair(seg, piece.lines, said_before=earlier, never=never)
            return piece if piece.lines else None
        notes = problems or (rev.to_notes() if rev else [])
        if not notes:
            notes = ["The editor did not pass this. Tighten the opening and check every claim against the material."]
    # Out of rewrites with the rules still unhappy: fix what can be fixed
    # by cutting, and check again. The newest draft that survives airs; a
    # rewrite is not always better than what it replaced (asked to stop
    # borrowing from the example, the model has handed back the example).
    for piece in reversed(drafts):
        piece.lines = repair(seg, piece.lines, said_before=earlier, never=never)
        if not piece.lines:
            continue
        fixed = Copy(lines=[Line(**l) for l in piece.lines])
        piece.lint = [n for n in lint(seg, fixed, speakers, earlier_openers) if not n.startswith("Too short")
                      or fixed.words() < seg.words * 0.35]
        piece.repaired = True
        if not any(n.startswith(HARD) for n in piece.lint):
            piece.attempts = len(drafts)
            return piece
    return None
