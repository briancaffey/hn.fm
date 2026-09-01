"""Utilities for managing script segments"""

import json
import os
import shutil
from pathlib import Path
from typing import Optional, List

from ..db import repo
from ..web.models import Segment


def k_seg(item_id: int, run: int, seg: int) -> str:
    """Legacy entity key string (kept on the Pydantic models / API responses)"""
    return f"hnfm:seg:{item_id}:{run}:{seg}"


def k_img(item_id: int, run: int, seg: int, index: int) -> str:
    """Legacy entity key string for a segment image"""
    return f"hnfm:seg:{item_id}:{run}:{seg}:img:{index}"


def seg_dir(outputs_root: str, item_id: int, run: int, seg: int) -> str:
    """Generate disk directory path for a segment"""
    return f"{outputs_root}/hn/item/{item_id}/runs/{run}/segments/{seg}"


def asr_json_path(outputs_root: str, item_id: int, run: int, seg: int) -> str:
    """Generate path for ASR JSON file"""
    return f"{outputs_root}/hn/item/{item_id}/runs/{run}/segments/{seg}/audio/asr.json"


def seg_root(outputs_root: str, item_id: int, run: int, seg: int) -> str:
    """Generate root directory path for a segment (same as seg_dir)"""
    return seg_dir(outputs_root, item_id, run, seg)


def img_dir(outputs_root: str, item_id: int, run: int, seg: int, index: int) -> str:
    """Generate directory path for a segment image"""
    return f"{outputs_root}/hn/item/{item_id}/runs/{run}/segments/{seg}/images/{index}"


def img_path(outputs_root: str, item_id: int, run: int, seg: int, index: int) -> str:
    """Generate path for segment image file"""
    return f"{img_dir(outputs_root, item_id, run, seg, index)}/image.png"


def img_meta_path(
    outputs_root: str, item_id: int, run: int, seg: int, index: int
) -> str:
    """Generate path for segment image metadata file"""
    return f"{img_dir(outputs_root, item_id, run, seg, index)}/meta.json"


def video_dir(outputs_root: str, item_id: int, run: int, seg: int) -> str:
    """Generate directory path for segment video files"""
    return f"{outputs_root}/hn/item/{item_id}/runs/{run}/segments/{seg}/video"


def video_path(outputs_root: str, item_id: int, run: int, seg: int) -> str:
    """Generate path for segment video file"""
    return f"{video_dir(outputs_root, item_id, run, seg)}/segment.mp4"


def subtitles_path(outputs_root: str, item_id: int, run: int, seg: int) -> str:
    """Generate path for segment subtitles VTT file"""
    return f"{video_dir(outputs_root, item_id, run, seg)}/captions.vtt"


def timeline_path(outputs_root: str, item_id: int, run: int, seg: int) -> str:
    """Generate path for segment timeline debug JSON file"""
    return f"{video_dir(outputs_root, item_id, run, seg)}/timeline.json"


def write_json(path: str, data: dict) -> None:
    """Write JSON data to file with proper directory creation"""
    path_obj = Path(path)
    path_obj.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def _clean_script_for_tts(script: str) -> str:
    """
    Clean script text for better TTS results.

    Belt-and-braces: the script schema forbids markdown, but this text is read
    aloud by a synthetic voice, and a stray `**` is narrated as "asterisk
    asterisk". A prior run emitted `**[S1]**`, which also broke the speaker-tag
    parser downstream — so the guard stays even now that the contract is
    enforced upstream.

    Args:
        script: Raw script text from LLM

    Returns:
        Cleaned script text with TTS-friendly characters
    """
    replacements = {
        ord("“"): '"',
        ord("”"): '"',
        ord("‘"): "'",
        ord("’"): "'",
        ord("—"): ", ",
        ord("–"): ", ",
        # ord('\n\n'): '\n',
        ord("…"): ", ",
        ord("`"): "",
        ord("_"): " ",
        ord("*"): None,  # markdown emphasis -> spoken as "asterisk"
        ord("#"): None,  # markdown headers
    }

    script = script.replace("\n\n", "\n")

    script = script.translate(replacements)

    return script


def next_seg_id(item_id: int, run: int) -> int:
    """Get next segment ID atomically"""
    return repo.next_counter(f"seg:{item_id}:{run}")


def generate_script_v1(content_clean: str, summary: str) -> str:
    """Flat `[S1] …` script text. Thin wrapper over `generate_script()` for
    callers that only want the rendered view."""
    return generate_script(content_clean, summary).to_script_text()


