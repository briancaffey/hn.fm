import requests
import json
import os
from typing import Optional, Dict, Any
from datetime import datetime

class WhisperXClient:
    """Client for the WhisperX FastAPI server"""

    def __init__(self, base_url: str = "http://localhost:8042"):
        self.base_url = base_url.rstrip('/')
        # Get HF token from environment variable
        self.hf_token = os.getenv('HF_TOKEN')
        if not self.hf_token:
            raise ValueError("HF_TOKEN environment variable not set. Please export HF_TOKEN='your_token_here'")

    def health_check(self) -> Dict[str, Any]:
        """Check server health"""
        response = requests.get(f"{self.base_url}/health")
        response.raise_for_status()
        return response.json()

    def process_audio(
        self,
        audio_file_path: str,
        model_size: str = "large-v2",
        min_speakers: Optional[int] = None,
        max_speakers: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Process audio file with transcription and speaker diarization

        Args:
            audio_file_path: Path to the audio file
            model_size: Whisper model size
            min_speakers: Minimum number of speakers
            max_speakers: Maximum number of speakers

        Returns:
            API response with transcription and diarization results
        """

        # Open the file and keep it open for the request
        audio_file = open(audio_file_path, 'rb')

        try:
            # Prepare the files and data for the request
            files = {'audio_file': audio_file}
            data = {
                'model_size': model_size,
                'hf_token': self.hf_token
            }

            if min_speakers is not None:
                data['min_speakers'] = min_speakers
            if max_speakers is not None:
                data['max_speakers'] = max_speakers

            # Make the request
            response = requests.post(
                f"{self.base_url}/process-audio",
                files=files,
                data=data
            )

            response.raise_for_status()
            return response.json()

        finally:
            # Always close the file
            audio_file.close()

    def save_results_to_json(self, results: Dict[str, Any], filename: Optional[str] = None) -> str:
        """Save results to a JSON file with timestamp"""
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"whisperx_results_{timestamp}.json"

        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)

        print(f"💾 Results saved to: {filename}")
        return filename

    def print_results(self, results: Dict[str, Any]) -> None:
        """Pretty print the results in a readable format"""
        print("=" * 80)
        print("WHISPERX AUDIO PROCESSING RESULTS")
        print("=" * 80)

        # Print metadata
        metadata = results.get('metadata', {})
        print(f"\n📊 METADATA:")
        print(f"   Language: {results.get('language', 'Unknown')}")
        print(f"   Model Size: {metadata.get('model_size', 'Unknown')}")
        print(f"   Device: {metadata.get('device', 'Unknown')}")
        print(f"   Audio Duration: {metadata.get('audio_duration', 0):.2f} seconds")
        print(f"   Number of Segments: {metadata.get('num_segments', 0)}")
        print(f"   Number of Speakers: {metadata.get('num_speakers', 0)}")

        # Print segments with speaker information
        segments = results.get('segments', [])
        if segments:
            print(f"\n🎤 TRANSCRIPTION WITH SPEAKER DIARIZATION:")
            print("-" * 80)

            for i, segment in enumerate(segments):
                start_time = segment.get('start', 0)
                end_time = segment.get('end', 0)
                speaker = segment.get('speaker', 'UNKNOWN')
                text = segment.get('text', '').strip()

                # Format timestamps
                start_str = f"{int(start_time//60):02d}:{start_time%60:05.2f}"
                end_str = f"{int(end_time//60):02d}:{end_time%60:05.2f}"

                print(f"[{start_str} → {end_str}] Speaker {speaker}: {text}")

        print("\n" + "=" * 80)

def main():
    """Example usage of the WhisperX client"""

    try:
        # Initialize client (will check for HF_TOKEN)
        client = WhisperXClient()
    except ValueError as e:
        print(f"❌ Configuration Error: {e}")
        print("\n💡 To fix this:")
        print("   export HF_TOKEN='your_huggingface_token_here'")
        print("   Then run this script again")
        return

    try:
        # Check server health
        print("🔍 Checking server health...")
        health = client.health_check()
        print(f"✅ Server is healthy: {health}")

        # Example audio processing
        print("\n🎵 Processing audio file...")

        # Use the actual audio file in the project
        audio_file_path = "audio.wav"  # Path to your audio file

        # Process the audio
        results = client.process_audio(
            audio_file_path=audio_file_path,
            model_size="large-v2"
        )

        # Print results
        client.print_results(results)

        # Save results to JSON file
        client.save_results_to_json(results)

    except requests.exceptions.ConnectionError:
        print("❌ Error: Could not connect to the server. Make sure it's running on http://localhost:8042")
    except requests.exceptions.HTTPError as e:
        print(f"❌ HTTP Error: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"Response: {e.response.text}")
    except FileNotFoundError:
        print(f"❌ Error: Audio file not found at {audio_file_path}")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")

if __name__ == "__main__":
    main()
