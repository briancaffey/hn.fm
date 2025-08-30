#!/usr/bin/env python3
"""Test script to capture detailed ASR error response."""

import sys
import os
import requests
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_asr_error_details():
    """Test ASR service and capture error details."""
    try:
        # ASR service URL
        base_url = "http://192.168.5.173:8042"

        # Test health first
        logger.info("🔍 Testing ASR service health...")
        health_response = requests.get(f"{base_url}/health", timeout=10)
        logger.info(f"Health status: {health_response.status_code}")
        logger.info(f"Health response: {health_response.text}")

        # Test with a small audio file first
        logger.info("\n🎵 Testing with a small audio file...")

        # Create a minimal test audio file (1 second of silence)
        import numpy as np
        import wave

        # Create a simple 1-second WAV file
        sample_rate = 16000
        duration = 1
        samples = np.zeros(sample_rate * duration, dtype=np.int16)

        test_audio_path = "test_silence.wav"
        with wave.open(test_audio_path, 'w') as wav_file:
            wav_file.setnchannels(1)  # Mono
            wav_file.setsampwidth(2)  # 16-bit
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(samples.tobytes())

        logger.info(f"Created test audio file: {test_audio_path}")

        # Test with the small file
        with open(test_audio_path, 'rb') as audio_file:
            files = {'audio_file': audio_file}
            data = {
                'model_size': 'large-v2',
                'min_speakers': 1,
                'max_speakers': 2
            }

            logger.info("📤 Sending small audio file to ASR service...")
            response = requests.post(
                f"{base_url}/process-audio",
                files=files,
                data=data,
                timeout=60
            )

            logger.info(f"Response status: {response.status_code}")
            logger.info(f"Response headers: {dict(response.headers)}")
            logger.info(f"Response body: {response.text}")

            if response.status_code != 200:
                logger.error(f"❌ ASR failed with status {response.status_code}")
                return False
            else:
                logger.info("✅ Small audio file processed successfully!")
                return True

    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        # Clean up test file
        if os.path.exists("test_silence.wav"):
            os.remove("test_silence.wav")

if __name__ == "__main__":
    logger.info("🧪 Starting ASR error details test...")
    success = test_asr_error_details()
    if success:
        logger.info("✅ Test completed successfully")
    else:
        logger.error("❌ Test failed")
        sys.exit(1)
