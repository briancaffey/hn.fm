"""The cast: who is on the station, and what each of them is like (issue #41).

Six hosts, three correspondents, an announcer, and callers. A character is
a voice, a role and a sheet. The sheet is what the writer is told about
how the person talks. It is given to the writer only for the people in
the piece, and it is short and about manner on purpose: the local model
reads a description of a person back out as copy ("she counts that among
the small clever things that delight her", of a story about an assault),
so a sheet says how to speak, never what the person is like inside, and
any sentence that shares four words in a row with a sheet is cut before
the booth (writers.repair).

The role decides how the voice is treated in the mix (fx.py): hosts sit in
the studio, correspondents are on a line from somewhere else, callers are
on the phone, the announcer is the station's big voice.

Moods are the sub-voices the speech model has for that speaker. They are
not the same for everyone: only Jason can sound happy, only Ray and Sofia
fearful. Measured on the model (evals/radio_voices.py): calm runs 40 to 90
per cent slower than the plain voice; neutral is flatter and lower; angry
and sad are large changes. A mood a character does not have is put back
to "default" in code, so the writer cannot ask for a voice that is not
there.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

_V = "Magpie-Multilingual."


@dataclass(frozen=True)
class Character:
    key: str
    name: str                 # as said on air
    voice: str                # the speech model's voice
    role: str                 # host, correspondent, announcer
    line: str                 # one line, for listings and the listen page
    sheet: str                # for the writer; never read out
    moods: Tuple[str, ...]    # besides "default"
    beat: str = ""            # a correspondent's patch


_C = Character

CAST: Dict[str, Character] = {c.key: c for c in (
    _C("mia", "Mia", _V + "EN-US.Mia", "host",
       "Warm and quick. Delighted by small clever things.",
       "Quick and warm, in short sentences. Likes a count: three steps, one weekend. On a light story may begin with Okay. On a serious story, plain and quiet. Never cynical.",
       ("calm", "neutral", "sad", "angry")),
    _C("leo", "Leo", _V + "EN-US.Leo", "host",
       "Deadpan. Gets the dry line, and the last word.",
       "Deadpan. The shortest sentences on the station. No exclamations and no enthusiasm. Disagrees by stating one fact and stopping.",
       ("calm", "neutral", "sad", "angry")),
    _C("sofia", "Sofia", _V + "EN-US.Sofia", "host",
       "Exact and brisk. A newsreader who leads with the number.",
       "A newsreader. Leads with the number or the name, then what happened, then what is not known. No adjective that is not needed. At most one dry aside, and it comes last.",
       ("neutral", "calm", "fearful", "angry")),
    _C("jason", "Jason", _V + "EN-US.Jason", "host",
       "Low and unhurried. Has seen this one before.",
       "Unhurried and understated, in short plain words. Wants to know who pays and who maintains it. Glad, briefly, when something really works.",
       ("happy", "calm", "neutral", "angry")),
    _C("aria", "Aria", _V + "EN-US.Aria", "host",
       "Clear and even. Explains how the thing actually works.",
       "Explains the mechanism in the order it happens. At most one everyday comparison. Even and patient.",
       ("calm", "neutral", "sad", "angry")),
    _C("ray", "Ray", _V + "EN-US.Ray", "host",
       "Deep and slow. Takes the long view, late at night.",
       "Slow and plain. Takes the long view: what will still matter in ten years. Kind about people who make things. Ends quietly.",
       ("calm", "neutral", "fearful", "angry")),
    # --- correspondents: on a line from outside the studio ------------------
    _C("kit", "Kit", _V + "VI-VN.Long", "correspondent",
       "At the workbench. Reports on what people built.",
       "The reporter on things people made. Says what it is, what you notice first, and the one clever part. Reports; does not review.",
       (), beat="what people built"),
    _C("robin", "Robin", _V + "KO-KR.Phung", "correspondent",
       "Live from the comment section.",
       "Reports from the comment thread as if from a crowded room: what the argument is and which side is louder. Never names anyone, never takes a side.",
       (), beat="the argument in the thread"),
    _C("sam", "Sam", _V + "HI-IN.HouZhen", "correspondent",
       "Down in the machine room. Outages, chips and plumbing.",
       "Covers the machinery: servers, chips, networks. Calm about failure. Says what broke or changed in plain words, and what it costs.",
       (), beat="infrastructure and how it fails"),
    # --- imaging -----------------------------------------------------------
    _C("announcer", "The announcer", _V + "EN-US.Diego", "announcer",
       "The station's big voice, on the sweepers.",
       "The announcer says the station's name and the show's, and nothing else.", ()),
)}

HOSTS: Tuple[str, ...] = tuple(k for k, c in CAST.items() if c.role == "host")
CORRESPONDENTS: Tuple[str, ...] = tuple(k for k, c in CAST.items() if c.role == "correspondent")
ALL_MOODS: Tuple[str, ...] = ("default", "neutral", "calm", "happy", "fearful", "sad", "angry")

# What each mood does to a voice, as the writer is told.
MOOD_NOTES = {
    "default": "the natural voice; nearly every line",
    "neutral": "flatter and lower; a straight news read",
    "calm": "much slower; one quiet closing line at most",
    "happy": "bright; real delight, once",
    "fearful": "tight and quick; mock alarm, once",
    "sad": "a big change; only for a line that is truly that",
    "angry": "a big change; only for a line that is truly that",
}

# Callers are voices no host or correspondent uses. The same speakers come
# in several accents; the pool is ordered so that any three in a row are
# three different people.
CALLER_VOICES: Tuple[str, ...] = tuple(_V + v for v in (
    "EN-US.Diego", "EN-US.Isabela", "EN-US.Pascal", "EN-US.Louise",
    "DE-DE.Diego", "ES-US.Isabela", "FR-FR.Pascal", "JA-JP.Louise",
    "PT-BR.Diego", "IT-IT.Isabela", "HI-IN.Pascal", "FR-FR.Louise",
))


def is_caller(speaker: str) -> bool:
    return (speaker or "").startswith("caller")


def character(key: str) -> Optional[Character]:
    return CAST.get(key)


def role_of(speaker: str) -> str:
    """How a speaker's voice is treated: a key of fx.TREATMENTS."""
    if is_caller(speaker):
        return "phone"
    c = CAST.get(speaker)
    return {"correspondent": "field", "announcer": "big"}.get(c.role if c else "", "studio")


