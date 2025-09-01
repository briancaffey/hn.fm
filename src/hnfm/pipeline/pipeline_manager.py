"""Simple pipeline manager for hn.fm"""

import os
import json
import hashlib
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
import logging
from dataclasses import dataclass

from hnfm.utils.config import config_manager
from hnfm.utils.logger import setup_logging
from hnfm.utils.filename_utils import sanitize_filename
from hnfm.scraper.hn_scraper import HNScraper
from hnfm.scraper.content_scraper import ContentScraper
from hnfm.content.content_processor import ContentProcessor
from hnfm.content.script_generator import ScriptGenerator
from hnfm.audio.tts_service import TTSService
from hnfm.audio.studio_voice_service import StudioVoiceService
from hnfm.audio.audio_processor import AudioProcessor
from hnfm.audio.asr_service import ASRService
from hnfm.video.video_generator import VideoGenerator
from hnfm.video.image_generator import ImageGenerationService

# Setup logging based on config
log_level = config_manager.get("development.log_level", "INFO")
setup_logging(level=log_level)

logger = logging.getLogger(__name__)


@dataclass
class PipelineStep:
    """Simple pipeline step"""

    name: str
    description: str
    dependencies: List[str]
    cache_key: str
    output_files: List[str]
    completed: bool = False
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    error: Optional[str] = None
    artifacts: Dict[str, str] = None
    metadata: Dict[str, Any] = None


@dataclass
class PipelineState:
    """Simple pipeline state"""

    story_id: str
    story_title: str
    current_step: str
    steps: Dict[str, PipelineStep]
    metadata: Dict[str, Any]
    created_at: datetime
    updated_at: datetime


