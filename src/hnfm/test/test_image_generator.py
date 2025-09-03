#!/usr/bin/env python3
"""Simple image generation service tests for hn.fm"""

import os
import sys
import pytest
from unittest.mock import patch, MagicMock
import base64

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from hnfm.video.image_generator import ImageGenerationService


class TestImageGenerationService:
    """Simple image generation service tests"""

    def test_image_generation_service_initialization(self):
        """Test that image generation service can be initialized"""
        print("🧪 Testing Image Generation Service Initialization...")

        # Mock the config manager to avoid real config calls
        with patch("hnfm.video.image_generator.config_manager") as mock_config:
            # Mock config values
            mock_config.get.side_effect = lambda key, default=None: {
                "image_generation.base_url": "http://localhost:7860",
                "image_generation.default_height": 1024,
                "image_generation.default_width": 1024,
                "image_generation.default_cfg_scale": 5,
                "image_generation.default_mode": "base",
                "image_generation.default_steps": 50,
                "image_generation.default_samples": 1,
                "image_generation.output_directory": "images",
            }.get(key, default)

            # Initialize service
            service = ImageGenerationService()

            # Verify basic properties
            assert service.base_url == "http://localhost:7860"
            assert service.default_height == 1024
            assert service.default_width == 1024
            assert service.default_cfg_scale == 5
            assert service.default_mode == "base"
            assert service.default_steps == 50
            assert service.default_samples == 1
            assert service.output_directory == "images"

            print("✅ Image generation service initialization test passed")

    def test_generate_image_success(self):
        """Test image generation with mocked API response"""
        print("🧪 Testing Image Generation...")

        # Create a fake base64 image data
        fake_image_data = b"fake_image_data_for_testing"
        fake_base64_data = base64.b64encode(fake_image_data).decode("utf-8")

        # Mock all the external dependencies
        with (
            patch("hnfm.video.image_generator.config_manager") as mock_config,
            patch("hnfm.video.image_generator.requests.post") as mock_requests,
        ):
            # Mock config values
            mock_config.get.side_effect = lambda key, default=None: {
                "image_generation.base_url": "http://localhost:7860",
                "image_generation.default_height": 1024,
                "image_generation.default_width": 1024,
                "image_generation.default_cfg_scale": 5,
                "image_generation.default_mode": "base",
                "image_generation.default_steps": 50,
                "image_generation.default_samples": 1,
                "image_generation.output_directory": "images",
            }.get(key, default)

            # Mock successful API response
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "artifacts": [
                    {
                        "base64": fake_base64_data,
                        "seed": 12345,
                        "finishReason": "SUCCESS",
                    }
                ]
            }
            mock_response.raise_for_status.return_value = None
            mock_requests.return_value = mock_response

            # Initialize service
            service = ImageGenerationService()

            # Test image generation
            test_prompt = "A beautiful sunset over mountains"
            result = service.generate_image(test_prompt)

            # Verify result
            assert "artifacts" in result
            assert len(result["artifacts"]) == 1
            assert result["artifacts"][0]["base64"] == fake_base64_data
            assert result["artifacts"][0]["seed"] == 12345

            # Verify the API was called with correct parameters
            mock_requests.assert_called_once()
            call_args = mock_requests.call_args
            assert call_args[0][0] == "http://localhost:7860/v1/infer"
            assert call_args[1]["json"]["prompt"] == test_prompt
            assert call_args[1]["json"]["height"] == 1024
            assert call_args[1]["json"]["width"] == 1024

            print("✅ Image generation test passed")
