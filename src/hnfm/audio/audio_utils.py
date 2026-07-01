"""Audio utilities for segment section generation"""

import os
import wave
from pathlib import Path
from typing import List, Optional

from ..db import repo
from ..web.models import Segment, SegmentSection


def k_sec(item_id: int, run: int, seg: int, section: int) -> str:
    """Legacy entity key string (kept on the Pydantic models / API responses)"""
    return f"hnfm:seg:{item_id}:{run}:{seg}:sec:{section}"


# Disk path helpers
def seg_root(outputs_root: str, item_id: int, run: int, seg: int) -> str:
    """Generate root directory path for a segment"""
    return f"{outputs_root}/hn/item/{item_id}/runs/{run}/segments/{seg}"


def sec_dir(outputs_root: str, item_id: int, run: int, seg: int, section: int) -> str:
    """Generate directory path for a section"""
    return f"{seg_root(outputs_root, item_id, run, seg)}/audio/sections/{section}"


def sec_audio_path(
    outputs_root: str, item_id: int, run: int, seg: int, section: int
) -> str:
    """Generate audio file path for a section"""
    return f"{sec_dir(outputs_root, item_id, run, seg, section)}/audio.wav"


def sec_meta_path(
    outputs_root: str, item_id: int, run: int, seg: int, section: int
) -> str:
    """Generate metadata file path for a section"""
    return f"{sec_dir(outputs_root, item_id, run, seg, section)}/meta.json"


def combined_audio_path(outputs_root: str, item_id: int, run: int, seg: int) -> str:
    """Generate combined audio file path for a segment"""
    return f"{seg_root(outputs_root, item_id, run, seg)}/audio/segment.wav"


def split_script_into_sections(script: str) -> List[str]:
    """
    Split script into sections (two lines at a time).

    Args:
        script: Full script text

    Returns:
        List of section texts in order (indexes become sections 1..N)
    """
    lines = [line.strip() for line in script.split("\n") if line.strip()]

    sections = []
    for i in range(0, len(lines), 2):
        # Take up to 2 lines for each section
        section_lines = lines[i : i + 2]
        sections.append("\n".join(section_lines))

    return sections


def tts_synthesize_to_wav(text: str, out_path: str) -> int:
    """
    Synthesize text to WAV file using TTS service.

    Args:
        text: Text to synthesize
        out_path: Output WAV file path

    Returns:
        Duration in milliseconds
    """
    from .tts_api_service import TtsApiService

    # Ensure output directory exists
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)

    # Initialize TTS API service
    tts_service = TtsApiService()

    # Generate speech
    audio_data = tts_service.generate_speech(text)
    if not audio_data:
        raise RuntimeError(f"Failed to generate speech for text: {text[:100]}...")

    # Write audio data to file
    with open(out_path, "wb") as f:
        f.write(audio_data)

    # Get duration
    duration_ms = _get_audio_duration_ms(out_path)
    return duration_ms


def studio_voice_clean_inplace(wav_path: str) -> None:
    """
    Clean audio file in-place using studio-voice service.

    Args:
        wav_path: Path to WAV file to clean (will be overwritten)
    """
    # NVIDIA Studio Voice NIM is not deployed in the inference-club cluster, so
    # enhancement is a no-op by default (Magpie TTS output is already clean WAV).
    if os.getenv("STUDIO_VOICE_ENABLED", "false").lower() != "true":
        print(f"⏭️  Studio Voice disabled; skipping enhance for {wav_path}")
        return

    from .studio_voice_service import StudioVoiceService

    # Read original audio
    with open(wav_path, "rb") as f:
        audio_data = f.read()

    # Initialize studio voice service
    studio_voice = StudioVoiceService()

    # Enhance audio
    enhanced_audio = studio_voice.enhance_audio(audio_data)
    if not enhanced_audio:
        raise RuntimeError(f"Failed to enhance audio: {wav_path}")

    # Write enhanced audio back to file
    with open(wav_path, "wb") as f:
        f.write(enhanced_audio)


