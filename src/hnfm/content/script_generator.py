"""Script generation and audio processing for hn.fm."""

import os
from pathlib import Path
from typing import List, Optional
import logging

from ..audio.tts_service import TTSService
from ..audio.audio_processor import AudioProcessor
from ..audio.studio_voice_service import StudioVoiceService
from ..utils.config import config_manager

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
                story_output_dir = Path("outputs") / story_name
                story_output_dir.mkdir(parents=True, exist_ok=True)

            # Create content and audio subdirectories
            content_dir = story_output_dir / "content"
            audio_dir = story_output_dir / "audio"
            content_dir.mkdir(exist_ok=True)
            audio_dir.mkdir(exist_ok=True)

            # Save TTS lines to content directory
            tts_lines_path = content_dir / "tts_lines.txt"
            with open(tts_lines_path, "w", encoding="utf-8") as f:
                for line in lines:
                    f.write(line + "\n")

            all_audio_data = []
            all_cleaned_audio_data = []

            for i in range(0, len(lines), batch_size):
                batch_lines = lines[i : i + batch_size]
                batch_text = " ".join(batch_lines)

                logger.info(
                    f"Processing batch {i//batch_size + 1}: {len(batch_lines)} lines"
                )

                try:
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
                    self.audio_processor.save_audio_data(audio_data, batch_path)

                    # Clean audio using Studio Voice
                    logger.info(f"🧹 Cleaning audio for batch {i//batch_size + 1}")
                    cleaned_audio_data = self.studio_voice_service.enhance_audio(
                        audio_data
                    )
                    all_cleaned_audio_data.append(cleaned_audio_data)

                    # Save cleaned batch audio to audio directory
                    cleaned_batch_filename = (
                        f"cleaned_batch_{i//batch_size + 1:03d}.wav"
                    )
                    cleaned_batch_path = audio_dir / cleaned_batch_filename
                    self.audio_processor.save_audio_data(
                        cleaned_audio_data, cleaned_batch_path
                    )

                    logger.info(
                        f"✅ Batch {i//batch_size + 1} completed: TTS + cleaning"
                    )

                except Exception as e:
                    logger.error(
                        f"Failed to generate audio for batch {i//batch_size + 1}: {e}"
                    )
                    continue

            if not all_cleaned_audio_data:
                raise RuntimeError("No audio was generated and cleaned successfully")

            # Combine all cleaned audio files
            final_audio_path = audio_dir / f"{story_name}_final.wav"
            self.audio_processor.combine_audio_files(
                all_cleaned_audio_data, final_audio_path
            )

            logger.info(f"Successfully generated final audio: {final_audio_path}")
            return final_audio_path

        except Exception as e:
            logger.error(f"Failed to process TTS lines: {e}")
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