def generate_script(content_clean: str, summary: str) -> "Script":
    """Generate the structured script for a segment (plans/08, plans/11).

    Returns a `content.llm_schemas.Script`: writer-chosen sections, each with a
    speaker, a narrative beat and a `visual_intent`. The section boundaries are
    the point — they become both the TTS chunks and the visual beats, so the
    writer decides pacing instead of the old every-two-lines splitter.

    Raises RuntimeError on failure. A script is not optional: silently
    returning placeholder text here is what previously sent the pipeline on to
    spend GPU time rendering a one-line error string.
    """
    from ..content.llm_service import LLMService, LLMError
    from ..content.llm_schemas import Script
    from ..content.prompts import render
    from ..utils.config import config_manager

    show = config_manager.get("show", {}) or {}
    prompt = render(
        "script.write",
        show_name=show.get("name") or "hn.fm",
        summary=summary or "",
        content=content_clean or "",
    )

    try:
        script = LLMService(task="script.write").generate_structured(prompt, Script)
    except LLMError as e:
        raise RuntimeError(f"Failed to generate script: {e}") from e

    if not script.sections:
        raise RuntimeError("Failed to generate script: no sections returned")

    # The schema constrains structure; this scrubs the characters that make TTS
    # mispronounce (smart quotes, em dashes, stray markdown).
    for section in script.sections:
        section.text = _clean_script_for_tts(section.text).strip()

    script.sections = [s for s in script.sections if s.text]
    if not script.sections:
        raise RuntimeError("Failed to generate script: all sections were empty")

    # Renumber after the empty-section drop so indexes stay contiguous — they
    # key the audio sections, images and media plan downstream.
    for i, section in enumerate(script.sections, start=1):
        section.index = i

    _normalize_beats(script)
    return script


# Phrases that narrate the PIPELINE's limitations rather than the story ("the
# article doesn't say", "based on the information provided"). The prompt forbids
# these; a thin source makes the model do it anyway. Detected rather than
# rewritten — mechanically editing spoken sentences produces broken grammar, and
# the honest signal is more useful than a silent patch.
_GAP_NARRATION = (
    "not disclosed", "not specified", "isn't specified", "is not specified",
    "aren't disclosed", "are not disclosed", "not detailed", "isn't detailed",
    "doesn't say", "does not say", "doesn't mention", "does not mention",
    "the article doesn't", "the article does not", "the source doesn't",
    "information provided", "provided information", "isn't clear from",
    "not available in", "unspecified",
)

# Things an image generator cannot render, or that are editing directions
# rather than scenes. A visual_intent containing one of these is worse than no
# intent at all: it steers the art director toward screenshots and UI chrome.
_UNDEPICTABLE = (
    "screenshot", "website", "web page", "webpage", "url", ".org", ".com",
    "split screen", "split-screen", "timeline graphic", "logo", "user interface",
    "ui ", "dashboard", "chart", "graph showing", "infographic", "text overlay",
    "sign reading", "placeholder", "question mark over", "if existed",
    "caption", "subtitle", "title card",
)


def script_quality_flags(script: "Script") -> List[dict]:
    """Deterministic defects in a generated script.

    Recorded on the script step so they surface in the X-ray UI and feed
    plan 14's quality gate. These are the failures a prompt cannot reliably
    prevent but code can reliably detect.
    """
    flags = []

    gap_sections = [
        s.index
        for s in script.sections
        if any(p in s.text.lower() for p in _GAP_NARRATION)
    ]
    if gap_sections:
        flags.append({"flag": "gap_narration", "sections": gap_sections})

    undepictable = [
        s.index
        for s in script.sections
        if any(p in (s.visual_intent or "").lower() for p in _UNDEPICTABLE)
    ]
    if undepictable:
        flags.append({"flag": "undepictable_visual_intent", "sections": undepictable})

    speakers = [s.speaker for s in script.sections]
    if len(speakers) >= 6 and all(
        speakers[i] != speakers[i + 1] for i in range(len(speakers) - 1)
    ):
        # Strict ping-pong is the exact monotony the new prompt set out to kill.
        flags.append({"flag": "strict_alternation", "sections": []})

    return flags


