"""Script generation and audio processing for hn.fm."""

import os
from pathlib import Path
from typing import List, Optional
import logging

from ..audio.tts_service import TTSService
from ..audio.audio_processor import AudioProcessor
from ..audio.studio_voice_service import StudioVoiceService
from ..utils.config import config_manager
from ..utils.filename_utils import sanitize_filename

logger = logging.getLogger(__name__)


class ScriptGenerator:
    """Generates audio from script lines."""

    def __init__(self, output_dir: str = "outputs"):
        """Initialize the script generator.

        Args:
            output_dir: Base output directory
        """
        self.output_dir = Path(output_dir)
        self.tts_service = TTSService()
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

        Returns:
            Path to final combined audio file
        """
        try:
            # Read TTS lines
            with open(tts_lines_file, "r", encoding="utf-8") as f:
                lines = [line.strip() for line in f.readlines() if line.strip()]

            if not lines:
                raise RuntimeError("No TTS lines found in file")

            logger.info(f"Processing {len(lines)} TTS lines for story: {story_name}")

            # Use provided story directory or create default one
            if story_dir:
                story_output_dir = Path(story_dir)
            else:
                sanitized_story_name = sanitize_filename(story_name)
                story_output_dir = Path("outputs") / sanitized_story_name
                story_output_dir.mkdir(parents=True, exist_ok=True)

            # Create content and audio subdirectories
            content_dir = story_output_dir / "content"
            audio_dir = story_output_dir / "audio"
            content_dir.mkdir(exist_ok=True)
            audio_dir.mkdir(exist_ok=True)

            # Save TTS lines to content directory
            tts_lines_path = content_dir / "tts_lines.txt"
            try:
                with open(tts_lines_path, "w", encoding="utf-8") as f:
                    for line in lines:
                        f.write(line + "\n")
                logger.debug(f"Saved TTS lines to: {tts_lines_path}")
            except Exception as e:
                logger.warning(f"Failed to save TTS lines: {e}")
                # Continue without saving TTS lines

            all_audio_data = []
            all_cleaned_audio_data = []

            for i in range(0, len(lines), batch_size):
                batch_lines = lines[i : i + batch_size]
                batch_text = " ".join(batch_lines)

                logger.info(
                    f"Processing batch {i//batch_size + 1}: {len(batch_lines)} lines"
                )

                # Skip empty batches
                if not batch_lines or not batch_text.strip():
                    logger.warning(f"Skipping empty batch {i//batch_size + 1}")
                    continue

                try:
                    # Check if TTS service is available
                    if not hasattr(self.tts_service, 'generate_speech'):
                        logger.error(f"TTS service not available for batch {i//batch_size + 1}")
                        continue

                    # Generate audio for this batch
                    audio_data = self.tts_service.generate_speech(batch_text)

                    if not audio_data:
                        logger.warning(
                            f"No audio generated for batch {i//batch_size + 1}"
                        )
                        continue

                    all_audio_data.append(audio_data)

                    # Save raw batch audio to audio directory
                    batch_filename = f"batch_{i//batch_size + 1:03d}.wav"
                    batch_path = audio_dir / batch_filename

                    # Check if audio processor is available
                    if not hasattr(self.audio_processor, 'save_audio_data'):
                        logger.error(f"Audio processor not available for batch {i//batch_size + 1}")
                        continue

                    try:
                        self.audio_processor.save_audio_data(audio_data, batch_path)
                        logger.debug(f"Saved raw batch audio: {batch_path}")
                    except Exception as e:
                        logger.error(f"Failed to save raw batch audio for batch {i//batch_size + 1}: {e}")
                        # Continue without saving raw batch audio

                    # Clean audio using Studio Voice
                    logger.debug(f"🧹 Cleaning audio for batch {i//batch_size + 1}")

                    # Check if Studio Voice service is available
                    if not hasattr(self.studio_voice_service, 'enhance_audio'):
                        logger.warning(f"Studio Voice service not available for batch {i//batch_size + 1}, using original audio")
                        cleaned_audio_data = None
                    else:
                        cleaned_audio_data = self.studio_voice_service.enhance_audio(
                            audio_data
                        )

                    # Fallback to original audio if cleaning fails
                    if cleaned_audio_data is None:
                        logger.warning(f"Audio cleaning failed for batch {i//batch_size + 1}, using original audio as fallback")
                        cleaned_audio_data = audio_data
                        # Adjust sample rate to match expected output format
                        try:
                            if not hasattr(self.studio_voice_service, 'convert_sample_rate'):
                                logger.warning(f"Sample rate conversion not available for batch {i//batch_size + 1}, using original audio")
                                cleaned_audio_data = audio_data
                            else:
                                cleaned_audio_data = self.studio_voice_service.convert_sample_rate(
                                    cleaned_audio_data,
                                    self.studio_voice_service.sample_rate
                                )
                                logger.info(f"✅ Sample rate conversion successful for fallback audio in batch {i//batch_size + 1}")
                        except Exception as e:
                            logger.error(f"Sample rate conversion failed for fallback audio in batch {i//batch_size + 1}: {e}")
                            # If even sample rate conversion fails, keep original audio
                            cleaned_audio_data = audio_data
                            logger.info(f"Using original audio without sample rate conversion for batch {i//batch_size + 1}")

                    # Ensure we have valid audio data before proceeding
                    if cleaned_audio_data is None:
                        logger.error(f"No valid audio data available for batch {i//batch_size + 1}, skipping")
                        continue

                    all_cleaned_audio_data.append(cleaned_audio_data)

                    # Save cleaned batch audio to audio directory
                    cleaned_batch_filename = (
                        f"cleaned_batch_{i//batch_size + 1:03d}.wav"
                    )
                    cleaned_batch_path = audio_dir / cleaned_batch_filename

                    try:
                        self.audio_processor.save_audio_data(
                            cleaned_audio_data, cleaned_batch_path
                        )
                        logger.debug(f"Saved cleaned batch audio: {cleaned_batch_path}")
                    except Exception as e:
                        logger.error(f"Failed to save cleaned batch audio for batch {i//batch_size + 1}: {e}")
                        # Continue without saving cleaned batch audio

                    if cleaned_audio_data == audio_data:
                        logger.info(
                            f"✅ Batch {i//batch_size + 1} completed: TTS + cleaning (using fallback audio)"
                        )
                    else:
                        logger.info(
                            f"✅ Batch {i//batch_size + 1} completed: TTS + cleaning"
                        )

                except Exception as e:
                    logger.error(
                        f"Failed to generate audio for batch {i//batch_size + 1}: {e}"
                    )
                    logger.debug(f"Batch {i//batch_size + 1} details: lines {i} to {min(i + batch_size, len(tts_lines))}")
                    continue

            if not all_cleaned_audio_data:
                raise RuntimeError("No audio was generated and cleaned successfully")

            # Log summary of processing
            total_batches = len(all_cleaned_audio_data)
            try:
                fallback_batches = sum(1 for audio in all_cleaned_audio_data if audio in all_audio_data)
                if fallback_batches > 0:
                    logger.info(f"📊 Audio processing summary: {total_batches} total batches, {fallback_batches} used fallback audio")
                else:
                    logger.info(f"📊 Audio processing summary: {total_batches} total batches, all successfully cleaned")
            except Exception as e:
                logger.warning(f"Could not calculate fallback summary: {e}")
                logger.info(f"📊 Audio processing summary: {total_batches} total batches processed")

            # Combine all cleaned audio files
            try:
                sanitized_story_name = sanitize_filename(story_name)
            except Exception as e:
                logger.error(f"Failed to sanitize story name '{story_name}': {e}")
                # Use a fallback name
                sanitized_story_name = "story"

            final_audio_path = audio_dir / f"{sanitized_story_name}_final.wav"

            # Check if audio processor is available for combination
            if not hasattr(self.audio_processor, 'combine_audio_files'):
                raise RuntimeError("Audio processor not available for combining audio files")

            try:
                self.audio_processor.combine_audio_files(
                    all_cleaned_audio_data, final_audio_path
                )
                logger.debug(f"Successfully combined audio files into: {final_audio_path}")
            except Exception as e:
                logger.error(f"Failed to combine audio files: {e}")
                raise RuntimeError(f"Audio combination failed: {e}")

            logger.debug(f"Successfully generated final audio: {final_audio_path}")

                        # Verify the final audio file was created
            try:
                if not final_audio_path.exists():
                    raise RuntimeError(f"Final audio file was not created: {final_audio_path}")

                if final_audio_path.stat().st_size == 0:
                    raise RuntimeError(f"Final audio file is empty: {final_audio_path}")

                logger.info(f"🎵 Final audio file created successfully: {final_audio_path}")
                return final_audio_path
            except Exception as e:
                logger.error(f"Final audio file verification failed: {e}")
                raise RuntimeError(f"Final audio file verification failed: {e}")

        except Exception as e:
            logger.error(f"Failed to process TTS lines: {e}")
            logger.error(f"Story: {story_name}, Lines: {len(lines) if 'lines' in locals() else 'unknown'}")
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

    def generate_script_from_content(self, title: str, paragraphs: List[str]) -> dict:
        """Generate a podcast script from content paragraphs.

        Args:
            title: Article title
            paragraphs: List of content paragraphs

        Returns:
            Dictionary with script, tts_lines, and metadata
        """
        try:
            from ..content.llm_service import LLMService

            logger.info(f"📝 Generating podcast script for: {title}")

            # Get LLM configuration from config
            llm_config = config_manager.get("llm", {})

            # Initialize LLM service with configuration
            if llm_config.get("enabled", False):
                base_url = llm_config.get("base_url")
                model = llm_config.get("model", "gpt-oss")
                logger.info(f"Using local LLM: {base_url} with model: {model}")
                llm_service = LLMService(base_url=base_url, model=model)
            else:
                logger.info("Using OpenAI LLM (fallback)")
                llm_service = LLMService()

            # Prepare content for script generation
            content_text = "\n\n".join(paragraphs)

            # Generate script using LLM
            script_prompt = f"""
            Create a natural, engaging podcast script from this article.

            Article Title: {title}

            Content:
            {content_text}

            Requirements:
            - Use [S1] and [S2] speaker tags for dialogue (NOT **S1:** format)
            - Make it conversational and engaging
            - Break into natural speaking segments (2-3 sentences max per line)
            - Maintain the key insights and information
            - Keep total length reasonable for a podcast segment (3-5 minutes)
            - Use straight quotes (") and apostrophes (') instead of curly quotes (") and apostrophes (')
            - Avoid special characters that might cause TTS issues
            - Each line should start with [S1] or [S2] followed by the dialogue

            Format the output as a script with [S1] and [S2] tags, one per line.
            Example:
            [S1] Hey there, welcome to the podcast!
            [S2] Today we're talking about an interesting topic.
            [S1] Let's dive right in.
            """

            script = llm_service.generate_content(script_prompt)

            if not script:
                logger.error("🚨 CRITICAL: LLM returned None - this should not happen!")
                print(f"   🚨 CRITICAL: LLM returned None - using emergency fallback")
                raise RuntimeError("Failed to generate script from LLM")

            # Check if this is the fallback script
            if script == "[S1] This is a fallback, error generating script":
                logger.warning("⚠️  WARNING: Using emergency fallback script due to LLM failure")
                print(f"   ⚠️  WARNING: LLM failed, using emergency fallback script")
                print(f"   📝 Fallback script: {script}")
            else:
                logger.info(f"✅ Script generated successfully by LLM")
                print(f"   ✅ Script generated successfully by LLM")

            # Split script into TTS lines
            tts_lines = []
            for line in script.split("\n"):
                line = line.strip()
                if line and (line.startswith("[S1]") or line.startswith("[S2]")):
                    tts_lines.append(line)

            if not tts_lines:
                # Fallback: create simple lines from paragraphs
                logger.warning("⚠️  WARNING: No valid TTS lines found in script, creating fallback lines")
                print(f"   ⚠️  WARNING: No valid TTS lines found, creating fallback lines")
                tts_lines = []
                for i, para in enumerate(
                    paragraphs[:10]
                ):  # Limit to first 10 paragraphs
                    speaker = "[S1]" if i % 2 == 0 else "[S2]"
                    # Truncate long paragraphs
                    if len(para) > 200:
                        para = para[:200] + "..."
                    tts_lines.append(f"{speaker} {para}")

            logger.info(f"📝 Script length: {len(script)} characters")
            logger.info(f"🎙️ TTS lines: {len(tts_lines)}")
            print(f"   📝 Script length: {len(script)} characters")
            print(f"   🎙️ TTS lines: {len(tts_lines)}")

            return {
                "script": script,
                "tts_lines": tts_lines,
                "meta": {
                    "title": title,
                    "paragraph_count": len(paragraphs),
                    "script_length": len(script),
                    "tts_line_count": len(tts_lines),
                },
            }

        except Exception as e:
            logger.error(f"Failed to generate script: {e}")
            # Fallback: create simple script from paragraphs
            tts_lines = []
            for i, para in enumerate(paragraphs[:8]):  # Limit to first 8 paragraphs
                speaker = "[S1]" if i % 2 == 0 else "[S2]"
                if len(para) > 150:
                    para = para[:150] + "..."
                tts_lines.append(f"{speaker} {para}")

            return {
                "script": "\n".join(tts_lines),
                "tts_lines": tts_lines,
                "meta": {
                    "title": title,
                    "paragraph_count": len(paragraphs),
                    "script_length": len("\n".join(tts_lines)),
                    "tts_line_count": len(tts_lines),
                    "fallback": True,
                },
            }
