"""What the producer plans and the director serves (plans/20).

A run sheet is a block of programming: an ordered list of items, each of one
kind. The producer (an LLM, or the deterministic fallback) writes one; the
director hands its items to Liquidsoap one at a time.
"""

from typing import List, Literal, Optional

from pydantic import BaseModel, Field

Kind = Literal["station_id", "episode", "coming_up", "music", "time_check"]

# Who can speak on air. Keys are what the producer chooses between; the
# voice module maps them to an engine and a voice.
HOSTS = ("mia", "jason", "sofia", "leo", "dia")


class RunItem(BaseModel):
    kind: Kind
    # For an episode: "item:run:seg" from the library listing.
    episode: Optional[str] = Field(default=None, description='"item:run:seg" for kind=episode, else null.')
    host: Optional[str] = Field(default=None, description="Who speaks, for station_id / coming_up / time_check.")
    line: Optional[str] = Field(default=None, description="What they say, at most 25 words. Null for episode and music.")
    music_style: Optional[str] = Field(default=None, description="A short style brief for kind=music, e.g. 'warm lo-fi piano, 70 bpm'.")
    seconds: Optional[int] = Field(default=None, description="For music only: 45-90.")


class RunSheet(BaseModel):
    title: str = Field(description="A name for this block, like a show segment title.")
    items: List[RunItem]