class PipelineManager:
    """Simple pipeline manager for hn.fm"""

    def __init__(
        self,
        cache_dir: Optional[str] = None,
        text_only: bool = False,
    ):
        """Initialize pipeline manager.

        Args:
            cache_dir: Cache directory path
            text_only: If True, only generate text content (no TTS, images, or video)
        """
        self.cache_dir = Path(
            cache_dir or config_manager.get("pipeline.cache.directory", "cache")
        )
        self.cache_dir.mkdir(exist_ok=True)

        self.text_only = text_only

        # Initialize services lazily to avoid dependency issues
        self._services = {}

        # Pipeline steps definition
        self.pipeline_steps = self._define_pipeline_steps()

        if text_only:
            logger.info(
                "Running in text-only mode - TTS, image, and video generation will be skipped"
            )

    def _define_pipeline_steps(self) -> Dict[str, PipelineStep]:
        """Define the pipeline steps."""
        base_steps = {
            "system_check": PipelineStep(
                name="system_check",
                description="Check all required services are running",
                dependencies=[],
                cache_key="system_status",
                output_files=["system_status.json"],
            ),
            "hn_scraping": PipelineStep(
                name="hn_scraping",
                description="Scrape Hacker News articles",
                dependencies=["system_check"],
                cache_key="hn_articles",
                output_files=["hn_articles.json"],
            ),
            "firecrawl_content": PipelineStep(
                name="firecrawl_content",
                description="Extract content using Firecrawl",
                dependencies=["hn_scraping"],
                cache_key="firecrawl_content",
                output_files=["raw_content.md", "processed_content.json"],
            ),
            "content_processing": PipelineStep(
                name="content_processing",
                description="Process and clean content",
                dependencies=["firecrawl_content"],
                cache_key="processed_content",
                output_files=["cleaned_content.md", "meaningful_paragraphs.json"],
            ),
            "script_generation": PipelineStep(
                name="script_generation",
                description="Generate podcast script with [S1]/[S2] tags",
                dependencies=["content_processing"],
                cache_key="script",
                output_files=["script.md", "script_metadata.json"],
            ),
            "tts_generation": PipelineStep(
                name="tts_generation",
                description="Generate TTS audio in batches",
                dependencies=["script_generation"],
                cache_key="tts_audio",
                output_files=["tts_lines_*.txt", "audio_*.wav"],
            ),
            "audio_cleaning": PipelineStep(
                name="audio_cleaning",
                description="Clean audio using Studio Voice",
                dependencies=["tts_generation"],
                cache_key="cleaned_audio",
                output_files=["cleaned_audio_*.wav"],
            ),
            "audio_assembly": PipelineStep(
                name="audio_assembly",
                description="Combine all audio into final file",
                dependencies=["audio_cleaning"],
                cache_key="final_audio",
                output_files=["final_audio.wav", "final_audio.mp3"],
            ),
            "image_generation": PipelineStep(
                name="image_generation",
                description="Generate images for video",
                dependencies=["script_generation"],
                cache_key="images",
                output_files=["image_*.png", "image_*.jpg"],
            ),
            "video_generation": PipelineStep(
                name="video_generation",
                description="Create final video with audio and images",
                dependencies=["audio_assembly", "image_generation"],
                cache_key="video",
                output_files=["final_video.mp4"],
            ),
        }

        # Filter steps based on text_only mode
        if self.text_only:
            text_only_steps = {
                k: v
                for k, v in base_steps.items()
                if k
                in [
                    "system_check",
                    "hn_scraping",
                    "firecrawl_content",
                    "content_processing",
                    "script_generation",
                ]
            }
            return text_only_steps

        return base_steps

    def _get_service(self, service_name: str):
        """Get a service instance, creating it if needed."""
        if service_name not in self._services:
            if service_name == "hn_scraper":
                self._services[service_name] = HNScraper()
            elif service_name == "content_scraper":
                self._services[service_name] = ContentScraper()
            elif service_name == "content_processor":
                self._services[service_name] = ContentProcessor()
            elif service_name == "script_generator":
                self._services[service_name] = ScriptGenerator()
            elif service_name == "tts_service":
                self._services[service_name] = TTSService()
            elif service_name == "studio_voice_service":
                self._services[service_name] = StudioVoiceService()
            elif service_name == "audio_processor":
                self._services[service_name] = AudioProcessor()
            elif service_name == "asr_service":
                self._services[service_name] = ASRService()
            elif service_name == "image_generator":
                self._services[service_name] = ImageGenerationService()
            elif service_name == "video_generator":
                self._services[service_name] = VideoGenerator()
            else:
                raise ValueError(f"Unknown service: {service_name}")

        return self._services[service_name]

    def execute_step(
        self,
        step_name: str,
        manifest_data: Dict[str, Any],
        segment_data: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        """Execute a pipeline step."""
        logger.info(f"Executing pipeline step: {step_name}")
        logger.debug(f"Manifest data: {manifest_data}")
        if segment_data:
            logger.debug(f"Segment data: {segment_data}")

        # Execute the step using pipeline logic
        if step_name == "system_check":
            return self._execute_system_check(manifest_data)
        elif step_name == "hn_scraping":
            return self._execute_hn_scraping(manifest_data)
        elif step_name == "firecrawl_content":
            return self._execute_firecrawl_content(manifest_data)
        elif step_name == "content_processing":
            return self._execute_content_processing(manifest_data)
        elif step_name == "script_generation":
            return self._execute_script_generation(manifest_data)
        elif step_name == "tts_generation":
            return self._execute_tts_generation(manifest_data)
        elif step_name == "audio_cleaning":
            return self._execute_audio_cleaning(manifest_data)
        elif step_name == "audio_assembly":
            return self._execute_audio_assembly(manifest_data)
        elif step_name == "image_generation":
            return self._execute_image_generation(manifest_data)
        elif step_name == "video_generation":
            return self._execute_video_generation(manifest_data)
        elif step_name == "asr_processing":
            return self._execute_asr_processing(manifest_data)
        else:
            raise ValueError(f"Unknown pipeline step: {step_name}")

    def _execute_system_check(self, manifest_data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute system check step."""
        logger.info("Executing system check")

        # Check if required services are available
        services_status = {}

        try:
            # Check TTS service
            tts_service = self._get_service("tts_service")
            services_status["tts"] = "available"
        except Exception as e:
            services_status["tts"] = f"error: {e}"

        try:
            # Check image generation service
            image_service = self._get_service("image_generator")
            services_status["image_generation"] = "available"
        except Exception as e:
            services_status["image_generation"] = f"error: {e}"

        try:
            # Check video generation service
            video_service = self._get_service("video_generator")
            services_status["video_generation"] = "available"
        except Exception as e:
            services_status["video_generation"] = f"error: {e}"

        # Save system status
        system_status_file = self.cache_dir / "system_status.json"
        with open(system_status_file, "w") as f:
            json.dump(services_status, f, indent=2)

        return {
            "artifacts": {"system_status.json": str(system_status_file)},
            "metadata": {"services_status": services_status},
        }

    def _execute_hn_scraping(self, manifest_data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute HN scraping step."""
        logger.info("Executing HN scraping")

        hn_scraper = self._get_service("hn_scraper")
        articles = hn_scraper.get_top_stories(limit=30)

        # Save articles
        articles_file = self.cache_dir / "hn_articles.json"
        with open(articles_file, "w") as f:
            json.dump(articles, f, indent=2)

        return {
            "artifacts": {"hn_articles.json": str(articles_file)},
            "metadata": {"articles_count": len(articles)},
        }

    def _execute_firecrawl_content(
        self, manifest_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute Firecrawl content extraction step."""
        logger.info("Executing Firecrawl content extraction")

        # Get the selected article from manifest data
        selected_article = manifest_data.get("selected_article", {})
        url = selected_article.get("url")
        title = selected_article.get("title", "Unknown Title")

        if not url:
            raise ValueError("No URL provided for content extraction")

        content_scraper = self._get_service("content_scraper")
        raw_content_data = content_scraper.extract_content(url)
        raw_content = raw_content_data.get("content", "")
        title = raw_content_data.get("title", "Unknown Title")

        # Save raw content
        raw_content_file = self.cache_dir / "raw_content.md"
        with open(raw_content_file, "w", encoding="utf-8") as f:
            f.write(raw_content)

        # Save processed content
        processed_content = {
            "url": url,
            "title": title,
            "raw_content": raw_content,
            "extracted_at": datetime.now().isoformat(),
        }
        processed_content_file = self.cache_dir / "processed_content.json"
        with open(processed_content_file, "w") as f:
            json.dump(processed_content, f, indent=2)

        return {
            "artifacts": {
                "raw_content.md": str(raw_content_file),
                "processed_content.json": str(processed_content_file),
            },
            "metadata": {
                "url": url,
                "title": title,
                "content_length": len(raw_content),
            },
        }

    def _execute_content_processing(
        self, manifest_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute content processing step."""
        logger.info("Executing content processing")

        # Get raw content from previous step
        raw_content_file = self.cache_dir / "raw_content.md"
        if not raw_content_file.exists():
            raise FileNotFoundError("Raw content file not found")

        with open(raw_content_file, "r", encoding="utf-8") as f:
            raw_content = f.read()

        # Get title from processed content file
        processed_content_file = self.cache_dir / "processed_content.json"
        if processed_content_file.exists():
            with open(processed_content_file, "r") as f:
                processed_data = json.load(f)
                title = processed_data.get("title", "Unknown Title")
        else:
            title = "Unknown Title"

        content_processor = self._get_service("content_processor")
        processed_content_obj = content_processor.process_content(title, raw_content)
        cleaned_content = processed_content_obj.cleaned_content

        # Save cleaned content
        cleaned_content_file = self.cache_dir / "cleaned_content.md"
        with open(cleaned_content_file, "w", encoding="utf-8") as f:
            f.write(cleaned_content)

        # Extract meaningful paragraphs
        meaningful_paragraphs = processed_content_obj.meaningful_paragraphs
        paragraphs_file = self.cache_dir / "meaningful_paragraphs.json"
        with open(paragraphs_file, "w") as f:
            json.dump(meaningful_paragraphs, f, indent=2)

        return {
            "artifacts": {
                "cleaned_content.md": str(cleaned_content_file),
                "meaningful_paragraphs.json": str(paragraphs_file),
            },
            "metadata": {
                "cleaned_content_length": len(cleaned_content),
                "paragraphs_count": len(meaningful_paragraphs),
            },
        }

    def _execute_script_generation(
        self, manifest_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute script generation step."""
        logger.info("Executing script generation")

        # Get cleaned content from previous step
        cleaned_content_file = self.cache_dir / "cleaned_content.md"
        if not cleaned_content_file.exists():
            raise FileNotFoundError("Cleaned content file not found")

        with open(cleaned_content_file, "r", encoding="utf-8") as f:
            cleaned_content = f.read()

        script_generator = self._get_service("script_generator")

        # Get meaningful paragraphs from previous step
        meaningful_paragraphs_file = self.cache_dir / "meaningful_paragraphs.json"
        if meaningful_paragraphs_file.exists():
            with open(meaningful_paragraphs_file, "r") as f:
                meaningful_paragraphs = json.load(f)
        else:
            meaningful_paragraphs = [cleaned_content]

        # Get title from processed content
        processed_content_file = self.cache_dir / "processed_content.json"
        if processed_content_file.exists():
            with open(processed_content_file, "r") as f:
                processed_data = json.load(f)
                title = processed_data.get("title", "Unknown Title")
        else:
            title = "Unknown Title"

        script_result = script_generator.generate_script_from_content(
            title, meaningful_paragraphs
        )
        script_content = script_result.get("script", "")

        # Save script
        script_file = self.cache_dir / "script.md"
        with open(script_file, "w", encoding="utf-8") as f:
            f.write(script_content)

        # Save script metadata
        script_metadata = {
            "generated_at": datetime.now().isoformat(),
            "script_length": len(script_content),
            "lines_count": len(script_content.split("\n")),
        }
        script_metadata_file = self.cache_dir / "script_metadata.json"
        with open(script_metadata_file, "w") as f:
            json.dump(script_metadata, f, indent=2)

        return {
            "artifacts": {
                "script.md": str(script_file),
                "script_metadata.json": str(script_metadata_file),
            },
            "metadata": {
                "script_length": len(script_content),
                "lines_count": len(script_content.split("\n")),
            },
        }

    def _execute_tts_generation(self, manifest_data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute TTS generation step."""
        if self.text_only:
            logger.info("Skipping TTS generation in text-only mode")
            return {"artifacts": {}, "metadata": {"skipped": True}}

        logger.info("Executing TTS generation")

        # Get script from previous step
        script_file = self.cache_dir / "script.md"
        if not script_file.exists():
            raise FileNotFoundError("Script file not found")

        with open(script_file, "r", encoding="utf-8") as f:
            script_content = f.read()

        tts_service = self._get_service("tts_service")

        # Split script into lines and generate TTS for each
        lines = script_content.split("\n")
        audio_files = []
        tts_lines = []

        for i, line in enumerate(lines):
            if line.strip():
                audio_file = self.cache_dir / f"audio_{i:03d}.wav"
                tts_service.generate_audio(line, str(audio_file))
                audio_files.append(str(audio_file))
                tts_lines.append(
                    {"line_number": i, "text": line, "audio_file": str(audio_file)}
                )

        # Save TTS lines info
        tts_lines_file = self.cache_dir / "tts_lines.json"
        with open(tts_lines_file, "w") as f:
            json.dump(tts_lines, f, indent=2)

        return {
            "artifacts": {
                "tts_lines.json": str(tts_lines_file),
                **{
                    f"audio_{i:03d}.wav": audio_files[i]
                    for i in range(len(audio_files))
                },
            },
            "metadata": {
                "audio_files_count": len(audio_files),
                "lines_processed": len(tts_lines),
            },
        }

    def _execute_audio_cleaning(self, manifest_data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute audio cleaning step."""
        if self.text_only:
            logger.info("Skipping audio cleaning in text-only mode")
            return {"artifacts": {}, "metadata": {"skipped": True}}

        logger.info("Executing audio cleaning")

        # Get TTS lines info
        tts_lines_file = self.cache_dir / "tts_lines.json"
        if not tts_lines_file.exists():
            raise FileNotFoundError("TTS lines file not found")

        with open(tts_lines_file, "r") as f:
            tts_lines = json.load(f)

        studio_voice_service = self._get_service("studio_voice_service")

        cleaned_audio_files = []
        for line_info in tts_lines:
            input_audio = line_info["audio_file"]
            output_audio = (
                self.cache_dir / f"cleaned_audio_{line_info['line_number']:03d}.wav"
            )
            studio_voice_service.clean_audio(input_audio, str(output_audio))
            cleaned_audio_files.append(str(output_audio))

        return {
            "artifacts": {
                **{
                    f"cleaned_audio_{i:03d}.wav": cleaned_audio_files[i]
                    for i in range(len(cleaned_audio_files))
                },
            },
            "metadata": {
                "cleaned_audio_files_count": len(cleaned_audio_files),
            },
        }

    def _execute_audio_assembly(self, manifest_data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute audio assembly step."""
        if self.text_only:
            logger.info("Skipping audio assembly in text-only mode")
            return {"artifacts": {}, "metadata": {"skipped": True}}

        logger.info("Executing audio assembly")

        # Get cleaned audio files
        cleaned_audio_files = list(self.cache_dir.glob("cleaned_audio_*.wav"))
        cleaned_audio_files.sort()

        if not cleaned_audio_files:
            raise FileNotFoundError("No cleaned audio files found")

        audio_processor = self._get_service("audio_processor")

        # Combine all audio files
        final_audio_wav = self.cache_dir / "final_audio.wav"
        final_audio_mp3 = self.cache_dir / "final_audio.mp3"

        audio_processor.combine_audio_files(
            [str(f) for f in cleaned_audio_files], str(final_audio_wav)
        )

        # Convert to MP3
        audio_processor.convert_to_mp3(str(final_audio_wav), str(final_audio_mp3))

        return {
            "artifacts": {
                "final_audio.wav": str(final_audio_wav),
                "final_audio.mp3": str(final_audio_mp3),
            },
            "metadata": {
                "input_files_count": len(cleaned_audio_files),
                "final_audio_duration": "calculated",  # Would need to calculate actual duration
            },
        }

    def _execute_image_generation(
        self, manifest_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute image generation step."""
        if self.text_only:
            logger.info("Skipping image generation in text-only mode")
            return {"artifacts": {}, "metadata": {"skipped": True}}

        logger.info("Executing image generation")

        # Get script from previous step
        script_file = self.cache_dir / "script.md"
        if not script_file.exists():
            raise FileNotFoundError("Script file not found")

        with open(script_file, "r", encoding="utf-8") as f:
            script_content = f.read()

        image_service = self._get_service("image_generator")

        # Generate images for key moments in the script
        lines = script_content.split("\n")
        image_files = []

        for i, line in enumerate(lines):
            if line.strip() and "[S1]" in line:  # Generate image for speaker 1 lines
                image_file = self.cache_dir / f"image_{i:03d}.png"
                image_service.generate_image(line, str(image_file))
                image_files.append(str(image_file))

        return {
            "artifacts": {
                **{
                    f"image_{i:03d}.png": image_files[i]
                    for i in range(len(image_files))
                },
            },
            "metadata": {
                "images_generated": len(image_files),
            },
        }

    def _execute_video_generation(
        self, manifest_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute video generation step."""
        if self.text_only:
            logger.info("Skipping video generation in text-only mode")
            return {"artifacts": {}, "metadata": {"skipped": True}}

        logger.info("Executing video generation")

        # Get final audio and images
        final_audio = self.cache_dir / "final_audio.mp3"
        image_files = list(self.cache_dir.glob("image_*.png"))
        image_files.sort()

        if not final_audio.exists():
            raise FileNotFoundError("Final audio file not found")

        video_service = self._get_service("video_generator")

        # Create final video
        final_video = self.cache_dir / "final_video.mp4"
        video_service.create_video(
            str(final_audio), [str(f) for f in image_files], str(final_video)
        )

        return {
            "artifacts": {
                "final_video.mp4": str(final_video),
            },
            "metadata": {
                "input_audio": str(final_audio),
                "input_images_count": len(image_files),
            },
        }

    def _execute_asr_processing(self, manifest_data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute ASR processing step."""
        logger.info("Executing ASR processing")

        # Get audio file from manifest
        audio_file = manifest_data.get("audio_file")
        if not audio_file:
            raise ValueError("No audio file provided for ASR processing")

        asr_service = self._get_service("asr_service")
        transcript = asr_service.transcribe_audio(audio_file)

        # Save transcript
        transcript_file = self.cache_dir / "transcript.txt"
        with open(transcript_file, "w", encoding="utf-8") as f:
            f.write(transcript)

        return {
            "artifacts": {
                "transcript.txt": str(transcript_file),
            },
            "metadata": {
                "transcript_length": len(transcript),
                "audio_file": audio_file,
            },
        }

    def _create_story_directory(self, title: str) -> Path:
        """Create a story-specific output directory."""
        sanitized_title = sanitize_filename(title)
        story_dir = self.cache_dir / sanitized_title
        story_dir.mkdir(exist_ok=True)
        return story_dir
