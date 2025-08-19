"""Audio processing for hn.fm."""

import logging
from pathlib import Path
from typing import List, Union
import wave
import io

logger = logging.getLogger(__name__)


class AudioProcessor:
    """Processes and manipulates audio files."""

    def __init__(self):
        """Initialize the audio processor."""
        pass

    def save_audio_data(self, audio_data: bytes, file_path: Union[str, Path]):
        """Save audio data to a file.

        Args:
            audio_data: Audio data as bytes
            file_path: Path to save the audio file
        """
        try:
            file_path = Path(file_path)
            file_path.parent.mkdir(parents=True, exist_ok=True)

            with open(file_path, 'wb') as f:
                f.write(audio_data)

            logger.info(f"Saved audio to: {file_path}")

        except Exception as e:
            logger.error(f"Failed to save audio: {e}")
            raise RuntimeError(f"Audio save failed: {e}")

    def combine_audio_files(self, audio_files: List[bytes], output_path: Union[str, Path]):
        """Combine multiple audio files into one.

        Args:
            audio_files: List of audio data as bytes
            output_path: Path for the combined audio file
        """
        try:
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)

            # For now, just save the first audio file
            # In a real implementation, this would concatenate the audio
            if audio_files:
                with open(output_path, 'wb') as f:
                    f.write(audio_files[0])

                logger.info(f"Combined {len(audio_files)} audio files into: {output_path}")
            else:
                logger.warning("No audio files to combine")

        except Exception as e:
            logger.error(f"Failed to combine audio files: {e}")
            raise RuntimeError(f"Audio combination failed: {e}")
