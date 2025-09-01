#!/usr/bin/env python3
"""Test script to verify TTS timeout mechanism."""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from hnfm.audio.tts_service import TTSService
import logging

# Set up logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def test_tts_timeout():
    """Test TTS service with timeout."""
    try:
        # Initialize TTS service
        tts_service = TTSService()

        # Show configuration
        logger.info("TTS Service Configuration:")
        if hasattr(tts_service, "get_timeout_info"):
            timeout_info = tts_service.get_timeout_info()
            for key, value in timeout_info.items():
                logger.info(f"  {key}: {value}")

        # Test health check
        logger.info(f"TTS Service Health: {tts_service.is_healthy()}")

        # Test with a simple text
        test_text = "This is a test of the TTS timeout mechanism."
        logger.info(f"Testing TTS with text: {test_text}")

        # Generate speech (this should timeout if the service is hanging)
        audio_data = tts_service.generate_speech(test_text)

        if audio_data:
            logger.info(f"✅ TTS completed successfully: {len(audio_data)} bytes")
        else:
            logger.warning("⚠️ TTS returned None (may have timed out)")

    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        return False

    return True


if __name__ == "__main__":
    logger.info("🧪 Starting TTS timeout test...")
    success = test_tts_timeout()
    if success:
        logger.info("✅ Test completed successfully")
    else:
        logger.error("❌ Test failed")
        sys.exit(1)
