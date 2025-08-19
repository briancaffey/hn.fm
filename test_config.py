#!/usr/bin/env python3
"""Test script for configuration loading."""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))


def test_config_loading():
    """Test if configuration is loading environment variables correctly."""
    try:
        from hnfm.utils.config import ConfigManager

        config_manager = ConfigManager()

        print("🧪 Testing Configuration Loading...")
        print()

        # Test TTS configuration
        print("🎵 TTS Configuration:")
        tts_base_url = config_manager.get("tts.base_url")
        tts_voice = config_manager.get("tts.default_voice")
        print(f"   Base URL: {tts_base_url}")
        print(f"   Default Voice: {tts_voice}")
        print()

        # Test Studio Voice configuration
        print("🎤 Studio Voice Configuration:")
        studio_target = config_manager.get("studio_voice.target")
        studio_model = config_manager.get("studio_voice.model_type")
        print(f"   Target: {studio_target}")
        print(f"   Model Type: {studio_model}")
        print()

        # Test LLM configuration
        print("🤖 LLM Configuration:")
        llm_base_url = config_manager.get("llm.base_url")
        llm_fallback = config_manager.get("llm.fallback_url")
        llm_model = config_manager.get("llm.model")
        print(f"   Base URL: {llm_base_url}")
        print(f"   Fallback URL: {llm_fallback}")
        print(f"   Model: {llm_model}")
        print()

        # Test API configuration
        print("🔌 API Configuration:")
        firecrawl_url = config_manager.get("apis.firecrawl.base_url")
        firecrawl_key = config_manager.get("apis.firecrawl.api_key")
        print(f"   Firecrawl URL: {firecrawl_url}")
        print(f"   Firecrawl Key: {'***' if firecrawl_key else 'Not set'}")
        print()

        # Test development configuration
        print("🛠️  Development Configuration:")
        debug = config_manager.get("development.debug")
        log_level = config_manager.get("development.log_level")
        print(f"   Debug: {debug}")
        print(f"   Log Level: {log_level}")
        print()

        # Check for missing required values
        required_vars = [
            ("TTS_BASE_URL", tts_base_url),
            ("STUDIO_VOICE_TARGET", studio_target),
            ("LLM_BASE_URL", llm_base_url),
        ]

        missing_vars = [var for var, value in required_vars if not value]

        if missing_vars:
            print("⚠️  Missing required environment variables:")
            for var in missing_vars:
                print(f"   - {var}")
            print()
            print("💡 Make sure to copy env.example to .env and fill in the values")
            return False
        else:
            print("✅ All required environment variables are set!")
            return True

    except Exception as e:
        print(f"❌ Configuration test failed: {e}")
        return False


if __name__ == "__main__":
    success = test_config_loading()
    sys.exit(0 if success else 1)
