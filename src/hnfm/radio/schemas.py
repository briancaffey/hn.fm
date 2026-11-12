"""What the models are asked to return (structured output).

The shape of a block is not here: that is `format.py`, and it is code. The
models make three kinds of thing — an assignment of stories to slots, a
piece of copy, and a review of a piece — plus the lyrics of a song.
"""

from typing import List, Literal, Optional

from pydantic import BaseModel, Field

# Who can speak on air. The voice module maps each to an engine and a voice.
from .cast import ALL_MOODS as MOODS
from .cast import HOSTS  # noqa: F401

CALLERS = ("caller1", "caller2", "caller3")


class Pick(BaseModel):
    slot: int = Field(description="The slot number from SLOTS TO FILL.")
    story: int = Field(description="The story id from STORIES.")
    angle: str = Field(description="The hook for the writer, twenty words at most.")


class Picks(BaseModel):
    title: str = Field(description="A short name for this block.")
    picks: List[Pick]


class Plan(BaseModel):
    """What the writer decides before writing: thinking, at a fixed price.
    The local model cannot be given a thinking budget (it does not stop),
    so the plan is three short fields ahead of the lines instead."""

    hook: str = Field(description="The single most concrete, surprising thing in the material.")
    facts: List[str] = Field(description="Two to four facts from the material that the piece will use.")
    ending: str = Field(description="The last line.")


class Line(BaseModel):
    speaker: str = Field(description="One of the speakers the assignment allows.")
    mood: str = Field(default="default", description="One of the moods this speaker has.")
    text: str = Field(description="Only the words spoken.")


class Copy(BaseModel):
    plan: Optional[Plan] = None
    lines: List[Line]

    def words(self) -> int:
        return sum(len(l.text.split()) for l in self.lines)

    def spoken(self) -> str:
        return " ".join(l.text.strip() for l in self.lines)


def copy_schema(speakers):
    """`Copy`, with `speaker` and `mood` narrowed to what this piece may
    use. Constrained decoding then cannot hand a line to a host who is not
    in the piece, which a prompt can only ask for."""
    from pydantic import create_model

    speaker_t = Literal[tuple(speakers)]  # type: ignore[valid-type]
    mood_t = Literal[MOODS]  # type: ignore[valid-type]
    line = create_model("Line", speaker=(speaker_t, ...), mood=(mood_t, ...), text=(str, ...))
    return create_model("Copy", plan=(Plan, ...), lines=(List[line], ...))


class Review(BaseModel):
    # Observations before scores: the editor says what it heard and what
    # it could not find in the material, and only then puts numbers on it.
    heard: str = Field(description="One sentence: what a listener would take away.")
    unsupported: List[str] = Field(
        default_factory=list,
        description="Every claim, number, name or quote in the piece that is NOT in the material. Empty if none.")
    recited: List[str] = Field(
        default_factory=list,
        description="Any words of the assignment read out on air ('the hook is', 'the tension'). Empty if none.")
    hook: int = Field(ge=1, le=5)
    clarity: int = Field(ge=1, le=5)
    faithful: int = Field(ge=1, le=5)
    speakable: int = Field(ge=1, le=5)
    voice: int = Field(ge=1, le=5)
    notes: List[str] = Field(default_factory=list, description="At most three instructions for the writer.")

    def scores(self) -> dict:
        return {k: getattr(self, k) for k in ("hook", "clarity", "faithful", "speakable", "voice")}

    def passes(self) -> bool:
        """The bar is applied here, not by the model: every score at least
        three, faithful at least four, nothing unsupported, nothing recited."""
        s = self.scores()
        return min(s.values()) >= 3 and s["faithful"] >= 4 and not self.unsupported and not self.recited

    def to_notes(self) -> List[str]:
        out = [f"Not in the material, cut it: {u}" for u in self.unsupported[:2]]
        out += [f'Never say the assignment\'s words on air: "{r}"' for r in self.recited[:1]]
        return (out + list(self.notes))[:4]


class Lyrics(BaseModel):
    title: str = Field(description="The song's name, four words at most.")
    style: str = Field(description="Comma-separated style tags for the music model.")
    lyrics: str = Field(description="Lyrics with [verse] and [chorus] marks on their own lines.")
