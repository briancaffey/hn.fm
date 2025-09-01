#!/usr/bin/env python3
"""Test script for image generation service."""

import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

from hnfm.video import ImageGenerationService
from hnfm.utils.config import config_manager


def test_single_image_generation():
    """Test generating a single image."""
    print("Testing single image generation...")

    # Initialize service
    service = ImageGenerationService()

    # Test prompt
    prompt = (
        "a cozy coffee shop interior with warm lighting and people working on laptops"
    )

    try:
        # Generate and save image
        output_path = service.generate_and_save_image(
            prompt=prompt, output_dir="test/images", filename="coffee_shop_test.png"
        )
        print(f"✅ Successfully generated image: {output_path}")

    except Exception as e:
        print(f"❌ Failed to generate image: {e}")
        return False

    return True


def test_multiple_images():
    """Test generating multiple images with different prompts."""
    print("\nTesting multiple image generation...")

    service = ImageGenerationService()

    prompts = [
        "a modern tech office with developers working",
        "a beautiful sunset over a city skyline",
        "a peaceful forest path with sunlight filtering through trees",
    ]

    generated_images = []

    for i, prompt in enumerate(prompts):
        try:
            filename = f"test_image_{i+1}.png"
            output_path = service.generate_and_save_image(
                prompt=prompt, output_dir="test/images", filename=filename
            )
            generated_images.append(output_path)
            print(f"✅ Generated image {i+1}: {output_path}")

        except Exception as e:
            print(f"❌ Failed to generate image {i+1}: {e}")

    print(f"\nGenerated {len(generated_images)} out of {len(prompts)} images")
    return len(generated_images) > 0


def test_health_check():
    """Test the health check functionality."""
    print("\nTesting health check...")

    service = ImageGenerationService()

    try:
        is_healthy = service.health_check()
        if is_healthy:
            print("✅ Service is healthy")
        else:
            print("⚠️  Service health check failed")
        return is_healthy

    except Exception as e:
        print(f"❌ Health check error: {e}")
        return False


def test_config():
    """Test configuration loading."""
    print("\nTesting configuration...")

    try:
        base_url = config_manager.get("image_generation.base_url")
        height = config_manager.get("image_generation.default_height")
        width = config_manager.get("image_generation.default_width")

        print(f"✅ Base URL: {base_url}")
        print(f"✅ Default height: {height}")
        print(f"✅ Default width: {width}")

        return True

    except Exception as e:
        print(f"❌ Configuration error: {e}")
        return False


def main():
    """Run all tests."""
    print("🧪 Image Generation Service Test Suite")
    print("=" * 50)

    # Test configuration
    config_ok = test_config()

    # Test health check
    health_ok = test_health_check()

    # Test single image generation
    single_ok = test_single_image_generation()

    # Test multiple image generation
    multiple_ok = test_multiple_images()

    # Summary
    print("\n" + "=" * 50)
    print("📊 Test Results Summary:")
    print(f"Configuration: {'✅ PASS' if config_ok else '❌ FAIL'}")
    print(f"Health Check: {'✅ PASS' if health_ok else '❌ FAIL'}")
    print(f"Single Image: {'✅ PASS' if single_ok else '❌ FAIL'}")
    print(f"Multiple Images: {'✅ PASS' if multiple_ok else '❌ FAIL'}")

    if all([config_ok, health_ok, single_ok, multiple_ok]):
        print("\n🎉 All tests passed!")
        return 0
    else:
        print("\n💥 Some tests failed!")
        return 1


if __name__ == "__main__":
    sys.exit(main())
