#!/usr/bin/env python3
"""Simple TTS service tests for hn.fm"""

import os
import sys
import pytest
from unittest.mock import patch, MagicMock

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from hnfm.audio.tts_service import TTSService


class TestTTSService:
    """Simple TTS service tests"""

    def test_tts_service_initialization(self):
        """Test that TTS service can be initialized"""
        print("🧪 Testing TTS Service Initialization...")

        # Mock the config manager and requests to avoid real API calls
        with (
            patch("hnfm.utils.config.config_manager") as mock_config,
            patch("hnfm.audio.tts_service.requests.get") as mock_requests,
        ):

            # Mock config values
            mock_config.get.side_effect = lambda key, default=None: {
                "tts.base_url": "http://localhost:7860",
                "tts.max_attempts": 3,
                "tts.delay_between_batches": 2,
                "tts.timeout_seconds": 120,
                "tts.retry_delay": 5,
            }.get(key, default)

            # Mock successful connection test
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_requests.return_value = mock_response

            # Initialize service
            tts_service = TTSService()

            # Verify basic properties
            assert tts_service.base_url == "http://localhost:7860"
            assert tts_service.max_attempts == 3

            print("✅ TTS service initialization test passed")

    def test_tts_generate_speech_success(self):
        """Test TTS speech generation with mocked gradio client"""
        print("🧪 Testing TTS Speech Generation...")

        # Mock all the external dependencies
        with (
            patch("hnfm.utils.config.config_manager") as mock_config,
            patch("hnfm.audio.tts_service.requests.get") as mock_requests,
            patch("gradio_client.Client") as mock_client_class,
            patch("gradio_client.handle_file") as mock_handle_file,
            patch("builtins.open", create=True) as mock_file_open,
            patch("os.path.exists") as mock_exists,
        ):

            # Mock config values
            mock_config.get.side_effect = lambda key, default=None: {
                "tts.base_url": "http://localhost:7860",
                "tts.max_attempts": 3,
                "tts.delay_between_batches": 2,
                "tts.timeout_seconds": 120,
                "tts.retry_delay": 5,
            }.get(key, default)

            # Mock successful connection test
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_requests.return_value = mock_response

            # Mock file operations
            mock_exists.return_value = True
            fake_audio_data = b"fake_audio_data_for_testing"
            mock_file = MagicMock()
            mock_file.read.return_value = fake_audio_data
            mock_file_open.return_value.__enter__.return_value = mock_file

            # Mock gradio client
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client
            mock_client.predict.return_value = "/tmp/fake_audio.wav"

            # Mock handle_file
            mock_handle_file.return_value = "mock_file_handle"

            # Initialize service
            tts_service = TTSService()

            # Test speech generation
            test_text = "Hello, this is a test message for TTS."
            audio_data = tts_service.generate_speech(test_text, voice="notebooklm")

            # Verify result
            assert audio_data == fake_audio_data, "Should return the mocked audio data"
            assert mock_client.predict.called, "Should have called the gradio client"

            print("✅ TTS speech generation test passed")
