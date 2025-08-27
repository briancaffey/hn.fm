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
            # Validate input data
            if audio_data is None:
                raise ValueError("Audio data cannot be None")

            if not isinstance(audio_data, bytes):
                raise ValueError(f"Audio data must be bytes, got {type(audio_data)}")

            if len(audio_data) == 0:
                raise ValueError("Audio data cannot be empty")

            file_path = Path(file_path)
            file_path.parent.mkdir(parents=True, exist_ok=True)

            with open(file_path, "wb") as f:
                f.write(audio_data)

            logger.debug(f"Saved audio to: {file_path}")

        except Exception as e:
            logger.error(f"Failed to save audio: {e}")
            raise RuntimeError(f"Audio save failed: {e}")

    def combine_audio_files(
        self, audio_files: List[bytes], output_path: Union[str, Path]
    ):
        """Combine multiple audio files into one.

        Args:
            audio_files: List of audio data as bytes
            output_path: Path for the combined audio file
        """
        try:
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)

            if not audio_files:
                logger.warning("No audio files to combine")
                return

            logger.info(f"Combining {len(audio_files)} audio files...")

            # Read the first file to get audio parameters
            first_audio = io.BytesIO(audio_files[0])
            with wave.open(first_audio, "rb") as first_wav:
                channels = first_wav.getnchannels()
                sample_width = first_wav.getsampwidth()
                sample_rate = first_wav.getframerate()

            # Create output WAV file
            with wave.open(str(output_path), "wb") as output_wav:
                output_wav.setnchannels(channels)
                output_wav.setsampwidth(sample_width)
                output_wav.setframerate(sample_rate)

                # Combine all audio files
                total_frames = 0
                for i, audio_data in enumerate(audio_files):
                    audio_io = io.BytesIO(audio_data)
                    with wave.open(audio_io, "rb") as input_wav:
                        # Verify audio parameters match
                        if (
                            input_wav.getnchannels() != channels
                            or input_wav.getsampwidth() != sample_width
                            or input_wav.getframerate() != sample_rate
                        ):
                            logger.warning(
                                f"Audio file {i+1} has different parameters, skipping"
                            )
                            continue

                        # Read and write frames
                        frames = input_wav.readframes(input_wav.getnframes())
                        output_wav.writeframes(frames)
                        total_frames += input_wav.getnframes()

                        logger.debug(
                            f"Added audio file {i+1}: {input_wav.getnframes()} frames"
                        )

            logger.info(
                f"Successfully combined {len(audio_files)} audio files into: {output_path}"
            )
            logger.info(
                f"Total frames: {total_frames}, Duration: {total_frames/sample_rate:.1f}s"
            )

        except Exception as e:
            logger.error(f"Failed to combine audio files: {e}")
            raise RuntimeError(f"Audio combination failed: {e}")

    def process_audio_for_asr(self, audio_file_path: str, story_dir: Union[str, Path]) -> dict:
        """Process audio file through ASR service and save results.

        Args:
            audio_file_path: Path to the audio file to process
            story_dir: Directory where to save ASR results

        Returns:
            ASR processing results as a dictionary
        """
        try:
            from .asr_service import ASRService

            # Create ASR service instance
            asr_service = ASRService()

            # Process the audio
            results = asr_service.process_audio(audio_file_path)

            return results

        except Exception as e:
            logger.error(f"Failed to process audio for ASR: {e}")
            raise RuntimeError(f"ASR processing failed: {e}")
