"""ASR (Automatic Speech Recognition) service for hn.fm."""

import os
import requests
import logging
from typing import Optional, Dict, Any
from pathlib import Path

from ..utils.config import config_manager

logger = logging.getLogger(__name__)


class ASRService:
    """Service for processing audio through WhisperX ASR."""

    def __init__(self):
        """Initialize the ASR service."""
        self.base_url = config_manager.get("asr.base_url")
        self.model_size = config_manager.get("asr.model_size", "large-v2")
        self.min_speakers = config_manager.get("asr.min_speakers", 1)
        self.max_speakers = config_manager.get("asr.max_speakers", 2)

        # Get HF token from environment variable
        self.hf_token = os.getenv('HF_TOKEN')

        if not self.base_url:
            raise ValueError("ASR base URL not configured. Please set asr.base_url in config.")

        self.base_url = self.base_url.rstrip('/')

        if not self.hf_token:
            logger.warning("HF_TOKEN environment variable not set. ASR may not work properly.")

    def health_check(self) -> Dict[str, Any]:
        """Check ASR server health.

        Returns:
            Health check response from the server

        Raises:
            requests.exceptions.RequestException: If health check fails
        """
        try:
            response = requests.get(f"{self.base_url}/health", timeout=10)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"ASR health check failed: {e}")
            raise

    def process_audio(
        self,
        audio_file_path: str,
        model_size: Optional[str] = None,
        min_speakers: Optional[int] = None,
        max_speakers: Optional[int] = None
    ) -> Dict[str, Any]:
        """Process audio file through ASR service.

        Args:
            audio_file_path: Path to the audio file to process
            model_size: Whisper model size (defaults to config value)
            min_speakers: Minimum number of speakers (defaults to config value)
            max_speakers: Maximum number of speakers (defaults to config value)

        Returns:
            ASR processing results as a dictionary

        Raises:
            FileNotFoundError: If audio file doesn't exist
            requests.exceptions.RequestException: If ASR request fails
        """
        if not Path(audio_file_path).exists():
            raise FileNotFoundError(f"Audio file not found: {audio_file_path}")

        # Use provided values or fall back to defaults
        model_size = model_size or self.model_size
        min_speakers = min_speakers if min_speakers is not None else self.min_speakers
        max_speakers = max_speakers if max_speakers is not None else self.max_speakers

        logger.info(f"🎙️ Processing audio through ASR service: {self.base_url}")
        logger.info(f"📁 Audio file: {audio_file_path}")
        logger.info(f"🎯 Model: {model_size}, Speakers: {min_speakers}-{max_speakers}")

        # Prepare the request
        files = {'audio_file': open(audio_file_path, 'rb')}
        data = {
            'model_size': model_size,
        }

        # Add HF token if available
        if self.hf_token:
            data['hf_token'] = self.hf_token

        # Add speaker constraints if specified
        if min_speakers is not None:
            data['min_speakers'] = min_speakers
        if max_speakers is not None:
            data['max_speakers'] = max_speakers

        try:
            # Make the request
            response = requests.post(
                f"{self.base_url}/process-audio",
                files=files,
                data=data,
                timeout=300  # 5 minute timeout for audio processing
            )

            response.raise_for_status()
            results = response.json()

            logger.info(f"✅ ASR processing completed successfully")
            logger.info(f"📊 Results: {len(results.get('segments', []))} segments, {results.get('language', 'Unknown')} language")

            return results

        except requests.exceptions.Timeout:
            logger.error("ASR request timed out after 5 minutes")
            raise RuntimeError("ASR processing timed out")
        except requests.exceptions.RequestException as e:
            logger.error(f"ASR request failed: {e}")
            raise RuntimeError(f"ASR processing failed: {e}")
        except Exception as e:
            logger.error(f"Unexpected error during ASR processing: {e}")
            raise RuntimeError(f"ASR processing failed: {e}")
        finally:
            # Always close the file
            if 'audio_file' in files and hasattr(files['audio_file'], 'close'):
                files['audio_file'].close()

    def save_results(self, results: Dict[str, Any], output_path: str) -> str:
        """Save ASR results to a JSON file.

        Args:
            results: ASR processing results
            output_path: Path where to save the results

        Returns:
            Path to the saved file
        """
        import json

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)

        logger.info(f"💾 ASR results saved to: {output_path}")
        return str(output_path)

    def process_and_save(
        self,
        audio_file_path: str,
        output_path: str,
        model_size: Optional[str] = None,
        min_speakers: Optional[int] = None,
        max_speakers: Optional[int] = None
    ) -> Dict[str, Any]:
        """Process audio and save results in one operation.

        Args:
            audio_file_path: Path to the audio file to process
            output_path: Path where to save the results
            model_size: Whisper model size (defaults to config value)
            min_speakers: Minimum number of speakers (defaults to config value)
            max_speakers: Maximum number of speakers (defaults to config value)

        Returns:
            ASR processing results
        """
        # Process the audio
        results = self.process_audio(
            audio_file_path=audio_file_path,
            model_size=model_size,
            min_speakers=min_speakers,
            max_speakers=max_speakers
        )

        # Save the results
        self.save_results(results, output_path)

        return results