def _usable_visual_intent(intent: str) -> str:
    """A visual intent, or "" if it would poison the image prompt.

    Falling back to no intent restores the pre-plans/08 behaviour (scene
    inferred from the spoken line), which is strictly better than steering the
    art director toward a screenshot it cannot draw.
    """
    if not intent:
        return ""
    return "" if any(p in intent.lower() for p in _UNDEPICTABLE) else intent


def _normalize_beats(script: "Script") -> None:
    """Enforce beat structure the schema can't express.

    An enum guarantees each beat is a *valid* value, not that the sequence is
    coherent. A live run produced three sections labelled `close`, two of them
    mid-script. Beats drive pacing and (from plans/13) shot grammar, so a
    `close` in the middle would tell the art director to land the piece twice.

    Mislabelled middles become `detail`; the first and last sections are
    pinned. Logged, because a model that keeps mislabelling is a prompt bug.
    """
    import logging

    log = logging.getLogger(__name__)
    sections = script.sections
    last = len(sections) - 1

    for i, section in enumerate(sections):
        if i == 0:
            if section.beat != "cold_open":
                log.info(f"beat fix: §1 {section.beat!r} -> 'cold_open'")
                section.beat = "cold_open"
        elif i == last:
            if section.beat != "close":
                log.info(f"beat fix: §{i + 1} {section.beat!r} -> 'close' (final)")
                section.beat = "close"
        elif section.beat in ("cold_open", "close"):
            log.info(f"beat fix: §{i + 1} {section.beat!r} -> 'detail' (mid-script)")
            section.beat = "detail"


def sections_for_segment(segment: Segment) -> List[str]:
    """The segment's narration sections, as `["[S1] …", "[S2] …"]`.

    THE place section boundaries are decided. Prefers the structured script,
    where the writer chose the breaks on meaning; falls back to the legacy
    every-two-lines splitter for segments written before plans/08.

    Same wire format either way, so every consumer (TTS, images, media plan)
    is unchanged — only the quality of the boundaries improves.
    """
    from ..audio.audio_utils import split_script_into_sections

    if segment.script_json:
        try:
            from ..content.llm_schemas import Script

            return Script.model_validate(segment.script_json).to_tts_sections()
        except Exception as e:
            # A malformed stored script must not strand the segment: the flat
            # text is still there and still splittable.
            import logging

            logging.getLogger(__name__).warning(
                f"script_json unreadable for seg {segment.item_id}:{segment.run}:"
                f"{segment.seg} ({e}); falling back to the legacy splitter"
            )
    return split_script_into_sections(segment.script)


def visual_intents_for_segment(segment: Segment) -> List[str]:
    """Per-section `visual_intent` from the structured script, aligned with
    `sections_for_segment`. Empty strings when unavailable (legacy segments),
    so callers can zip without length checks."""
    if segment.script_json:
        try:
            from ..content.llm_schemas import Script

            return [
                _usable_visual_intent(s.visual_intent or "")
                for s in Script.model_validate(segment.script_json).sections
            ]
        except Exception:
            pass
    return [""] * len(sections_for_segment(segment))


def save_segment(seg_obj: Segment, *, outputs_root: str) -> None:
    """
    Save segment to Postgres and disk.

    Args:
        seg_obj: Segment object to save
        outputs_root: Root outputs directory
    """
    # Save to Postgres
    repo.save_segment(seg_obj)

    # Save to disk
    seg_path = seg_dir(outputs_root, seg_obj.item_id, seg_obj.run, seg_obj.seg)
    Path(seg_path).mkdir(parents=True, exist_ok=True)

    segment_file = os.path.join(seg_path, "segment.json")
    with open(segment_file, "w", encoding="utf-8") as f:
        f.write(seg_obj.model_dump_json())


def get_segment(item_id: int, run: int, seg: int) -> Optional[Segment]:
    """
    Get segment from Postgres.

    Returns:
        Segment object or None if not found
    """
    return repo.get_segment(item_id, run, seg)


def list_segments_for_run(
    item_id: int, run: int, *, offset: int = 0, limit: int = 20
) -> List[int]:
    """
    List segment IDs for a run (newest-first).

    Returns:
        List of segment IDs
    """
    return repo.list_seg_numbers(item_id, run, offset=offset, limit=limit)


def list_all_segments(*, offset: int = 0, limit: int = 50) -> List[Segment]:
    """
    List all segments across all items and runs (newest-first).

    Returns:
        List of Segment objects
    """
    segments, _total = repo.list_all_segments(offset=offset, limit=limit)
    return segments


