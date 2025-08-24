#!/usr/bin/env python3
"""Test script for text-only pipeline mode."""

import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

from hnfm.pipeline import PipelineManager


def test_text_only_pipeline():
    """Test the text-only pipeline mode."""
    print("🧪 Testing Text-Only Pipeline Mode")
    print("=" * 50)

    # Initialize pipeline manager in text-only mode
    pipeline = PipelineManager(text_only=True)

    # Check pipeline steps
    print("📋 Pipeline Steps (Text-Only Mode):")
    for step_name, step in pipeline.pipeline_steps.items():
        print(f"   ✅ {step_name}: {step.description}")

    # Check that media steps are not included
    media_steps = ["image_generation", "tts_generation", "audio_cleaning",
                   "audio_assembly", "asr_processing", "video_generation"]

    missing_steps = [step for step in media_steps if step in pipeline.pipeline_steps]
    if missing_steps:
        print(f"❌ Unexpected media steps found: {missing_steps}")
        return False

    print(f"✅ All media steps correctly excluded: {media_steps}")

    # Check that text steps are included
    text_steps = ["system_check", "hn_scraping", "firecrawl_content",
                  "content_processing", "script_generation"]

    missing_text_steps = [step for step in text_steps if step not in pipeline.pipeline_steps]
    if missing_text_steps:
        print(f"❌ Missing text steps: {missing_text_steps}")
        return False

    print(f"✅ All text steps correctly included: {text_steps}")

    print("\n🎉 Text-only pipeline mode is properly configured!")
    return True


def main():
    """Run the test."""
    try:
        success = test_text_only_pipeline()
        if success:
            print("\n✅ All tests passed!")
            return 0
        else:
            print("\n❌ Some tests failed!")
            return 1
    except Exception as e:
        print(f"\n💥 Test failed with error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
