#!/usr/bin/env python3
"""Test script for text cleaning functionality."""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from hnfm.audio.tts_service import TTSService


def test_text_cleaning():
    """Test the text cleaning functionality."""
    print("🧪 Testing Text Cleaning...")

    # Initialize TTS service
    tts = TTSService(base_url="http://192.168.5.96:7860")

    # Test individual characters
    test_cases = [
        ("'", "'", "curly apostrophe"),
        ("'", "'", "curly apostrophe"),
        ('"', '"', "curly quote"),
        ('"', '"', "curly quote"),
        ("–", "-", "en dash"),
        ("—", "-", "em dash"),
        ("…", "...", "ellipsis"),
    ]

    for original, expected, description in test_cases:
        print(f"\n📝 Testing {description}:")
        print(f"   Original: '{original}'")

        # Test the cleaning method
        cleaned = tts._clean_text_for_tts(original)
        print(f"   Cleaned:  '{cleaned}'")

        if cleaned == expected:
            print("   ✅ Correctly replaced!")
        else:
            print(f"   ❌ Expected '{expected}', got '{cleaned}'")

    # Test a full sentence
    print(f"\n📝 Testing full sentence:")
    test_sentence = "I'm Alex, and today we've got a pretty cool topic."
    print(f"   Original: '{test_sentence}'")

    cleaned_sentence = tts._clean_text_for_tts(test_sentence)
    print(f"   Cleaned:  '{cleaned_sentence}'")

    # Check for problematic characters
    problematic_chars = ["'", "'", '"', '"', "–", "—", "…"]
    found_problematic = [char for char in problematic_chars if char in cleaned_sentence]

    if found_problematic:
        print(f"   ❌ Still has problematic characters: {found_problematic}")
    else:
        print("   ✅ All problematic characters replaced!")


if __name__ == "__main__":
    test_text_cleaning()