def count_all_segments() -> int:
    """Total number of segments across all items and runs."""
    _segments, total = repo.list_all_segments(offset=0, limit=0)
    return total


def delete_segment(item_id: int, run: int, seg: int, *, outputs_root: str) -> bool:
    """
    Delete segment from Postgres (sections/images cascade) and disk.

    Returns:
        True if segment was deleted, False if not found
    """
    if not repo.delete_segment_row(item_id, run, seg):
        return False

    # Delete from disk
    seg_path = seg_dir(outputs_root, item_id, run, seg)
    if os.path.exists(seg_path):
        shutil.rmtree(seg_path)

    return True


def alignment_from_sections(
    item_id: int, run: int, seg: int
) -> Optional[List[tuple[int, int]]]:
    """
    If narration sections exist: compute [(start_ms, duration_ms), ...] in index order.
    start_ms is cumulative sum of previous durations.
    Return None if sections missing.
    """
    try:
        alignments = []
        cumulative_start = 0

        for section_num in repo.list_section_numbers(item_id, run, seg):
            section = repo.get_section(item_id, run, seg, section_num)
            if not section or section.duration_ms is None:
                continue
            alignments.append((cumulative_start, section.duration_ms))
            cumulative_start += section.duration_ms

        return alignments if alignments else None

    except Exception:
        return None


def generate_image_prompt_v1(
    line_text: str,
    run_summary: str,
    theme=None,
    shot_hint: str = "",
    visual_intent: str = "",
) -> str:
    """Write a vivid SCENE for one section, then apply the take's visual THEME.

    The LLM invents the scene (subject/action/composition/shot) but does NOT pick
    an art style — the theme's style block is appended deterministically so every
    shot in a take is stylistically cohesive while scenes stay varied. `theme` is
    an `art_direction.Theme` (or None for a neutral look). Returns a plain string.

    `visual_intent` comes from the structured script: what the writer intended
    this beat to SHOW. Without it the art director can only infer intent from
    the spoken line, which is how abstract beats ended up as stock imagery.
    """
    from ..content.llm_service import LLMService, LLMError
    from ..content.art_direction import compose_prompt
    from ..content.prompts import render

    prompt = render(
        "image.scene",
        run_summary=run_summary,
        line_text=line_text,
        visual_intent=(
            f"\nWhat this beat should show:\n{visual_intent}\n" if visual_intent else ""
        ),
        shot_hint=(f"\nShot direction: {shot_hint}\n" if shot_hint else ""),
    )

    try:
        response = LLMService(task="image.scene").generate_content(prompt)
    except LLMError as e:
        raise RuntimeError(f"Failed to generate image prompt: {e}") from e

    scene = response.strip()
    if scene.startswith('"') and scene.endswith('"'):
        scene = scene[1:-1]

    return compose_prompt(scene, theme)


def generate_image_from_prompt(prompt: str, out_path: str, width=None, height=None) -> None:
    """
    Use video/image scripts you have (image_generator.py) or service.
    Must write a PNG to out_path. Overwrite if exists.
    """
    try:
        from ..image.image_service_factory import ImageServiceFactory

        # Create output directory if it doesn't exist
        Path(out_path).parent.mkdir(parents=True, exist_ok=True)

        # Generate and save image using the configured service
        service = ImageServiceFactory.create_image_service()
        kwargs = {}
        if width:
            kwargs["width"] = width
        if height:
            kwargs["height"] = height
        service.generate_and_save_image(prompt, out_path, "image.png", **kwargs)

    except Exception as e:
        raise RuntimeError(f"Failed to generate image: {e}")


def save_segment_image(si: "SegmentImage", *, outputs_root: str) -> None:
    """Save segment image to Postgres and disk"""
    # Save to Postgres
    repo.save_image(si)

    # Write meta.json
    meta_path = img_meta_path(outputs_root, si.item_id, si.run, si.seg, si.index)
    Path(meta_path).parent.mkdir(parents=True, exist_ok=True)
    # Use model_dump_json() to handle datetime serialization properly
    with open(meta_path, "w", encoding="utf-8") as f:
        f.write(si.model_dump_json())

    # Publish visuals to the object store (root frame, sequence frames, motion
    # clip). Non-fatal; re-publishing after a rebuild just overwrites.
    from ..storage import object_store

    object_store.publish_file(si.image_path)
    for frame_path in si.sequence_paths or []:
        if frame_path != si.image_path:
            object_store.publish_file(frame_path)
    object_store.publish_file(si.video_clip_path)


