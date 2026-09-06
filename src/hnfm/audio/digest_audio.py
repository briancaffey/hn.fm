"""A narrated edition: several stories as one continuous listen.

Segment audio answers "tell me about this story". This answers "read me the
digest" — the same editorial shape the Kindle edition has (an opening, quick
hits, a feature, a close), voiced as one episode with the stories separated
audibly rather than by a heading you cannot see while driving.

Built on the same TTS path as segments so voices, cleaning and stitching stay
identical; what is new is the script that spans stories rather than sitting
inside one.
"""

import logging
import os
from typing import List, Optional

logger = logging.getLogger(__name__)

# A short pause between spoken items, so the listener hears the seam. Longer
# than the gap between speaker turns (180ms) and shorter than a track change.
STORY_GAP_MS = int(os.getenv("DIGEST_AUDIO_GAP_MS", "900"))
SECTION_GAP_MS = int(os.getenv("DIGEST_AUDIO_SECTION_GAP_MS", "350"))


# Magpie returns audio over gRPC with a 4 MB response cap. At 22050 Hz,
# 16-bit mono that is roughly 95 seconds — about 350 words — and the request
# fails outright above it ("Received message larger than max"). Script lines
# are short so segments never hit this; digest sections are 350-500 words and
# hit it every time. Chunk well under, on sentence boundaries.
MAX_WORDS_PER_CALL = 170


def chunk_for_tts(text: str, max_words: int = MAX_WORDS_PER_CALL) -> List[str]:
    """Split prose into TTS-sized pieces without cutting a sentence.

    Mid-sentence splits are audible — the voice drops its intonation contour at
    the break — so a slightly uneven chunk is better than a clean word count.
    """
    import re

    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text or "") if s.strip()]
    chunks, current, count = [], [], 0
    for sent in sentences:
        n = len(sent.split())
        if current and count + n > max_words:
            chunks.append(" ".join(current))
            current, count = [sent], n
        else:
            current.append(sent)
            count += n
    if current:
        chunks.append(" ".join(current))
    return chunks or ([text] if text else [])


def _silence(ms: int, sample_rate: int = 22050) -> bytes:
    """Raw PCM silence, matching what the TTS backend returns."""
    return b"\x00\x00" * int(sample_rate * ms / 1000)


def build_audio_digest(
    sections,
    out_path: str,
    voice_seed: int = 0,
) -> dict:
    """Voice a composed edition end to end.

    `sections` are the same `compose.Section` objects the Kindle edition is
    typeset from, so the audio and the document say the same thing — the
    alternative, a separate audio script, drifts from the written edition
    within a week.
    """
    from .audio_utils import tts_synthesize_to_wav
    from ..utils.segment_utils import _clean_script_for_tts

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    parts: List[str] = []
    marks: List[dict] = []
    voices = None

    tmp_dir = os.path.join(os.path.dirname(out_path), "_parts")
    os.makedirs(tmp_dir, exist_ok=True)

    elapsed_ms = 0
    for i, sec in enumerate(sections):
        body = (sec.body or "").strip()
        if not body:
            continue
        # The written edition uses headings; a listener needs them spoken, and
        # only for the items that are actually separate stories.
        spoken = body if sec.kind == "teaser" else f"{sec.title}. {body}"
        spoken = _clean_script_for_tts(spoken)

        # One voice per item, alternating between stories: it reads like two
        # presenters trading pieces rather than one long monologue, and it
        # uses the voice variety the segments already have.
        seed = voice_seed + (0 if sec.kind == "teaser" else i)
        dur = 0
        chunk_paths = []
        for j, chunk in enumerate(chunk_for_tts(spoken)):
            part = os.path.join(tmp_dir, f"{i:02d}_{j:02d}.wav")
            try:
                dur += tts_synthesize_to_wav(chunk, part, voice_seed=seed)
                chunk_paths.append(part)
            except Exception as e:
                logger.warning(
                    f"audio digest: section {i} chunk {j} failed ({e}); skipping"
                )
        if not chunk_paths:
            logger.warning(f"audio digest: section {i} produced nothing; skipping")
            continue
        voices = getattr(tts_synthesize_to_wav, "last_voices", voices)
        marks.append({
            "at_ms": elapsed_ms,
            "kind": sec.kind,
            "title": sec.title or "Opening",
            "story_id": sec.story_id,
        })
        elapsed_ms += dur + (STORY_GAP_MS if sec.kind != "teaser" else SECTION_GAP_MS)
        parts.extend(chunk_paths)

    if not parts:
        raise RuntimeError("audio digest: no sections were voiced")

    _concat(parts, out_path)
    return {
        "path": out_path,
        "sections": len(parts),
        "duration_ms": elapsed_ms,
        "marks": marks,
        "voices": voices,
    }


def _concat(parts: List[str], out_path: str) -> None:
    """Join the parts with ffmpeg.

    A concat demuxer list rather than the filter graph: the inputs are already
    identical in rate and channel count, so re-encoding them would cost time
    and quality for nothing.
    """
    import subprocess
    import tempfile

    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as f:
        for p in parts:
            f.write(f"file '{p}'\n")
        listing = f.name
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", listing,
             "-c", "copy", out_path],
            check=True, capture_output=True, timeout=600,
        )
    except subprocess.CalledProcessError as e:
        # `-c copy` fails when the parts disagree; re-encode rather than lose
        # the episode.
        logger.info(f"audio digest: stream copy failed, re-encoding ({e})")
        subprocess.run(
            ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", listing,
             "-ar", "22050", "-ac", "1", out_path],
            check=True, capture_output=True, timeout=900,
        )
    finally:
        os.unlink(listing)
