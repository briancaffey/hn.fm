"""TTS service for hn.fm."""

import requests
import logging
import time
import random
import os
from typing import Optional, Tuple
from pathlib import Path

logger = logging.getLogger(__name__)


class TTSService:
    """Text-to-speech service using local Gradio API."""

    def __init__(self, base_url: str = "http://192.168.5.96:7860"):
        """Initialize the TTS service.

        Args:
            base_url: Base URL for the TTS API
        """
        self.base_url = base_url.rstrip('/')
        self.max_attempts = 3
        self.delay_between_attempts = 2

        # Test connection
        self._test_connection()

    def _test_connection(self):
        """Test connection to the TTS API."""
        try:
            response = requests.get(f"{self.base_url}/config", timeout=5)
            if response.status_code == 200:
                logger.info("✅ Successfully connected to API")
            else:
                logger.warning(f"TTS API returned status {response.status_code}")
        except Exception as e:
            logger.warning(f"Could not connect to TTS API: {e}")

    def generate_speech(self, text: str, voice: str = "notebooklm") -> Optional[bytes]:
        """Generate speech from text.

        Args:
            text: Text to convert to speech
            voice: Voice to use

        Returns:
            Audio data as bytes or None if failed
        """
        if not text.strip():
            logger.warning("Empty text provided for TTS")
            return None

        logger.info(f"🎵 Generating audio for text: {text[:50]}...")
        logger.info(f"📝 Complete text being sent to API: {text}")
        logger.info(f"📝 Text length: {len(text)} characters")

        for attempt in range(1, self.max_attempts + 1):
            try:
                logger.info(f"🔄 Attempt {attempt}/{self.max_attempts}")

                # Generate random seed for consistency
                seed = random.randint(1, 100000)
                logger.info(f"🎲 Using seed: {seed}")

                # Generate speech
                audio_data = self._call_tts_api(text, voice, seed)

                if audio_data:
                    logger.info(f"✅ Successfully generated audio: {len(audio_data)} bytes")
                    return audio_data

            except Exception as e:
                logger.warning(f"Attempt {attempt} failed: {e}")
                if attempt < self.max_attempts:
                    time.sleep(self.delay_between_attempts)

        logger.error(f"Failed to generate speech after {self.max_attempts} attempts")
        return None

    def _call_tts_api(self, text: str, voice: str, seed: int) -> Optional[bytes]:
        """Call the TTS API.

        Args:
            text: Text to convert
            voice: Voice to use
            seed: Random seed

        Returns:
            Audio data or None if failed
        """
        try:
            logger.info("🎵 Calling real TTS API using gradio_client")

            # Import gradio_client here to avoid dependency issues
            try:
                from gradio_client import Client
            except ImportError:
                logger.error("gradio_client not installed. Install with: pip install gradio-client")
                return None

            # Initialize the client
            client = Client(self.base_url)
            logger.info(f"🔌 Connected to Gradio API at {self.base_url}")

            # Prepare the text input - append "That's it." to prevent early cutoff
            full_text = text + " That's it."
            logger.info(f"📝 Full text being sent: {full_text[:100]}...")
            logger.info(f"🎲 Using seed: {seed}")

            # Make the API call with the correct structure based on your working implementation
            result = client.predict(
                text_input=full_text,
                audio_prompt_text_input="",  # Empty for text-only generation
                audio_prompt_input=None,     # No audio prompt
                max_new_tokens=3072,
                cfg_scale=3,
                temperature=1.8,
                top_p=0.95,
                cfg_filter_top_k=45,
                speed_factor=1,
                seed=seed,
                api_name="/generate_audio"
            )

            logger.info(f"📥 Received result from API")

            # Handle the result - it might be a tuple or single path
            if isinstance(result, tuple):
                # If it's a tuple, the first element should be the file path
                result_path = result[0] if len(result) > 0 else None
                logger.info(f"📦 API returned tuple with {len(result)} elements")
            else:
                result_path = result

            # The result should be a file path to the generated audio
            if result_path and os.path.exists(result_path):
                logger.info(f"📁 Audio file generated at: {result_path}")

                # Read the audio file and return as bytes
                with open(result_path, 'rb') as f:
                    audio_data = f.read()

                logger.info(f"✅ Successfully read audio file: {len(audio_data)} bytes")
                return audio_data
            else:
                logger.error(f"❌ API returned invalid result: {result}")
                return None

        except Exception as e:
            logger.error(f"TTS API call failed: {e}")
            return None

    def _wait_for_completion(self, session_hash: str) -> Optional[bytes]:
        """Wait for TTS job completion.

        Args:
            session_hash: Session hash from job submission

        Returns:
            Audio data or None if failed
        """
        try:
            # Poll for completion
            while True:
                response = requests.get(
                    f"{self.base_url}/gradio_api/queue/data?session_hash={session_hash}",
                    stream=True
                )

                if response.status_code != 200:
                    raise RuntimeError(f"Failed to get job status: {response.status_code}")

                # Check for completion
                for line in response.iter_lines():
                    if line:
                        line_str = line.decode('utf-8')
                        if '"msg": "process_completed"' in line_str:
                            # Get the result
                            audio_data = self._get_audio_result(session_hash)
                            return audio_data

                time.sleep(0.1)

        except Exception as e:
            logger.error(f"Failed to wait for completion: {e}")
            return None

    def _get_audio_result(self, session_hash: str) -> Optional[bytes]:
        """Get audio result from completed job.

        Args:
            session_hash: Session hash

        Returns:
            Audio data or None if failed
        """
        try:
            # Get the audio file
            response = requests.get(
                f"{self.base_url}/gradio_api/file=/tmp/gradio/{session_hash}/audio.wav"
            )

            if response.status_code == 200:
                logger.info("📥 Received result from API")
                logger.info(f"📦 API returned tuple with {len(response.content)} elements")
                return response.content
            else:
                raise RuntimeError(f"Failed to get audio result: {response.status_code}")

        except Exception as e:
            logger.error(f"Failed to get audio result: {e}")
            return None
