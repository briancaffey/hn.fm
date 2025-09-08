"""Script generation and audio processing for hn.fm."""

import os
from pathlib import Path
from typing import List, Optional
import logging

from ..audio.tts_api_service import TtsApiService
from ..audio.audio_processor import AudioProcessor
from ..audio.studio_voice_service import StudioVoiceService
from ..utils.config import config_manager
from ..utils.filename_utils import sanitize_filename

logger = logging.getLogger(__name__)


class ScriptGenerator:
    """Generates audio from script lines using TTS and audio enhancement services.

    Note: Script generation (creating [S1]/[S2] formatted scripts from content)
    is now handled by generate_script_v1() in segment_utils.py. This class
    focuses on audio processing: TTS generation, audio enhancement, and combining audio files.
    """

    def __init__(self, output_dir: str = "outputs"):
        """Initialize the script generator.

        Args:
            output_dir: Base output directory
        """
        self.output_dir = Path(output_dir)
        self.tts_service = TtsApiService()
        self.audio_processor = AudioProcessor()

        # Get Studio Voice configuration
        from ..utils.config import ConfigManager

        config_manager = ConfigManager()
        studio_voice_config = config_manager.get("studio_voice", {})
        target = studio_voice_config.get("target")
        model_type = studio_voice_config.get("studio_voice.model_type", "48k-hq")
        streaming = studio_voice_config.get("studio_voice.streaming", False)
        ssl_mode = studio_voice_config.get("studio_voice.ssl_mode")

        if not target:
            raise ValueError("STUDIO_VOICE_TARGET environment variable not set")

        self.studio_voice_service = StudioVoiceService(
            target=target, model_type=model_type, streaming=streaming, ssl_mode=ssl_mode
        )

    def _clean_and_validate_input(self, tts_lines_file: str) -> List[str]:
        """Clean and validate input TTS lines from file.

        Args:
            tts_lines_file: Path to TTS lines file

        Returns:
            List of cleaned TTS lines

        Raises:
            RuntimeError: If no valid lines found
        """
        with open(tts_lines_file, "r", encoding="utf-8") as f:
            lines = [line.strip() for line in f.readlines() if line.strip()]

        if not lines:
            raise RuntimeError("No TTS lines found in file")

        return lines

    def _setup_output_directories(
        self, story_name: str, story_dir: Optional[str] = None
    ) -> tuple[Path, Path, Path]:
        """Setup output directories for story processing.

        Args:
            story_name: Name of the story
            story_dir: Optional custom story directory

        Returns:
            Tuple of (story_output_dir, content_dir, audio_dir)
        """
        if story_dir:
            story_output_dir = Path(story_dir)
        else:
            sanitized_story_name = sanitize_filename(story_name)
            story_output_dir = Path("outputs") / sanitized_story_name
            story_output_dir.mkdir(parents=True, exist_ok=True)

        content_dir = story_output_dir / "content"
        audio_dir = story_output_dir / "audio"
        content_dir.mkdir(exist_ok=True)
        audio_dir.mkdir(exist_ok=True)

        return story_output_dir, content_dir, audio_dir

    def _save_tts_lines(self, lines: List[str], content_dir: Path) -> None:
        """Save TTS lines to content directory.

        Args:
            lines: List of TTS lines to save
            content_dir: Content directory path
        """
        tts_lines_path = content_dir / "tts_lines.txt"
        try:
            with open(tts_lines_path, "w", encoding="utf-8") as f:
                for line in lines:
                    f.write(line + "\n")
            logger.debug(f"Saved TTS lines to: {tts_lines_path}")
        except Exception as e:
            logger.warning(f"Failed to save TTS lines: {e}")

    def _generate_audio_from_text(
        self, text: str, batch_number: int
    ) -> Optional[bytes]:
        """Generate audio from text using TTS service.

        Args:
            text: Text to convert to speech
            batch_number: Batch number for logging

        Returns:
            Audio data bytes or None if generation failed
        """
        # Check if TTS service is available
        if not hasattr(self.tts_service, "generate_speech"):
            logger.error(f"TTS service not available for batch {batch_number}")
            return None

        # Check TTS service health before making call
        if (
            hasattr(self.tts_service, "is_healthy")
            and not self.tts_service.is_healthy()
        ):
            logger.warning(
                f"TTS service appears unhealthy for batch {batch_number}, attempting anyway..."
            )

        # Log the full batch text being processed
        logger.info(f"🎵 Processing batch {batch_number}: {text}")

        # Generate audio for this batch
        logger.info(f"🎵 Starting TTS generation for batch {batch_number}...")
        audio_data = self.tts_service.generate_speech(text)

        if audio_data:
            logger.info(
                f"✅ TTS generation completed for batch {batch_number}: {len(audio_data)} bytes"
            )
        else:
            logger.error(f"❌ TTS generation failed for batch {batch_number}")

        return audio_data

    def _clean_audio_segment(self, audio_data: bytes, batch_number: int) -> bytes:
        """Clean audio segment using Studio Voice service.

        Args:
            audio_data: Raw audio data to clean
            batch_number: Batch number for logging

        Returns:
            Cleaned audio data (fallback to original if cleaning fails)
        """
        logger.debug(f"🧹 Cleaning audio for batch {batch_number}")

        # Check if Studio Voice service is available
        if not hasattr(self.studio_voice_service, "enhance_audio"):
            logger.warning(
                f"Studio Voice service not available for batch {batch_number}, using original audio"
            )
            return audio_data

        cleaned_audio_data = self.studio_voice_service.enhance_audio(audio_data)

        # Fallback to original audio if cleaning fails
        if cleaned_audio_data is None:
            logger.warning(
                f"Audio cleaning failed for batch {batch_number}, using original audio as fallback"
            )
            cleaned_audio_data = audio_data

            # Adjust sample rate to match expected output format
            try:
                if not hasattr(self.studio_voice_service, "convert_sample_rate"):
                    logger.warning(
                        f"Sample rate conversion not available for batch {batch_number}, using original audio"
                    )
                    return audio_data
                else:
                    cleaned_audio_data = self.studio_voice_service.convert_sample_rate(
                        cleaned_audio_data,
                        self.studio_voice_service.sample_rate,
                    )
                    logger.info(
                        f"✅ Sample rate conversion successful for fallback audio in batch {batch_number}"
                    )
            except Exception as e:
                logger.error(
                    f"Sample rate conversion failed for fallback audio in batch {batch_number}: {e}"
                )
                # If even sample rate conversion fails, keep original audio
                cleaned_audio_data = audio_data
                logger.info(
                    f"Using original audio without sample rate conversion for batch {batch_number}"
                )

        return cleaned_audio_data

    def _save_batch_audio(
        self,
        audio_data: bytes,
        audio_dir: Path,
        batch_number: int,
        is_cleaned: bool = False,
    ) -> None:
        """Save batch audio to audio directory.

        Args:
            audio_data: Audio data to save
            audio_dir: Audio directory path
            batch_number: Batch number for filename
            is_cleaned: Whether this is cleaned audio (affects filename)
        """
        if not hasattr(self.audio_processor, "save_audio_data"):
            logger.error(f"Audio processor not available for batch {batch_number}")
            return

        prefix = "cleaned_batch" if is_cleaned else "batch"
        batch_filename = f"{prefix}_{batch_number:03d}.wav"
        batch_path = audio_dir / batch_filename

        try:
            self.audio_processor.save_audio_data(audio_data, batch_path)
            logger.debug(f"Saved {prefix} batch audio: {batch_path}")
        except Exception as e:
            logger.error(
                f"Failed to save {prefix} batch audio for batch {batch_number}: {e}"
            )

    def _combine_audio_files(
        self, all_cleaned_audio_data: List[bytes], story_name: str, audio_dir: Path
    ) -> Path:
        """Combine all cleaned audio files into final output.

        Args:
            all_cleaned_audio_data: List of cleaned audio data
            story_name: Name of the story
            audio_dir: Audio directory path

        Returns:
            Path to final combined audio file

        Raises:
            RuntimeError: If combination fails
        """
        # Sanitize story name for filename
        try:
            sanitized_story_name = sanitize_filename(story_name)
        except Exception as e:
            logger.error(f"Failed to sanitize story name '{story_name}': {e}")
            sanitized_story_name = "story"

        final_audio_path = audio_dir / f"{sanitized_story_name}_final.wav"

        # Check if audio processor is available for combination
        if not hasattr(self.audio_processor, "combine_audio_files"):
            raise RuntimeError(
                "Audio processor not available for combining audio files"
            )

        try:
            self.audio_processor.combine_audio_files(
                all_cleaned_audio_data, final_audio_path
            )
            logger.debug(f"Successfully combined audio files into: {final_audio_path}")
        except Exception as e:
            logger.error(f"Failed to combine audio files: {e}")
            raise RuntimeError(f"Audio combination failed: {e}")

        return final_audio_path

    def _verify_final_audio(self, final_audio_path: Path) -> None:
        """Verify the final audio file was created successfully.

        Args:
            final_audio_path: Path to final audio file

        Raises:
            RuntimeError: If verification fails
        """
        if not final_audio_path.exists():
            raise RuntimeError(f"Final audio file was not created: {final_audio_path}")

        if final_audio_path.stat().st_size == 0:
            raise RuntimeError(f"Final audio file is empty: {final_audio_path}")

        logger.info(f"🎵 Final audio file created successfully: {final_audio_path}")

    def _log_processing_summary(
        self, all_audio_data: List[bytes], all_cleaned_audio_data: List[bytes]
    ) -> None:
        """Log summary of audio processing.

        Args:
            all_audio_data: List of all raw audio data
            all_cleaned_audio_data: List of all cleaned audio data
        """
        total_batches = len(all_cleaned_audio_data)
        try:
            fallback_batches = sum(
                1 for audio in all_cleaned_audio_data if audio in all_audio_data
            )
            if fallback_batches > 0:
                logger.info(
                    f"📊 Audio processing summary: {total_batches} total batches, {fallback_batches} used fallback audio"
                )
            else:
                logger.info(
                    f"📊 Audio processing summary: {total_batches} total batches, all successfully cleaned"
                )
        except Exception as e:
            logger.warning(f"Could not calculate fallback summary: {e}")
            logger.info(
                f"📊 Audio processing summary: {total_batches} total batches processed"
            )

    def process_tts_lines(
        self,
        tts_lines_file: str,
        story_name: str,
        batch_size: int = 2,
        story_dir: Optional[str] = None,
    ) -> Path:
        """Process TTS lines and generate audio.

        Args:
            tts_lines_file: Path to TTS lines file
            story_name: Name of the story
            batch_size: Number of lines to process per batch
            story_dir: Optional custom story directory

        Returns:
            Path to final combined audio file
        """
        try:
            # Clean and validate input
            lines = self._clean_and_validate_input(tts_lines_file)
            logger.info(f"Processing {len(lines)} TTS lines for story: {story_name}")

            # Setup output directories
            story_output_dir, content_dir, audio_dir = self._setup_output_directories(
                story_name, story_dir
            )

            # Save TTS lines to content directory
            self._save_tts_lines(lines, content_dir)

            all_audio_data = []
            all_cleaned_audio_data = []

            # Process lines in batches
            for i in range(0, len(lines), batch_size):
                batch_lines = lines[i : i + batch_size]
                batch_text = " ".join(batch_lines)
                batch_number = i // batch_size + 1

                logger.info(
                    f"Processing batch {batch_number}: {len(batch_lines)} lines"
                )

                # Skip empty batches
                if not batch_lines or not batch_text.strip():
                    logger.warning(f"Skipping empty batch {batch_number}")
                    continue

                try:
                    # Generate audio from text
                    audio_data = self._generate_audio_from_text(
                        batch_text, batch_number
                    )
                    if not audio_data:
                        logger.warning(f"No audio generated for batch {batch_number}")
                        continue

                    all_audio_data.append(audio_data)

                    # Save raw batch audio
                    self._save_batch_audio(
                        audio_data, audio_dir, batch_number, is_cleaned=False
                    )

                    # Clean audio segment
                    cleaned_audio_data = self._clean_audio_segment(
                        audio_data, batch_number
                    )
                    all_cleaned_audio_data.append(cleaned_audio_data)

                    # Save cleaned batch audio
                    self._save_batch_audio(
                        cleaned_audio_data, audio_dir, batch_number, is_cleaned=True
                    )

                    # Log completion status
                    if cleaned_audio_data == audio_data:
                        logger.info(
                            f"✅ Batch {batch_number} completed: TTS + cleaning (using fallback audio)"
                        )
                    else:
                        logger.info(
                            f"✅ Batch {batch_number} completed: TTS + cleaning"
                        )

                except Exception as e:
                    logger.error(
                        f"Failed to generate audio for batch {batch_number}: {e}"
                    )
                    logger.debug(
                        f"Batch {batch_number} details: lines {i} to {min(i + batch_size, len(lines))}"
                    )
                    continue

            if not all_cleaned_audio_data:
                raise RuntimeError("No audio was generated and cleaned successfully")

            # Log processing summary
            self._log_processing_summary(all_audio_data, all_cleaned_audio_data)

            # Combine all cleaned audio files
            final_audio_path = self._combine_audio_files(
                all_cleaned_audio_data, story_name, audio_dir
            )

            # Verify final audio file
            self._verify_final_audio(final_audio_path)

            return final_audio_path

        except Exception as e:
            logger.error(f"Failed to process TTS lines: {e}")
            logger.error(
                f"Story: {story_name}, Lines: {len(lines) if 'lines' in locals() else 'unknown'}"
            )
            raise RuntimeError(f"TTS processing failed: {e}")

    def get_story_name_from_filename(self, filename: str) -> str:
        """Extract story name from filename.

        Args:
            filename: TTS lines filename

        Returns:
            Extracted story name
        """
        # Remove common prefixes and suffixes
        name = filename.replace("tts_lines_", "").replace(".txt", "")
        # Convert to title case and replace underscores with spaces
        name = name.replace("_", " ").title()
        return name