def get_segment_image(
    item_id: int, run: int, seg: int, index: int
) -> Optional["SegmentImage"]:
    """Get segment image from Postgres"""
    return repo.get_image(item_id, run, seg, index)


def list_segment_images(item_id: int, run: int, seg: int) -> List[int]:
    """List segment image indexes in order"""
    return repo.list_image_indexes(item_id, run, seg)


def update_segment_images_status(
    item_id: int,
    run: int,
    seg: int,
    total: int,
    ready: bool,
    *,
    outputs_root: str,
) -> None:
    """Update segment image status"""
    # Load Segment
    segment = get_segment(item_id, run, seg)
    if not segment:
        raise RuntimeError(f"Segment not found: {item_id}:{run}:{seg}")

    # Update image fields
    segment.images_total = total
    segment.images_ready = ready

    # Re-save to Postgres and disk
    save_segment(segment, outputs_root=outputs_root)


def list_section_numbers(item_id: int, run: int, seg: int) -> List[int]:
    """Get ordered section indices for a segment"""
    return repo.list_section_numbers(item_id, run, seg)


def load_section_and_image(item_id: int, run: int, seg: int, index: int) -> dict:
    """
    Load section and image data for a specific index.

    Returns:
        {
            "index": index,
            "duration_ms": int,             # from SegmentSection.duration_ms (REQUIRED)
            "image_path": str,              # from SegmentImage.image_path (REQUIRED)
            "text": str                     # from SegmentImage.line_text (for subtitles)
        }
    Raises if any required field is missing or empty.
    """
    # Load section data
    section = repo.get_section(item_id, run, seg, index)
    if not section or section.duration_ms is None:
        raise RuntimeError(f"Section {index} missing or duration_ms is None")

    # Load image data
    image = get_segment_image(item_id, run, seg, index)
    if not image or not image.image_path:
        raise RuntimeError(f"Image {index} missing or image_path is None")

    return {
        "index": index,
        "duration_ms": section.duration_ms,
        "image_path": image.image_path,
        "text": image.line_text,
    }


