#!/usr/bin/env python3
"""Test script to test ASR service directly with audio file."""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from hnfm.audio.asr_service import ASRService
import logging

# Set up logging
logging.basicConfig(
    level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def test_asr_with_audio():
    """Test ASR service with actual audio file."""
    try:
        # Initialize ASR service
        asr_service = ASRService()

        # Show configuration
        logger.info("ASR Service Configuration:")
        if hasattr(asr_service, "get_timeout_info"):
            timeout_info = asr_service.get_timeout_info()
            for key, value in timeout_info.items():
                logger.info(f"  {key}: {value}")

        # Test health check
        logger.info(f"ASR Service Health: {asr_service.is_healthy()}")

        # Test with the AlphaSuite audio file
        audio_file_path = "outputs/show_hn_alphasuite_an_open_source_platform_for_quantitative_stock_analysis_68af3b/audio/show_hn_alphasuite_an_open_source_platform_for_quantitative_stock_analysis_final.wav"

        if not os.path.exists(audio_file_path):
            logger.error(f"❌ Audio file not found: {audio_file_path}")
            return False

        logger.info(f"🎵 Testing ASR with audio file: {audio_file_path}")

        # Get file info
        file_size = os.path.getsize(audio_file_path)
        logger.info(f"📁 File size: {file_size / (1024*1024):.2f} MB")

        # Test ASR processing
        logger.info("🎙️ Starting ASR processing...")
        results = asr_service.process_audio(audio_file_path)

        if results:
            logger.info(f"✅ ASR completed successfully!")
            logger.info(f"📊 Results: {len(results.get('segments', []))} segments")
            logger.info(f"🌍 Language: {results.get('language', 'Unknown')}")
            return True
        else:
            logger.error("❌ ASR returned None")
            return False

    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    logger.info("🧪 Starting ASR audio test...")
    success = test_asr_with_audio()
    if success:
        logger.info("✅ Test completed successfully")
    else:
        logger.error("❌ Test failed")
        sys.exit(1)
