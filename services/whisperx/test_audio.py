#!/usr/bin/env python3
"""
Simple test script for WhisperX audio processing
Run this with: python test_audio.py
Make sure to set: export HF_TOKEN='your_token_here'
"""

import os
from client import WhisperXClient

def main():
    """Test audio processing with HF_TOKEN from environment"""

    # Check if HF_TOKEN is set
    if not os.getenv('HF_TOKEN'):
        print("❌ HF_TOKEN environment variable not set!")
        print("\n💡 To fix this:")
        print("   export HF_TOKEN='your_huggingface_token_here'")
        print("   Then run this script again")
        return

    try:
        # Initialize client
        client = WhisperXClient()

        # Check server health
        print("🔍 Checking server health...")
        health = client.health_check()
        print(f"✅ Server is healthy: {health}")

        # Process the audio file
        print("\n🎵 Processing audio.wav...")
        results = client.process_audio(
            audio_file_path="audio.wav",
            model_size="large-v2"
        )

        # Print results
        client.print_results(results)

        # Save results to JSON
        filename = client.save_results_to_json(results)
        print(f"\n🎉 Audio processing complete! Results saved to: {filename}")

    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    main()
