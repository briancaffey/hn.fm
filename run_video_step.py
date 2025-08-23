#!/usr/bin/env python3
"""Standalone script to run the video generation step against a specific output folder."""

import os
import sys
import argparse
from pathlib import Path

# Add src to path so we can import hnfm modules
sys.path.insert(0, str(Path(__file__).parent / "src"))

from hnfm.video.video_generator import VideoGenerator
from hnfm.utils.config import config_manager
from hnfm.utils.logger import setup_logging


def main():
    """Run video generation step against a specific output folder."""
    parser = argparse.ArgumentParser(
        description="Generate video from ASR and audio files in an output folder"
    )
    parser.add_argument(
        "output_folder",
        help="Path to output folder containing content/asr.json and final_audio.wav"
    )
    parser.add_argument(
        "--audio-file",
        help="Path to audio file (defaults to final_audio.wav in output folder)"
    )
    parser.add_argument(
        "--output-video",
        help="Output video path (defaults to content/video.mp4 in output folder)"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging"
    )

    args = parser.parse_args()

    # Setup logging
    log_level = "DEBUG" if args.verbose else "INFO"
    setup_logging(log_level)

    # Validate output folder
    output_folder = Path(args.output_folder)
    if not output_folder.exists():
        print(f"❌ Output folder does not exist: {output_folder}")
        sys.exit(1)

    # Check for required files
    asr_file = output_folder / "content" / "asr.json"
    if not asr_file.exists():
        print(f"❌ ASR file not found: {asr_file}")
        sys.exit(1)

    # Determine audio file path
    if args.audio_file:
        audio_file = Path(args.audio_file)
        if not audio_file.exists():
            print(f"❌ Audio file not found: {audio_file}")
            sys.exit(1)
    else:
        # Look for final_audio.wav in the output folder
        audio_file = output_folder / "final_audio.wav"
        if not audio_file.exists():
            # Try to find any .wav file in the output folder
            wav_files = list(output_folder.glob("*.wav"))
            if wav_files:
                audio_file = wav_files[0]
                print(f"📁 Using audio file: {audio_file}")
            else:
                print(f"❌ No audio file found in {output_folder}")
                print("   Please specify --audio-file or ensure final_audio.wav exists")
                sys.exit(1)

    # Determine output video path
    if args.output_video:
        output_video = Path(args.output_video)
    else:
        output_video = output_folder / "content" / "video.mp4"

    print(f"🎬 Starting video generation...")
    print(f"📁 ASR file: {asr_file}")
    print(f"🎵 Audio file: {audio_file}")
    print(f"🎥 Output: {output_video}")
    print()

    try:
        # Initialize video generator
        video_generator = VideoGenerator()

        # Generate video
        result = video_generator.generate_video(
            asr_file_path=str(asr_file),
            audio_file_path=str(audio_file),
            output_path=str(output_video)
        )

        print(f"✅ Video generation completed successfully!")
        print(f"🎥 Video saved to: {output_video}")
        print(f"⏱️ Duration: {result['duration']:.2f} seconds")
        print(f"📐 Resolution: {result['resolution']}")
        print(f"🎬 FPS: {result['fps']}")

    except Exception as e:
        print(f"❌ Video generation failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
