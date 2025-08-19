#!/usr/bin/env python3
"""Test script for TTS service integration and text cleaning."""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from hnfm.audio.tts_service import TTSService


def test_tts_integration():
    """Test the TTS service integration."""
    print("🧪 Testing TTS Service Integration...")

    # Initialize TTS service
    tts = TTSService(base_url="http://192.168.5.96:7860")

    # Test text with problematic characters
    test_text = "It's about D2 – the text‑to‑diagram tool that turns plain language into visuals."

    print(f"📝 Test text: '{test_text}'")

    # Test text cleaning directly
    print("\n🧹 Testing text cleaning:")
    cleaned = tts._clean_text_for_tts(test_text)
    print(f"   Before: '{test_text}'")
    print(f"   After:  '{cleaned}'")

    # Check if problematic characters were replaced
    problematic_chars = ["–", "‑"]
    found_problematic = [char for char in problematic_chars if char in cleaned]

    if found_problematic:
        print(f"   ❌ Still has problematic characters: {found_problematic}")
    else:
        print("   ✅ All problematic characters replaced!")

    # Test voice sample loading
    print("\n🎤 Testing voice sample loading:")
    voice_sample_text = tts._load_voice_sample_text("notebooklm")
    voice_sample_audio = tts._load_voice_sample_audio("notebooklm")

    print(f"   Voice sample text: {voice_sample_text}")
    print(f"   Voice sample audio: {voice_sample_audio}")

    if voice_sample_text and voice_sample_audio:
        print("   ✅ Voice samples loaded successfully!")
    else:
        print("   ❌ Voice samples not loaded!")


if __name__ == "__main__":
    test_tts_integration()