def moods_for(speaker: str) -> Tuple[str, ...]:
    if is_caller(speaker):
        return ("default",)
    c = CAST.get(speaker)
    return ("default",) + (c.moods if c else ())


def mood_or_default(speaker: str, mood: Optional[str]) -> str:
    m = (mood or "default").strip().lower()
    return m if m in moods_for(speaker) else "default"


def briefing(speakers: Sequence[str]) -> str:
    """Who is in the piece, for the writer: each person's sheet and the
    moods that person has."""
    out: List[str] = []
    callers = [s for s in speakers if is_caller(s)]
    for s in speakers:
        c = CAST.get(s)
        if not c:
            continue
        moods = "; ".join(f"{m} ({MOOD_NOTES[m]})" for m in moods_for(s))
        said = f' Called "{c.name}" on air.' if c.role == "correspondent" else ""
        out.append(f"- {s}: {c.sheet}{said}\n  Moods {s} can use: {moods}.")
    if callers:
        out.append(f"- {', '.join(callers)}: listeners on the phone. Plain, slightly hesitant speech, "
                   "one point each, never named. Mood: default.")
    return "\n".join(out)


def sheets(speakers: Sequence[str]) -> List[str]:
    """The sheets of the people in a piece: direction, which must never be
    heard on air."""
    return [CAST[s].sheet for s in speakers if s in CAST]


def listing() -> List[dict]:
    """The cast, for the listen page and the desk."""
    return [{"key": c.key, "name": c.name, "role": c.role, "line": c.line, "beat": c.beat,
             "moods": list(moods_for(c.key))} for c in CAST.values()]