def build_timeline(item_id: int, run: int, seg: int) -> List[dict]:
    """
    Build timeline for video generation from sections and images.
    Includes intro, title page, main content, and outro.

    Returns:
        List of dicts with:
        {
            "index": int,
            "image_path": str,
            "start_ms": int,
            "duration_ms": int,
            "text": str,
            "type": str  # "intro", "title", "content", "outro"
        }
    """
    from ..utils.run_utils import get_run
    from pathlib import Path

    # Get run data for title and emojis
    run_data = get_run(item_id, run)
    if not run_data:
        raise RuntimeError(f"Run data not found for item {item_id}, run {run}")

    timeline = []
    cumulative_start = 0

    # Add intro sequence (4 seconds)
    intro_audio_path = Path(__file__).parent.parent / "video" / "media" / "intro.wav"
    intro_image_path = (
        Path(__file__).parent.parent / "video" / "media" / "hnfm_square.png"
    )

    if intro_audio_path.exists() and intro_image_path.exists():
        timeline.append(
            {
                "index": -3,  # Special index for intro
                "image_path": str(intro_image_path),
                "start_ms": cumulative_start,
                "duration_ms": 4000,  # 4 seconds
                "text": "Intro",
                "type": "intro",
            }
        )
        cumulative_start += 4000

    # Add main content from sections and images
    section_numbers = list_section_numbers(item_id, run, seg)

    for index in section_numbers:
        data = load_section_and_image(item_id, run, seg, index)

        total = int(data["duration_ms"] or 0)
        si = get_segment_image(item_id, run, seg, index)

        # If this section has an LTX motion clip, play it for its (lightly
        # stretched) length, then fill the rest of the section with the image
        # sequence — so motion stays natural instead of heavily slowed.
        clip = getattr(si, "video_clip_path", None) if si else None
        if clip and Path(clip).exists():
            clip_ms = int((getattr(si, "video_clip_seconds", None) or 0) * 1000) or total
            clip_ms = max(0, min(clip_ms, total))
            timeline.append(
                {
                    "index": data["index"],
                    "image_path": data["image_path"],
                    "video_path": clip,
                    "start_ms": cumulative_start,
                    "duration_ms": clip_ms,
                    "text": data["text"],
                    "type": "video",
                }
            )
            cumulative_start += clip_ms

            remaining = total - clip_ms
            if remaining > 400:
                tail = [
                    p for p in (getattr(si, "sequence_paths", None) or []) if p
                ] or [data["image_path"]]
                m = max(1, len(tail))
                per = max(400, remaining // m)
                for k, fp in enumerate(tail):
                    d = (remaining - per * (m - 1)) if k == m - 1 else per
                    if d <= 0:
                        d = per
                    timeline.append(
                        {
                            "index": data["index"],
                            "image_path": fp,
                            "start_ms": cumulative_start,
                            "duration_ms": d,
                            "text": data["text"],
                            "type": "content",
                        }
                    )
                    cumulative_start += d
            continue

        # Otherwise expand an image sequence (root + edits) across the slot so
        # the visuals change in quick cadence. Falls back to a single image.
        frames = [
            p for p in (getattr(si, "sequence_paths", None) or []) if p
        ] or [data["image_path"]]
        n = max(1, len(frames))
        per = max(500, total // n) if total else 0

        for k, fp in enumerate(frames):
            d = (total - per * (n - 1)) if k == n - 1 else per
            if d <= 0:
                d = per or total
            timeline.append(
                {
                    "index": data["index"],
                    "image_path": fp,
                    "start_ms": cumulative_start,
                    "duration_ms": d,
                    "text": data["text"],
                    "type": "content",
                }
            )
            cumulative_start += d

    # Add outro sequence (4 seconds)
    outro_image_path = (
        Path(__file__).parent.parent / "video" / "media" / "hnfm_square.png"
    )

    if outro_image_path.exists():
        timeline.append(
            {
                "index": -1,  # Special index for outro
                "image_path": str(outro_image_path),
                "start_ms": cumulative_start,
                "duration_ms": 4000,  # 4 seconds
                "text": "Outro",
                "type": "outro",
            }
        )

    return timeline


def write_vtt_from_timeline(timeline: List[dict], out_path: str) -> None:
    """
    Create WebVTT subtitles from timeline data.

    Args:
        timeline: List of dicts with start_ms, duration_ms, text
        out_path: Output VTT file path
    """
    from pathlib import Path

    # Ensure output directory exists
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)

    with open(out_path, "w", encoding="utf-8") as f:
        f.write("WEBVTT\n\n")

        for item in timeline:
            start_ms = item["start_ms"]
            duration_ms = item["duration_ms"]
            end_ms = start_ms + duration_ms
            text = item["text"]

            # Convert to VTT time format (HH:MM:SS.mmm)
            start_time = _ms_to_vtt_time(start_ms)
            end_time = _ms_to_vtt_time(end_ms)

            f.write(f"{start_time} --> {end_time}\n")
            f.write(f"{text}\n\n")


def write_ass_from_asr(asr_data: dict, out_path: str, width: int = 1280, height: int = 720) -> None:
    """Animated karaoke captions (ASS) from ASR word timings, via pysubs2.

    Each caption line highlights word-by-word as it is spoken (smooth ``\\kf``
    fill synced to the actual word times). Times are offset by the 4s intro.
    Falls back to a flat single line if only flat words are present.
    """
    import pysubs2
    from pathlib import Path

    INTRO_OFFSET = 4.0
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)

    segments = asr_data.get("segments") or []
    if not segments and asr_data.get("words"):
        segments = [{"words": asr_data["words"]}]

    subs = pysubs2.SSAFile()
    subs.info["Title"] = "hn.fm captions"
    subs.info["PlayResX"] = str(width)
    subs.info["PlayResY"] = str(height)
    subs.info["ScaledBorderAndShadow"] = "yes"

    style = pysubs2.SSAStyle()
    style.fontname = "DejaVu Sans"
    style.fontsize = 44
    style.bold = True
    style.primarycolor = pysubs2.Color(80, 230, 255)      # active word = cyan
    style.secondarycolor = pysubs2.Color(255, 255, 255)   # upcoming = white
    style.outlinecolor = pysubs2.Color(0, 0, 0)
    style.backcolor = pysubs2.Color(0, 0, 0, 160)
    style.outline = 3.5
    style.shadow = 1.5
    style.alignment = pysubs2.Alignment.BOTTOM_CENTER
    style.marginl = 80
    style.marginr = 80
    style.marginv = 60
    subs.styles["Caption"] = style

    for seg in segments:
        words = [w for w in (seg.get("words") or []) if (w.get("word") or "").strip()]
        if not words:
            continue
        seg_start = float(words[0].get("start", 0)) + INTRO_OFFSET
        seg_end = float(words[-1].get("end", 0)) + INTRO_OFFSET
        if seg_end <= seg_start:
            seg_end = seg_start + 0.6

        parts = []
        for i, w in enumerate(words):
            w_start = float(w.get("start", 0))
            nxt = float(words[i + 1].get("start", 0)) if i + 1 < len(words) else float(w.get("end", w_start))
            dur_cs = max(1, round((nxt - w_start) * 100))
            token = (w.get("word") or "").strip().replace("{", "(").replace("}", ")")
            parts.append("{\\kf%d}%s " % (dur_cs, token))

        text = "{\\fad(120,80)}" + "".join(parts).strip()
        subs.append(
            pysubs2.SSAEvent(
                start=int(seg_start * 1000),
                end=int(seg_end * 1000),
                style="Caption",
                text=text,
            )
        )

    subs.save(out_path)


