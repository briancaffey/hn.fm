"""Readable output — the same stories hn.fm narrates, typeset to read.

The pipeline's product is a video; this is the other half. Nothing here
re-derives content: a digest is a *rendering* of Story Briefs that triage and
`build_story_brief` already produced, so generating one costs no LLM calls and
cannot invent a claim the brief does not contain.

    select.py   which stories go in (ranked, same order as the triage queue)
    render.py   brief -> HTML (browser, and Send-to-Kindle) and EPUB (Kindle)
    deliver.py  email the file to a Send-to-Kindle address
"""

from .select import select_stories, Digest  # noqa: F401
from .render import render_html, write_epub  # noqa: F401
