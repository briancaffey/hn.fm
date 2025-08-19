#!/usr/bin/env python3
"""Command-line interface for generating audio from TTS lines."""

import argparse
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from hnfm.content.script_generator import ScriptGenerator


def main():
    """Main function for the audio generation CLI."""
    parser = argparse.ArgumentParser(
        description="Generate audio from TTS lines using hn.fm TTS pipeline"
    )
    parser.add_argument(
        "tts_file",
        help="Path to TTS lines file (e.g., outputs/tts_lines_*.txt)"
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=2,
        help="Number of lines to process at once (default: 2)"
    )
    parser.add_argument(
        "--output-dir",
        default="outputs",
        help="Base output directory (default: outputs)"
    )
    parser.add_argument(
        "--story-name",
        help="Custom story name (default: extracted from filename)"
    )

    args = parser.parse_args()

    # Check if TTS file exists
    tts_file = Path(args.tts_file)
    if not tts_file.exists():
        print(f"❌ TTS file not found: {tts_file}")
        sys.exit(1)

    # Initialize script generator
    script_generator = ScriptGenerator(output_dir=args.output_dir)

    # Extract story name if not provided
    if not args.story_name:
        story_name = script_generator.get_story_name_from_filename(tts_file.name)
    else:
        story_name = args.story_name

    print(f"🎤 Generating audio for story: {story_name}")
    print(f"📁 TTS file: {tts_file}")
    print(f"📁 Output directory: {args.output_dir}")
    print(f"🔢 Batch size: {args.batch_size}")
    print("=" * 50)

    try:
        # Process TTS lines and generate audio
        final_audio_path = script_generator.process_tts_lines(
            tts_lines_file=str(tts_file),
            story_name=story_name,
            batch_size=args.batch_size
        )

        print(f"\n✅ Successfully generated audio!")
        print(f"🎵 Final audio file: {final_audio_path}")
        print(f"📁 Story files organized in: {final_audio_path.parent}")

        # List generated files
        story_dir = final_audio_path.parent
        print(f"\n📋 Generated files:")
        for file_path in sorted(story_dir.glob("*.wav")):
            size_mb = file_path.stat().st_size / (1024 * 1024)
            print(f"  • {file_path.name} ({size_mb:.1f} MB)")

    except Exception as e:
        print(f"\n❌ Error generating audio: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