def write_vtt_from_asr(asr_data: dict, out_path: str) -> None:
    """Plain WebVTT from the same ASR timings `write_ass_from_asr` uses.

    The ASS file is for burning into the video; it cannot serve as the browser
    `<track>`, because `<track>` accepts WebVTT only and would ignore ASS even
    if it were served. So both are written from one ASR source: ASS for the
    burn-in, this for the player.

    Cue boundaries and the 4s INTRO_OFFSET deliberately mirror the ASS writer —
    if the two drift apart, the on-screen captions and the track disagree.
    Karaoke markup is dropped; per-word highlighting has no WebVTT equivalent
    worth emulating here, and the burned-in captions already carry it.
    """
    from pathlib import Path

    INTRO_OFFSET = 4.0
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)

    segments = asr_data.get("segments") or []
    if not segments and asr_data.get("words"):
        segments = [{"words": asr_data["words"]}]

    with open(out_path, "w", encoding="utf-8") as f:
        f.write("WEBVTT\n\n")
        for seg in segments:
            words = [
                w for w in (seg.get("words") or []) if (w.get("word") or "").strip()
            ]
            if not words:
                continue
            start = float(words[0].get("start", 0)) + INTRO_OFFSET
            end = float(words[-1].get("end", 0)) + INTRO_OFFSET
            if end <= start:
                end = start + 0.6
            text = " ".join((w.get("word") or "").strip() for w in words)
            f.write(f"{_ms_to_vtt_time(int(start * 1000))} --> ")
            f.write(f"{_ms_to_vtt_time(int(end * 1000))}\n{text}\n\n")


def _seconds_to_ass_time(seconds: float) -> str:
    """Convert seconds to ASS time format (H:MM:SS.cc)."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    centiseconds = int((seconds % 1) * 100)

    return f"{hours}:{minutes:02d}:{secs:02d}.{centiseconds:02d}"


def _ms_to_vtt_time(ms: int) -> str:
    """Convert milliseconds to VTT time format (HH:MM:SS.mmm)"""
    seconds = ms // 1000
    milliseconds = ms % 1000
    minutes = seconds // 60
    seconds = seconds % 60
    hours = minutes // 60
    minutes = minutes % 60

    return f"{hours:02d}:{minutes:02d}:{seconds:02d}.{milliseconds:03d}"


def update_segment_video_fields(
    item_id: int,
    run: int,
    seg: int,
    *,
    outputs_root: str,
    video_path_str: str | None,
    subtitles_path_str: str | None,
    video_ready: bool,
) -> None:
    """
    Update segment video fields in Postgres and on disk.

    Args:
        item_id: Item ID
        run: Run number
        seg: Segment number
        outputs_root: Root outputs directory
        video_path_str: Path to video file (optional)
        subtitles_path_str: Path to subtitles file (optional)
        video_ready: Whether video is ready
    """
    # Load existing segment
    segment = get_segment(item_id, run, seg)
    if not segment:
        raise RuntimeError(f"Segment not found: {item_id}:{run}:{seg}")

    # Update video fields
    segment.video_path = video_path_str
    segment.subtitles_path = subtitles_path_str
    segment.video_ready = video_ready

    # Re-save to Postgres and disk
    save_segment(segment, outputs_root=outputs_root)

    # Publish the finished video + subtitles to the object store (non-fatal)
    from ..storage import object_store

    object_store.publish_file(video_path_str)
    object_store.publish_file(subtitles_path_str)
