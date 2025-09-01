#!/usr/bin/env python3
"""Script to run just the ASR step for a specific story."""

import sys
from pathlib import Path

# Add src to path (scripts are now in src/hnfm/scripts/)
sys.path.insert(0, str(Path(__file__).parent / ".." / ".."))

from hnfm.pipeline.enhanced_pipeline_manager import PipelineManager
from hnfm.utils.config import config_manager


def run_asr_step(story_dir_name: str):
    """Run just the ASR step for a specific story.

    Args:
        story_dir_name: Name of the story directory (e.g., 'im_too_dumb_for_zigs_new_io_interface_68a9d4')
    """
    try:
        # Initialize pipeline manager
        pipeline = PipelineManager()

        # Construct the story directory path
        story_dir = Path("outputs") / story_dir_name

        if not story_dir.exists():
            print(f"❌ Story directory not found: {story_dir}")
            return

        # Look for the final audio file
        final_audio = None

        # Check common locations
        possible_locations = [
            story_dir / "final_audio.wav",
            story_dir / "audio" / "final_audio.wav",
        ]

        # Also search for files with "final" in the name
        for audio_dir in [story_dir, story_dir / "audio"]:
            if audio_dir.exists():
                for wav_file in audio_dir.glob("*.wav"):
                    if "final" in wav_file.name.lower():
                        possible_locations.append(wav_file)

        # Find the first existing file
        for location in possible_locations:
            if location.exists():
                final_audio = location
                break

        if not final_audio:
            print(f"❌ Final audio file not found")
            print(f"   Checked locations:")
            for location in possible_locations:
                print(f"     - {location}")
            return

        print(f"🎬 Running ASR step for story: {story_dir_name}")
        print(f"📁 Story directory: {story_dir}")
        print(f"🎵 Final audio: {final_audio}")

        # Check if ASR file already exists
        asr_file = story_dir / "content" / "asr.json"
        if asr_file.exists():
            print(f"\n✅ ASR file already exists: {asr_file}")
            print("   Skipping processing. Use --force to reprocess.")
            return

        # Prepare inputs for the ASR step
        inputs = {
            "final_audio": str(final_audio),
            "story_dir": str(story_dir),
        }

        # Execute just the ASR step
        print("\n🔵 STEP ASR PROCESSING")
        print("   ====================")

        result = pipeline.execute_step("asr_processing", inputs)

        print(f"\n✅ ASR step completed successfully!")
        print(f"📄 Results saved to: {result['asr_results_path']}")

    except Exception as e:
        print(f"❌ ASR step failed: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python run_asr_step.py <story_directory_name>")
        print(
            "Example: python run_asr_step.py im_too_dumb_for_zigs_new_io_interface_68a9d4"
        )
        sys.exit(1)

    story_dir_name = sys.argv[1]
    run_asr_step(story_dir_name)
