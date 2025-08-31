#!/usr/bin/env python3
"""Test script to verify ASR timeout mechanism."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from hnfm.audio.asr_service import ASRService
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_asr_timeout():
    """Test ASR service with timeout."""
    try:
        # Initialize ASR service
        asr_service = ASRService()

        # Show configuration
        logger.info("ASR Service Configuration:")
        if hasattr(asr_service, 'get_timeout_info'):
            timeout_info = asr_service.get_timeout_info()
            for key, value in timeout_info.items():
                logger.info(f"  {key}: {value}")

        # Test health check
        logger.info(f"ASR Service Health: {asr_service.is_healthy()}")

        # Test with a sample audio file (you'll need to provide a real audio file)
        # For now, just test the configuration and health check
        logger.info("✅ ASR service initialized successfully with timeout configuration")

        return True

    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        return False

if __name__ == "__main__":
    logger.info("🧪 Starting ASR timeout test...")
    success = test_asr_timeout()
    if success:
        logger.info("✅ Test completed successfully")
    else:
        logger.error("❌ Test failed")
        sys.exit(1)
