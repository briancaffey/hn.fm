#!/usr/bin/env python3
"""Test script for pipeline with image generation."""

import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

from hnfm.pipeline import PipelineManager


def test_pipeline_with_images():
    """Test the pipeline with image generation step."""
    print("🧪 Testing Pipeline with Image Generation")
    print("=" * 50)

    # Initialize pipeline manager
    pipeline = PipelineManager()

    # Check if image generation step is defined
    if "image_generation" in pipeline.pipeline_steps:
        step = pipeline.pipeline_steps["image_generation"]
        print(f"✅ Image generation step found:")
        print(f"   Name: {step.name}")
        print(f"   Description: {step.description}")
        print(f"   Dependencies: {step.dependencies}")
        print(f"   Output files: {step.output_files}")
    else:
        print("❌ Image generation step not found in pipeline")
        return False

    # Check if image generation service is available
    try:
        image_service = pipeline._get_service("image_generator")
        print(f"✅ Image generation service available: {type(image_service).__name__}")
    except Exception as e:
        print(f"❌ Failed to get image generation service: {e}")
        return False

    # Check pipeline step dependencies
    tts_step = pipeline.pipeline_steps["tts_generation"]
    if "image_generation" in tts_step.dependencies:
        print("✅ TTS generation depends on image generation")
    else:
        print("❌ TTS generation does not depend on image generation")
        return False

    print("\n🎉 Pipeline with image generation is properly configured!")
    return True


def main():
    """Run the test."""
    try:
        success = test_pipeline_with_images()
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
