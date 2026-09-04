"""Source-specific extraction for links firecrawl cannot read (issue #17).

Firecrawl returns empty markdown for YouTube and HTTP 500 for PDFs. Both are
common on HN, and a PDF usually carries the most substantive content of any
link on the front page — one observed failure was an Anthropic system card,
which is exactly the kind of source this pipeline wants.

Neither of these is a third-party data service standing in for the source:
the PDF reader is entirely local, and the transcript reader fetches the same
youtube.com URL the story already points at. They are parsers, not middlemen.
"""

import io
import logging
import re
import urllib.parse
from typing import Optional

logger = logging.getLogger(__name__)

# Matches watch URLs, youtu.be short links, /embed/ and /shorts/.
_YOUTUBE_HOSTS = {
    "youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be", "www.youtu.be",
}

# Large PDFs are usually scanned scholarship with no text layer; the download
# cost is real and the yield is zero.
MAX_PDF_BYTES = 25 * 1024 * 1024
PDF_TIMEOUT_SECONDS = 30

# `summarize_text_v1` passes its whole input to the LLM with no truncation, so
# an unbounded extract would blow the context window: the Anthropic system card
# that motivated this handler yields 478,824 characters, roughly 120k tokens.
# Real article scrapes average ~18k chars and top out near 39k, so this is
# generous for anything the summariser can actually use. Applies to transcripts
# too — a three-hour talk runs long.
MAX_EXTRACT_CHARS = 60_000


def _capped(text: str, url: str) -> str:
    if len(text) <= MAX_EXTRACT_CHARS:
        return text
    logger.info(
        f"Truncating {len(text)} char extract from {url} to {MAX_EXTRACT_CHARS}"
    )
    return text[:MAX_EXTRACT_CHARS].rsplit(" ", 1)[0] + " […truncated]"


def _host(url: str) -> str:
    try:
        return (urllib.parse.urlparse(url).hostname or "").lower()
    except Exception:
        return ""


def youtube_video_id(url: str) -> Optional[str]:
    """The video id, or None if this is not a YouTube link."""
    host = _host(url)
    if host not in _YOUTUBE_HOSTS:
        return None
    try:
        parsed = urllib.parse.urlparse(url)
    except Exception:
        return None

    if host in ("youtu.be", "www.youtu.be"):
        vid = parsed.path.lstrip("/").split("/")[0]
        return vid or None

    if parsed.path.startswith(("/embed/", "/shorts/", "/live/")):
        vid = parsed.path.split("/")[2] if len(parsed.path.split("/")) > 2 else ""
        return vid or None

    vid = urllib.parse.parse_qs(parsed.query or "").get("v", [None])[0]
    return vid or None


def looks_like_pdf(url: str, content_type: str = "") -> bool:
    if "pdf" in (content_type or "").lower():
        return True
    path = urllib.parse.urlparse(url).path.lower() if url else ""
    return path.endswith(".pdf")


def fetch_youtube_transcript(url: str) -> Optional[str]:
    """The video's transcript as plain text, or None.

    Never raises: a missing transcript is an ordinary outcome (many videos have
    none) and must fall through to the normal scrape path, not fail the run.
    """
    vid = youtube_video_id(url)
    if not vid:
        return None
    try:
        from youtube_transcript_api import YouTubeTranscriptApi

        entries = YouTubeTranscriptApi().fetch(vid)
        text = " ".join(
            (getattr(e, "text", None) or e.get("text", "")).strip()
            for e in entries
        )
        text = re.sub(r"\s+", " ", text).strip()
        if not text:
            return None
        logger.info(f"📺 YouTube transcript: {len(text)} chars for {vid}")
        return _capped(text, url)
    except Exception as e:
        logger.info(f"No YouTube transcript for {vid}: {e}")
        return None


def fetch_pdf_text(url: str) -> Optional[str]:
    """Extracted PDF body text, or None. Never raises, same reasoning."""
    try:
        import requests
        from pypdf import PdfReader

        resp = requests.get(url, timeout=PDF_TIMEOUT_SECONDS, stream=True)
        resp.raise_for_status()

        if not looks_like_pdf(url, resp.headers.get("content-type", "")):
            return None

        size = int(resp.headers.get("content-length") or 0)
        if size and size > MAX_PDF_BYTES:
            logger.info(f"Skipping {size} byte PDF at {url} (over the cap)")
            return None

        raw = resp.content[:MAX_PDF_BYTES]
        reader = PdfReader(io.BytesIO(raw))
        text = "\n\n".join((page.extract_text() or "") for page in reader.pages)
        text = re.sub(r"\n{3,}", "\n\n", text).strip()
        if not text:
            # A scan with no text layer. Nothing here to read.
            logger.info(f"PDF at {url} has no extractable text layer")
            return None
        logger.info(f"📄 PDF text: {len(text)} chars from {len(reader.pages)} pages")
        return _capped(text, url)
    except Exception as e:
        logger.info(f"PDF extraction failed for {url}: {e}")
        return None


def extract(url: str) -> tuple[Optional[str], Optional[str]]:
    """`(content, source)` from a source-specific handler, or `(None, None)`.

    Tried BEFORE firecrawl, because for these two firecrawl is not a fallback
    worth waiting for — it fails deterministically on both.
    """
    if youtube_video_id(url):
        text = fetch_youtube_transcript(url)
        if text:
            return text, "youtube_transcript"
    if looks_like_pdf(url):
        text = fetch_pdf_text(url)
        if text:
            return text, "pdf"
    return None, None
