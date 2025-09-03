"""TTS service for hn.fm."""

import requests
import logging
import time
import random
import os
from typing import Optional, Tuple, Dict, Any
from pathlib import Path

logger = logging.getLogger(__name__)


class TTSService:
    """Text-to-speech service using local Gradio API."""

    def __init__(self, base_url: str = None):
        """Initialize the TTS service.

        Args:
            base_url: Base URL for the TTS API
        """
        # Use default URL if none provided
        if base_url is None:
            from ..utils.config import config_manager

            base_url = config_manager.get("tts.base_url", "http://localhost:7860")

        # Handle case where base_url might still be None or empty
        if not base_url:
            base_url = "http://localhost:7860"
            logger.warning(
                "No TTS base URL configured, using default: http://localhost:7860"
            )

        self.base_url = base_url.rstrip("/")
        self.max_attempts = int(config_manager.get("tts.max_attempts", 3))
        self.delay_between_attempts = int(config_manager.get("tts.delay_between_batches", 2))

        # Handle timeout_seconds with proper fallback
        timeout_val = config_manager.get("tts.timeout_seconds", 120)
        if isinstance(timeout_val, str) and timeout_val.startswith("${"):
            self.timeout_seconds = 120  # Default fallback
        else:
            self.timeout_seconds = int(timeout_val)

        self.retry_delay = 5  # Fixed value, no config needed

        # Test connection
        self._test_connection()

    def is_healthy(self) -> bool:
        """Check if the TTS service is healthy and responsive.

        Returns:
            True if service is healthy, False otherwise
        """
        try:
            response = requests.get(f"{self.base_url}/config", timeout=5)
            return response.status_code == 200
        except Exception as e:
            logger.debug(f"Health check failed: {e}")
            return False

    def get_timeout_info(self) -> Dict[str, Any]:
        """Get timeout configuration information for debugging.

        Returns:
            Dictionary with timeout settings
        """
        return {
            "timeout_seconds": self.timeout_seconds,
            "retry_delay": self.retry_delay,
            "max_attempts": self.max_attempts,
            "base_url": self.base_url,
        }

    def _test_connection(self):
        """Test connection to the TTS API."""
        try:
            response = requests.get(f"{self.base_url}/config", timeout=10)
            if response.status_code == 200:
                logger.debug("✅ Successfully connected to API")
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

        # Show progress for each line being processed
        first_words = text[:60].replace("\n", " ").strip()
        if len(first_words) >= 60:
            first_words = first_words[:57] + "..."
        logger.info(f"🗣️ Generating audio: {first_words}")

        # Log the full text being processed for debugging
        logger.info(f"📝 Full text being narrated: {text}")

        for attempt in range(1, self.max_attempts + 1):
            try:
                logger.debug(f"🔄 Attempt {attempt}/{self.max_attempts}")

                # Generate random seed for consistency
                seed = random.randint(1, 100000)
                logger.debug(f"🎲 Using seed: {seed}")

                # Generate speech with timeout protection
                audio_data = self._call_tts_api_with_timeout(text, voice, seed)

                if audio_data:
                    logger.debug(
                        f"✅ Successfully generated audio: {len(audio_data)} bytes"
                    )
                    return audio_data

            except Exception as e:
                logger.warning(f"Attempt {attempt} failed: {e}")
                if attempt < self.max_attempts:
                    logger.info(f"Waiting {self.retry_delay} seconds before retry...")
                    time.sleep(self.retry_delay)
                else:
                    logger.error(
                        f"All {self.max_attempts} attempts failed. Last error: {e}"
                    )

        logger.error(f"Failed to generate speech after {self.max_attempts} attempts")
        return None

    def _call_tts_api_with_timeout(
        self, text: str, voice: str, seed: int
    ) -> Optional[bytes]:
        """Call the TTS API with timeout protection.

        Args:
            text: Text to convert
            voice: Voice to use
            seed: Random seed

        Returns:
            Audio data or None if failed
        """
        import threading
        import queue

        result_queue = queue.Queue()
        exception_queue = queue.Queue()

        def _tts_worker():
            """Worker function to run TTS in separate thread."""
            try:
                logger.debug(f"🎵 Starting TTS generation in worker thread...")
                result = self._call_tts_api(text, voice, seed)
                result_queue.put(result)
                logger.debug(f"🎵 TTS worker thread completed successfully")
            except Exception as e:
                logger.error(f"🎵 TTS worker thread failed: {e}")
                exception_queue.put(e)

        # Start TTS worker thread
        worker_thread = threading.Thread(target=_tts_worker, daemon=True)
        worker_thread.start()
        logger.debug(
            f"🎵 TTS worker thread started, waiting up to {self.timeout_seconds}s..."
        )

        # Wait for result with timeout
        try:
            worker_thread.join(timeout=self.timeout_seconds)

            if worker_thread.is_alive():
                logger.warning(
                    f"⏰ TTS request timed out after {self.timeout_seconds} seconds"
                )
                # Try to get a quick response with a shorter timeout
                logger.info("🔄 Attempting quick retry with shorter timeout...")
                worker_thread.join(timeout=30)  # 30 second quick retry

                if worker_thread.is_alive():
                    logger.error("⏰ Quick retry also timed out, giving up")
                    return None
                else:
                    logger.info("✅ Quick retry succeeded")

            # Check for exceptions
            try:
                exception = exception_queue.get_nowait()
                logger.error(f"❌ TTS worker thread failed: {exception}")
                return None
            except queue.Empty:
                pass

            # Get result
            try:
                result = result_queue.get_nowait()
                if result:
                    logger.debug(
                        f"✅ TTS worker thread returned {len(result)} bytes of audio data"
                    )
                else:
                    logger.warning("⚠️ TTS worker thread returned None")
                return result
            except queue.Empty:
                logger.error("❌ TTS worker thread completed but no result available")
                return None

        except Exception as e:
            logger.error(f"❌ Error in timeout wrapper: {e}")
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
            logger.debug("🎵 Calling real TTS API using gradio_client")

            # Import gradio_client here to avoid dependency issues
            try:
                from gradio_client import Client
            except ImportError:
                logger.error(
                    "gradio_client not installed. Install with: pip install gradio-client"
                )
                return None

            # Initialize the client silently
            client = Client(self.base_url)

            # Clean the text for TTS (replace problematic characters)
            cleaned_text = self._clean_text_for_tts(text)

            # Log the text cleaning process
            logger.debug(
                f"🧹 Text cleaning: '{text[:50]}...' → '{cleaned_text[:50]}...'"
            )

            # Prepare the text input - append new line and [S1] to prevent early cutoff
            full_text = cleaned_text + " \n[S1]"
            logger.debug(f"📝 Full text being sent: {full_text[:100]}...")
            logger.debug(f"🎲 Using seed: {seed}")

            # Load voice sample files for voice consistency
            voice_sample_text = self._load_voice_sample_text(voice)
            voice_sample_audio_path = self._load_voice_sample_audio(voice)

            logger.debug(f"🎤 Using voice: {voice}")
            if voice_sample_text:
                logger.debug(f"📝 Voice sample text: {voice_sample_text[:50]}...")
            else:
                logger.warning(f"⚠️  No voice sample text found for voice: {voice}")
            if voice_sample_audio_path:
                logger.debug(f"🎵 Voice sample audio: {voice_sample_audio_path}")
            else:
                logger.warning(f"⚠️  No voice sample audio found for voice: {voice}")

            # Import handle_file for proper audio file handling
            try:
                from gradio_client import handle_file
            except ImportError:
                logger.error(
                    "gradio_client not installed. Install with: pip install gradio-client"
                )
                return None

            # Make the API call with the correct structure based on your working implementation
            result = client.predict(
                text_input=full_text,
                audio_prompt_text_input=voice_sample_text or "",  # Voice sample text
                audio_prompt_input=(
                    handle_file(voice_sample_audio_path)
                    if voice_sample_audio_path
                    else None
                ),  # Voice sample audio file
                max_new_tokens=3072,
                cfg_scale=3,
                temperature=1.8,
                top_p=0.95,
                cfg_filter_top_k=45,
                speed_factor=1,
                seed=seed,
                api_name="/generate_audio",
            )

            logger.debug(f"📥 Received result from API")

            # Handle the result - it might be a tuple or single path
            if isinstance(result, tuple):
                # If it's a tuple, the first element should be the file path
                result_path = result[0] if len(result) > 0 else None
                logger.debug(f"📦 API returned tuple with {len(result)} elements")
            else:
                result_path = result

                # The result should be a file path to the generated audio
            if result_path and os.path.exists(result_path):
                logger.debug(f"📁 Audio file generated at: {result_path}")

                # Get audio duration
                duration = self._get_audio_duration(result_path)
                if duration:
                    logger.debug(f"⏱️  Audio duration: {duration:.1f}s")

                # Read the audio file and return as bytes
                with open(result_path, "rb") as f:
                    audio_data = f.read()

                logger.debug(
                    f"✅ Successfully read audio file: {len(audio_data)} bytes"
                )
                return audio_data
            else:
                logger.error(f"❌ API returned invalid result: {result}")
                return None

        except Exception as e:
            logger.error(f"TTS API call failed: {e}")
            return None

    def _load_voice_sample_text(self, voice: str) -> Optional[str]:
        """Load the voice sample text from the voices directory.

        Args:
            voice: Voice name (e.g., 'notebooklm')

        Returns:
            Voice sample text or None if not found
        """
        try:
            voice_dir = Path("voices") / voice
            sample_text_path = voice_dir / "sample.txt"

            if sample_text_path.exists():
                with open(sample_text_path, "r", encoding="utf-8") as f:
                    return f.read().strip()
            else:
                logger.warning(f"Voice sample text not found: {sample_text_path}")
                return None

        except Exception as e:
            logger.warning(f"Failed to load voice sample text: {e}")
            return None

    def _load_voice_sample_audio(self, voice: str) -> Optional[str]:
        """Load the voice sample audio file path from the voices directory.

        Args:
            voice: Voice name (e.g., 'notebooklm')

        Returns:
            Path to voice sample audio file or None if not found
        """
        try:
            voice_dir = Path("voices") / voice
            sample_audio_path = voice_dir / "sample.wav"

            if sample_audio_path.exists():
                return str(sample_audio_path)
            else:
                logger.warning(f"Voice sample audio not found: {sample_audio_path}")
                return None

        except Exception as e:
            logger.warning(f"Failed to load voice sample audio: {e}")
            return None

    def _clean_text_for_tts(self, text: str) -> str:
        """Clean text for better TTS results by replacing problematic characters.

        Args:
            text: Raw text to clean

        Returns:
            Cleaned text suitable for TTS
        """
        logger.debug(f"🧹 Cleaning text: '{text[:100]}...'")

        # replace ‑ with -
        cleaned = text.replace("‑", "-")

        # Replace curly quotes and apostrophes with straight ones
        cleaned = cleaned.replace("“", '"').replace(
            "”", '"'
        )  # Curly double quotes to straight quotes
        cleaned = cleaned.replace("‘", "'").replace(
            "’", "'"
        )  # Curly single quotes/apostrophes to straight ones

        # Replace other problematic characters
        cleaned = cleaned.replace("–", "-")  # En dash to hyphen
        cleaned = cleaned.replace("—", "-")  # Em dash to hyphen
        cleaned = cleaned.replace("…", "...")  # Ellipsis to three dots

        # remove stars
        cleaned = cleaned.replace("*", "")

        # Remove any other non-ASCII characters that might cause issues
        cleaned = cleaned.encode("ascii", "replace").decode("ascii")

        logger.debug(
            f"🧹 Text cleaning complete: {len(text)} chars → {len(cleaned)} chars"
        )
        logger.debug(f"🧹 Before: '{text[:100]}...'")
        logger.debug(f"🧹 After:  '{cleaned[:100]}...'")

        return cleaned

    def _get_audio_duration(self, file_path: str) -> Optional[float]:
        """Get the duration of a WAV file in seconds.

        Args:
            file_path: Path to the WAV file

        Returns:
            Duration in seconds or None if failed
        """
        try:
            import wave

            with wave.open(file_path, "rb") as wav_file:
                frames = wav_file.getnframes()
                rate = wav_file.getframerate()
                duration = frames / float(rate)
                return duration
        except Exception as e:
            logger.debug(f"Could not determine audio duration: {e}")
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
                    stream=True,
                )

                if response.status_code != 200:
                    raise RuntimeError(
                        f"Failed to get job status: {response.status_code}"
                    )

                # Check for completion
                for line in response.iter_lines():
                    if line:
                        line_str = line.decode("utf-8")
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
                logger.debug("📥 Received result from API")
                logger.debug(
                    f"📦 API returned tuple with {len(response.content)} elements"
                )
                return response.content
            else:
                raise RuntimeError(
                    f"Failed to get audio result: {response.status_code}"
                )

        except Exception as e:
            logger.error(f"Failed to get audio result: {e}")
            return None