def save_section_meta(meta: SegmentSection, *, outputs_root: str) -> None:
    """
    Save section metadata to Postgres and disk.

    Args:
        meta: Section metadata object
        outputs_root: Root outputs directory
    """
    # Save to Postgres
    repo.save_section(meta)

    # Ensure directory exists
    meta_dir = sec_dir(outputs_root, meta.item_id, meta.run, meta.seg, meta.section)
    Path(meta_dir).mkdir(parents=True, exist_ok=True)

    # Save to disk
    meta_file = sec_meta_path(
        outputs_root, meta.item_id, meta.run, meta.seg, meta.section
    )
    with open(meta_file, "w", encoding="utf-8") as f:
        f.write(meta.model_dump_json())

    # Publish the section audio to the object store (non-fatal)
    from ..storage import object_store

    object_store.publish_file(meta.audio_path)


def get_section_meta(
    item_id: int, run: int, seg: int, section: int
) -> Optional[SegmentSection]:
    """
    Get section metadata from Postgres.

    Returns:
        Section metadata or None if not found
    """
    return repo.get_section(item_id, run, seg, section)


def list_section_numbers(item_id: int, run: int, seg: int) -> List[int]:
    """
    List section numbers for a segment in order.

    Returns:
        List of section numbers in ascending order
    """
    return repo.list_section_numbers(item_id, run, seg)


def delete_sections(item_id: int, run: int, seg: int) -> None:
    """Remove all section records for a segment (rebuild-all clears first)."""
    repo.delete_sections(item_id, run, seg)


def stitch_sections_to_wav(section_paths: List[str], out_path: str) -> int:
    """
    Stitch multiple WAV files into one combined WAV file.

    Args:
        section_paths: List of WAV file paths to combine
        out_path: Output combined WAV file path

    Returns:
        Total duration in milliseconds
    """
    # Ensure output directory exists
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)

    if not section_paths:
        raise ValueError("No section paths provided")

    # Read first file to get format info
    with wave.open(section_paths[0], "rb") as first_wav:
        n_channels = first_wav.getnchannels()
        sample_width = first_wav.getsampwidth()
        framerate = first_wav.getframerate()

    # Combine all audio data
    combined_frames = b""
    total_duration_ms = 0

    for section_path in section_paths:
        if not os.path.exists(section_path):
            raise FileNotFoundError(f"Section file not found: {section_path}")

        with wave.open(section_path, "rb") as wav_file:
            # Verify format matches
            if (
                wav_file.getnchannels() != n_channels
                or wav_file.getsampwidth() != sample_width
                or wav_file.getframerate() != framerate
            ):
                raise ValueError(f"Audio format mismatch in {section_path}")

            # Read frames and add to combined
            frames = wav_file.readframes(wav_file.getnframes())
            combined_frames += frames

            # Calculate duration
            duration_frames = wav_file.getnframes()
            duration_ms = int((duration_frames / framerate) * 1000)
            total_duration_ms += duration_ms

    # Write combined WAV file
    with wave.open(out_path, "wb") as out_wav:
        out_wav.setnchannels(n_channels)
        out_wav.setsampwidth(sample_width)
        out_wav.setframerate(framerate)
        out_wav.writeframes(combined_frames)

    return total_duration_ms


def update_segment_audio_status(
    item_id: int,
    run: int,
    seg: int,
    sections_total: int,
    combined_path: str,
    ready: bool,
    *,
    outputs_root: str,
) -> None:
    """
    Update segment audio status in Postgres and disk.

    Args:
        item_id: Item ID
        run: Run number
        seg: Segment number
        sections_total: Total number of sections
        combined_path: Path to combined audio file
        ready: Whether audio is ready
        outputs_root: Root outputs directory
    """
    from ..utils.segment_utils import get_segment, save_segment

    # Load existing segment
    segment = get_segment(item_id, run, seg)
    if not segment:
        raise RuntimeError(f"Segment not found: {item_id}:{run}:{seg}")

    # Update audio fields
    segment.sections_total = sections_total
    segment.audio_combined_path = combined_path
    segment.audio_ready = ready

    # Save to Postgres and disk
    save_segment(segment, outputs_root=outputs_root)

    # Publish the combined audio to the object store (non-fatal)
    from ..storage import object_store

    object_store.publish_file(combined_path)


def _get_audio_duration_ms(wav_path: str) -> int:
    """
    Get audio duration in milliseconds.

    Args:
        wav_path: Path to WAV file

    Returns:
        Duration in milliseconds
    """
    try:
        with wave.open(wav_path, "rb") as wav_file:
            frames = wav_file.getnframes()
            rate = wav_file.getframerate()
            duration_seconds = frames / float(rate)
            return int(duration_seconds * 1000)
    except Exception as e:
        raise RuntimeError(f"Could not determine audio duration for {wav_path}: {e}")
