#!/usr/bin/env python3
"""Test script for the updated video generator with images."""

import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

from hnfm.video import VideoGenerator


def test_video_generation():
    """Test the video generator with the existing story data."""
    print("🎬 Testing Video Generation with Images")
    print("=" * 50)

    # Paths to the existing story
    story_dir = Path(
        "outputs/comet_ai_browser_can_get_prompt_injected_from_any_site_drain_your_bank_account_68ab69"
    )

    if not story_dir.exists():
        print(f"❌ Story directory not found: {story_dir}")
        return False

    # Required files
    asr_file = story_dir / "content" / "asr.json"
    audio_file = (
        story_dir
        / "audio"
        / "Comet_AI_browser_can_get_prompt_injected_from_any_site,_drain_your_bank_account_final.wav"
    )
    main_yaml = story_dir / "content" / "main.yaml"
    output_video = story_dir / "content" / "video_with_images.mp4"

    # Check if required files exist
    print("🔍 Checking required files...")
    print(f"   ASR file: {asr_file} - {'✅' if asr_file.exists() else '❌'}")
    print(f"   Audio file: {audio_file} - {'✅' if audio_file.exists() else '❌'}")
    print(f"   Main YAML: {main_yaml} - {'✅' if main_yaml.exists() else '❌'}")

    if not all([asr_file.exists(), audio_file.exists(), main_yaml.exists()]):
        print("❌ Missing required files")
        return False

    try:
        # Initialize video generator
        print("\n🎬 Initializing video generator...")
        video_gen = VideoGenerator()

        # Debug: Load and check the content data manually
        print("\n🔍 Debug: Loading main.yaml content...")
        import yaml

        with open(main_yaml, "r", encoding="utf-8") as f:
            content_data = yaml.safe_load(f)

        print(f"   Content keys: {list(content_data.keys())}")
        print(f"   Narration type: {type(content_data.get('narration'))}")

        # Check the correct structure
        narration = content_data.get("narration", {})
        if isinstance(narration, dict):
            print(f"   Narration keys: {list(narration.keys())}")
            if "generated" in narration:
                generated_groups = narration["generated"]
                print(f"   Generated groups count: {len(generated_groups)}")

                # Check each generated group
                for i, group in enumerate(generated_groups):
                    print(f"   Generated Group {i}:")
                    print(f"     - status: {group.get('status')}")
                    print(f"     - image_file: {group.get('image_file')}")
                    print(f"     - has image_file: {bool(group.get('image_file'))}")
                    print(
                        f"     - status == 'generated': {group.get('status') == 'generated'}"
                    )
                    if group.get("image_file"):
                        print(
                            f"     - image exists: {Path(group.get('image_file')).exists()}"
                        )
                    print()
        else:
            print(f"   Narration is not a dict: {narration}")

        # Generate video with images
        print("\n🎬 Generating video with images...")
        result = video_gen.generate_video(
            asr_file_path=str(asr_file),
            audio_file_path=str(audio_file),
            main_yaml_path=str(main_yaml),
            output_path=str(output_video),
        )

        if result and result.get("success"):
            print(f"✅ Video generation successful!")
            print(f"   Output: {output_video}")
            print(f"   Duration: {result.get('duration', 'unknown')} seconds")
            print(f"   Resolution: {result.get('resolution', 'unknown')}")
            print(f"   FPS: {result.get('fps', 'unknown')}")

            # Check if output file exists and has size
            if output_video.exists():
                size_mb = output_video.stat().st_size / (1024 * 1024)
                print(f"   File size: {size_mb:.1f} MB")
            else:
                print("⚠️  Output file not found")

            return True
        else:
            print("❌ Video generation failed")
            return False

    except Exception as e:
        print(f"💥 Error during video generation: {e}")
        import traceback

        traceback.print_exc()
        return False


def main():
    """Main entry point."""
    print("Video Generator Test")
    print("Testing the updated video generator with image support")
    print()

    success = test_video_generation()

    if success:
        print("\n🎉 Test completed successfully!")
        print("The video generator is now working with images!")
        return 0
    else:
        print("\n💥 Test failed. Check the logs above for details.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
