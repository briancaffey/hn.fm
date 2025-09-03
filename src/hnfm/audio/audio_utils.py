"""Audio utilities for segment section generation"""

import json
import os
import wave
from datetime import datetime
from pathlib import Path
from typing import List, Optional
import redis

from ..web.models import Segment, SegmentSection


# Redis key helpers
def k_sec(item_id: int, run: int, seg: int, section: int) -> str:
    """Generate Redis key for a section"""
    return f"hnfm:seg:{item_id}:{run}:{seg}:sec:{section}"


def k_sec_list(item_id: int, run: int, seg: int) -> str:
    """Generate Redis key for section list (ordered)"""
    return f"hnfm:seg:{item_id}:{run}:{seg}:sec:list"


# Disk path helpers
def seg_root(outputs_root: str, item_id: int, run: int, seg: int) -> str:
    """Generate root directory path for a segment"""
    return f"{outputs_root}/hn/item/{item_id}/runs/{run}/segments/{seg}"


def sec_dir(outputs_root: str, item_id: int, run: int, seg: int, section: int) -> str:
    """Generate directory path for a section"""
    return f"{seg_root(outputs_root, item_id, run, seg)}/audio/sections/{section}"


def sec_audio_path(outputs_root: str, item_id: int, run: int, seg: int, section: int) -> str:
    """Generate audio file path for a section"""
    return f"{sec_dir(outputs_root, item_id, run, seg, section)}/audio.wav"


def sec_meta_path(outputs_root: str, item_id: int, run: int, seg: int, section: int) -> str:
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
    lines = [line.strip() for line in script.split('\n') if line.strip()]

    sections = []
    for i in range(0, len(lines), 2):
        # Take up to 2 lines for each section
        section_lines = lines[i:i+2]
        sections.append('\n'.join(section_lines))

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
    from .tts_service import TTSService

    # Ensure output directory exists
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)

    # Initialize TTS service
    tts_service = TTSService()

    # Generate speech
    audio_data = tts_service.generate_speech(text)
    if not audio_data:
        raise RuntimeError(f"Failed to generate speech for text: {text[:100]}...")

    # Write audio data to file
    with open(out_path, 'wb') as f:
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
    from .studio_voice_service import StudioVoiceService

    # Read original audio
    with open(wav_path, 'rb') as f:
        audio_data = f.read()

    # Initialize studio voice service
    studio_voice = StudioVoiceService()

    # Enhance audio
    enhanced_audio = studio_voice.enhance_audio(audio_data)
    if not enhanced_audio:
        raise RuntimeError(f"Failed to enhance audio: {wav_path}")

    # Write enhanced audio back to file
    with open(wav_path, 'wb') as f:
        f.write(enhanced_audio)


def save_section_meta(meta: SegmentSection, *, redis_client: redis.Redis, outputs_root: str) -> None:
    """
    Save section metadata to Redis and disk.

    Args:
        meta: Section metadata object
        redis_client: Redis client
        outputs_root: Root outputs directory
    """
    # Save to Redis
    redis_client.set(meta.key, meta.model_dump_json())

    # Ensure directory exists
    meta_dir = sec_dir(outputs_root, meta.item_id, meta.run, meta.seg, meta.section)
    Path(meta_dir).mkdir(parents=True, exist_ok=True)

    # Save to disk
    meta_file = sec_meta_path(outputs_root, meta.item_id, meta.run, meta.seg, meta.section)
    with open(meta_file, 'w', encoding='utf-8') as f:
        f.write(meta.model_dump_json())


def get_section_meta(item_id: int, run: int, seg: int, section: int, *, redis_client: redis.Redis) -> Optional[SegmentSection]:
    """
    Get section metadata from Redis.

    Args:
        item_id: Item ID
        run: Run number
        seg: Segment number
        section: Section number
        redis_client: Redis client

    Returns:
        Section metadata or None if not found
    """
    key = k_sec(item_id, run, seg, section)
    data = redis_client.get(key)

    if not data:
        return None

    try:
        return SegmentSection.model_validate_json(data)
    except Exception:
        return None


def list_section_numbers(item_id: int, run: int, seg: int, *, redis_client: redis.Redis) -> List[int]:
    """
    List section numbers for a segment in order.

    Args:
        item_id: Item ID
        run: Run number
        seg: Segment number
        redis_client: Redis client

    Returns:
        List of section numbers in ascending order
    """
    key = k_sec_list(item_id, run, seg)
    section_strings = redis_client.lrange(key, 0, -1)

    return [int(section_str) for section_str in section_strings]


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
    with wave.open(section_paths[0], 'rb') as first_wav:
        n_channels = first_wav.getnchannels()
        sample_width = first_wav.getsampwidth()
        framerate = first_wav.getframerate()

    # Combine all audio data
    combined_frames = b''
    total_duration_ms = 0

    for section_path in section_paths:
        if not os.path.exists(section_path):
            raise FileNotFoundError(f"Section file not found: {section_path}")

        with wave.open(section_path, 'rb') as wav_file:
            # Verify format matches
            if (wav_file.getnchannels() != n_channels or
                wav_file.getsampwidth() != sample_width or
                wav_file.getframerate() != framerate):
                raise ValueError(f"Audio format mismatch in {section_path}")

            # Read frames and add to combined
            frames = wav_file.readframes(wav_file.getnframes())
            combined_frames += frames

            # Calculate duration
            duration_frames = wav_file.getnframes()
            duration_ms = int((duration_frames / framerate) * 1000)
            total_duration_ms += duration_ms

    # Write combined WAV file
    with wave.open(out_path, 'wb') as out_wav:
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
    redis_client: redis.Redis,
    outputs_root: str
) -> None:
    """
    Update segment audio status in Redis and disk.

    Args:
        item_id: Item ID
        run: Run number
        seg: Segment number
        sections_total: Total number of sections
        combined_path: Path to combined audio file
        ready: Whether audio is ready
        redis_client: Redis client
        outputs_root: Root outputs directory
    """
    from ..utils.segment_utils import k_seg, get_segment

    # Load existing segment
    segment = get_segment(item_id, run, seg, redis_client=redis_client)
    if not segment:
        raise RuntimeError(f"Segment not found: {item_id}:{run}:{seg}")

    # Update audio fields
    segment.sections_total = sections_total
    segment.audio_combined_path = combined_path
    segment.audio_ready = ready

    # Save to Redis
    redis_client.set(segment.key, segment.model_dump_json())

    # Save to disk
    seg_path = seg_root(outputs_root, item_id, run, seg)
    Path(seg_path).mkdir(parents=True, exist_ok=True)

    segment_file = os.path.join(seg_path, "segment.json")
    with open(segment_file, "w", encoding="utf-8") as f:
        f.write(segment.model_dump_json())


def _get_audio_duration_ms(wav_path: str) -> int:
    """
    Get audio duration in milliseconds.

    Args:
        wav_path: Path to WAV file

    Returns:
        Duration in milliseconds
    """
    try:
        with wave.open(wav_path, 'rb') as wav_file:
            frames = wav_file.getnframes()
            rate = wav_file.getframerate()
            duration_seconds = frames / float(rate)
            return int(duration_seconds * 1000)
    except Exception as e:
        raise RuntimeError(f"Could not determine audio duration for {wav_path}: {e}")
