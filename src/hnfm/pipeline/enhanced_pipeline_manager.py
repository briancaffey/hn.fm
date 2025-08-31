"""Enhanced pipeline manager with Redis-first design and service locking"""

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
class EnhancedPipelineStep:
    """Enhanced pipeline step with locking and versioning support"""

    name: str
    description: str
    dependencies: List[str]
    cache_key: str
    output_files: List[str]
    service_name: str  # Service that needs to be locked
    lock_timeout: int = 300  # Lock timeout in seconds
    completed: bool = False
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    error: Optional[str] = None
    version: int = 1
    artifacts: Dict[str, str] = None
    metadata: Dict[str, Any] = None


@dataclass
class EnhancedPipelineState:
    """Enhanced pipeline state with Redis integration"""

    story_id: str
    story_title: str
    current_step: str
    steps: Dict[str, EnhancedPipelineStep]
    metadata: Dict[str, Any]
    created_at: datetime
    updated_at: datetime
    manifest_id: Optional[str] = None
    redis_synced: bool = False


class EnhancedPipelineManager:
    """Enhanced pipeline manager with Redis-first design and service locking"""

    def __init__(
        self,
        cache_dir: Optional[str] = None,
        text_only: bool = False,
        redis_integration: bool = True,
    ):
        """Initialize enhanced pipeline manager.

        Args:
            cache_dir: Cache directory path
            text_only: If True, only generate text content (no TTS, images, or video)
            redis_integration: Whether to use Redis integration
        """
        self.cache_dir = Path(
            cache_dir or config_manager.get("pipeline.cache.directory", "cache")
        )
        self.cache_dir.mkdir(exist_ok=True)

        self.text_only = text_only
        self.redis_integration = redis_integration

        # Initialize services lazily to avoid dependency issues
        self._services = {}

        # Enhanced pipeline steps definition
        self.pipeline_steps = self._define_enhanced_pipeline_steps()

        if text_only:
            logger.info(
                "Running in text-only mode - TTS, image, and video generation will be skipped"
            )

        if redis_integration:
            logger.info(
                "Redis integration enabled - using enhanced locking and versioning"
            )

        # Initialize Redis components if integration is enabled
        self.redis_repo = None
        self.lock_manager = None
        if redis_integration:
            try:
                from hnfm.web.redis_repo import RedisRepository
                from hnfm.web.locks import ServiceLockManager

                self.redis_repo = RedisRepository()
                self.lock_manager = ServiceLockManager(self.redis_repo.redis_client)
                logger.info("Redis components initialized successfully")
            except ImportError as e:
                logger.warning(f"Redis integration not available: {e}")
                self.redis_integration = False

    def _define_enhanced_pipeline_steps(self) -> Dict[str, EnhancedPipelineStep]:
        """Define the enhanced pipeline steps with service locking information."""
        base_steps = {
            "system_check": EnhancedPipelineStep(
                name="system_check",
                description="Check all required services are running",
                dependencies=[],
                cache_key="system_status",
                output_files=["system_status.json"],
                service_name="system",
                lock_timeout=60,
            ),
            "hn_scraping": EnhancedPipelineStep(
                name="hn_scraping",
                description="Scrape Hacker News articles",
                dependencies=["system_check"],
                cache_key="hn_articles",
                output_files=["hn_articles.json"],
                service_name="hn_api",
                lock_timeout=120,
            ),
            "firecrawl_content": EnhancedPipelineStep(
                name="firecrawl_content",
                description="Extract content using Firecrawl",
                dependencies=["hn_scraping"],
                cache_key="firecrawl_content",
                output_files=["raw_content.md", "processed_content.json"],
                service_name="firecrawl",
                lock_timeout=300,
            ),
            "content_processing": EnhancedPipelineStep(
                name="content_processing",
                description="Process and clean content",
                dependencies=["firecrawl_content"],
                cache_key="processed_content",
                output_files=["cleaned_content.md", "meaningful_paragraphs.json"],
                service_name="llm",
                lock_timeout=600,
            ),
            "script_generation": EnhancedPipelineStep(
                name="script_generation",
                description="Generate podcast script with [S1]/[S2] tags",
                dependencies=["content_processing"],
                cache_key="script",
                output_files=["script.md", "script_metadata.json"],
                service_name="llm",
                lock_timeout=600,
            ),
            "tts_generation": EnhancedPipelineStep(
                name="tts_generation",
                description="Generate TTS audio in batches",
                dependencies=["script_generation"],
                cache_key="tts_audio",
                output_files=["tts_lines_*.txt", "audio_*.wav"],
                service_name="tts",
                lock_timeout=1800,
            ),
            "audio_cleaning": EnhancedPipelineStep(
                name="audio_cleaning",
                description="Clean audio using Studio Voice",
                dependencies=["tts_generation"],
                cache_key="cleaned_audio",
                output_files=["cleaned_audio_*.wav"],
                service_name="studio_voice",
                lock_timeout=900,
            ),
            "audio_assembly": EnhancedPipelineStep(
                name="audio_assembly",
                description="Combine all audio into final file",
                dependencies=["audio_cleaning"],
                cache_key="final_audio",
                output_files=["final_audio.wav", "final_audio.mp3"],
                service_name="audio_processor",
                lock_timeout=300,
            ),
            "image_generation": EnhancedPipelineStep(
                name="image_generation",
                description="Generate images for video",
                dependencies=["script_generation"],
                cache_key="images",
                output_files=["image_*.png", "image_*.jpg"],
                service_name="vision",
                lock_timeout=1200,
            ),
            "video_generation": EnhancedPipelineStep(
                name="video_generation",
                description="Create final video with audio and images",
                dependencies=["audio_assembly", "image_generation"],
                cache_key="video",
                output_files=["final_video.mp4"],
                service_name="video",
                lock_timeout=1800,
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

    def execute_step_with_locking(
        self,
        step_name: str,
        manifest_data: Dict[str, Any],
        segment_data: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        """Execute a pipeline step with proper service locking."""

        if not self.redis_integration or not self.lock_manager:
            logger.warning("Redis integration not available, executing without locking")
            return self._execute_step_directly(step_name, manifest_data)

        step = self.pipeline_steps.get(step_name)
        if not step:
            raise ValueError(f"Unknown pipeline step: {step_name}")

        service_name = step.service_name
        lock_timeout = step.lock_timeout

        logger.info(f"Executing step {step_name} with service lock on {service_name}")

        with self.lock_manager.service_lock(service_name, lock_timeout):
            return self._execute_step_directly(step_name, manifest_data, segment_data)

    def _execute_step_directly(
        self,
        step_name: str,
        manifest_data: Dict[str, Any],
        segment_data: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        """Execute a pipeline step directly without locking."""
        logger.info(f"Executing pipeline step directly: {step_name}")
        logger.debug(f"Manifest data: {manifest_data}")
        if segment_data:
            logger.debug(f"Segment data: {segment_data}")

        # Execute the step using enhanced pipeline logic
        if step_name == "firecrawl_content":
            return self._execute_firecrawl_content(manifest_data)
        elif step_name == "content_processing":
            return self._execute_content_processing(manifest_data)
        elif step_name == "script_generation":
            return self._execute_script_generation(manifest_data)
        elif step_name == "tts_generation":
            return self._execute_tts_generation(manifest_data)
        elif step_name == "image_generation":
            return self._execute_image_generation(manifest_data)
        elif step_name == "video_generation":
            return self._execute_video_generation(manifest_data)
        else:
            raise ValueError(
                f"Step {step_name} not implemented in enhanced pipeline manager"
            )

    def get_enhanced_pipeline_status(self, content_id: str) -> Optional[Dict[str, Any]]:
        """Get enhanced pipeline status for a content item."""
        if not self.redis_integration or not self.redis_repo:
            logger.warning(
                "Redis integration not available, cannot get enhanced status"
            )
            return None

        try:
            status = self.redis_repo.get_enhanced_pipeline_status(content_id)
            if status:
                return status.dict()
            return None
        except Exception as e:
            logger.error(f"Error getting enhanced pipeline status: {e}")
            return None

    def retry_failed_step(
        self, content_id: str, step_name: str
    ) -> Optional[Dict[str, Any]]:
        """Retry a failed pipeline step."""
        if not self.redis_integration or not self.redis_repo:
            logger.warning("Redis integration not available, cannot retry step")
            return None

        try:
            # Find the failed segment
            manifest = self.redis_repo.get_or_create_manifest(content_id)
            segment = manifest.segments.get(step_name)

            if not segment or segment.status != "failed":
                logger.warning(f"No failed segment found for {step_name}")
                return None

            # Retry the segment
            new_segment = self.redis_repo.retry_segment(segment.segment_id)

            if new_segment:
                logger.info(
                    f"Successfully retried step {step_name} as {new_segment.segment_id}"
                )
                return {
                    "step_name": step_name,
                    "new_segment_id": new_segment.segment_id,
                    "status": "retry_initiated",
                }

            return None

        except Exception as e:
            logger.error(f"Error retrying failed step {step_name}: {e}")
            return None

    def cleanup_old_versions(
        self, content_id: str, keep_versions: int = 2
    ) -> Dict[str, Any]:
        """Clean up old versions of pipeline steps."""
        if not self.redis_integration or not self.redis_repo:
            logger.warning("Redis integration not available, cannot cleanup versions")
            return {"cleaned_count": 0, "error": "Redis integration not available"}

        try:
            manifest = self.redis_repo.get_or_create_manifest(content_id)
            cleaned_count = 0

            for step_name, segment in manifest.segments.items():
                if segment.status == "completed" and segment.version > keep_versions:
                    # Remove old segment
                    segment_key = f"hnfm:segments:{content_id}:{step_name}"
                    self.redis_repo.redis_client.delete(segment_key)
                    cleaned_count += 1
                    logger.info(f"Cleaned up old segment {segment.segment_id}")

            return {
                "cleaned_count": cleaned_count,
                "content_id": content_id,
                "keep_versions": keep_versions,
            }

        except Exception as e:
            logger.error(f"Error cleaning up old versions: {e}")
            return {"cleaned_count": 0, "error": str(e)}

    def get_service_lock_status(self) -> Dict[str, Any]:
        """Get status of all service locks."""
        if not self.redis_integration or not self.lock_manager:
            return {"error": "Redis integration not available"}

        try:
            service_names = [
                "firecrawl",
                "llm",
                "tts",
                "vision",
                "video",
                "studio_voice",
                "audio_processor",
            ]
            lock_statuses = {}

            for service_name in service_names:
                is_locked = self.lock_manager.is_service_locked(service_name)
                lock_info = (
                    self.lock_manager.get_lock_info(service_name) if is_locked else None
                )

                lock_statuses[service_name] = {
                    "is_locked": is_locked,
                    "lock_info": lock_info,
                }

            return {"timestamp": datetime.now().isoformat(), "services": lock_statuses}

        except Exception as e:
            logger.error(f"Error getting service lock status: {e}")
            return {"error": str(e)}

    def force_release_service_lock(self, service_name: str) -> Dict[str, Any]:
        """Force release a service lock (use with caution)."""
        if not self.redis_integration or not self.lock_manager:
            return {"error": "Redis integration not available"}

        try:
            success = self.lock_manager.force_release_lock(service_name)
            return {
                "service_name": service_name,
                "force_released": success,
                "timestamp": datetime.now().isoformat(),
            }

        except Exception as e:
            logger.error(f"Error force releasing lock for {service_name}: {e}")
            return {"error": str(e)}

    def _create_story_directory(self, title: str) -> Path:
        """Create a story-specific output directory."""
        # Sanitize the title for use as a directory name
        safe_title = sanitize_filename(title)
        story_dir = self.cache_dir / safe_title
        story_dir.mkdir(exist_ok=True)
        return story_dir

    def _execute_firecrawl_content(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Execute Firecrawl content extraction step."""
        try:
            # Get the selected article from previous step
            selected_article = inputs.get("selected_article")
            if not selected_article:
                raise RuntimeError("No selected article found in inputs")

            url = selected_article.get("url")
            title = selected_article.get("title", "Unknown Title")

            # Debug logging
            logger.debug(f"Selected article: {selected_article}")
            logger.debug(f"Title extracted: {title}")
            logger.debug(f"URL extracted: {url}")

            if not url:
                raise RuntimeError("No URL found in selected article")

            print(f"   🌐 Extracting content from: {url}")
            print(f"   📖 Article title: {title}")
            logger.info(f"🌐 Extracting content from: {url}")
            logger.info(f"📖 Article title: {title}")

            # Create story-specific output directory
            story_dir = self._create_story_directory(title)
            content_dir = story_dir / "content"
            content_dir.mkdir(exist_ok=True)

            # Save HN metadata to hn.yaml file
            hn_scraper = self._get_service("hn_scraper")
            selected_article_id = selected_article.get("id")
            if selected_article_id:
                hn_metadata_path = hn_scraper.save_story_metadata(
                    selected_article_id, content_dir
                )
                if hn_metadata_path:
                    print(f"   📊 Saved HN metadata to: {hn_metadata_path.name}")
                    logger.info(f"📊 Saved HN metadata to: {hn_metadata_path}")
                else:
                    print(f"   ⚠️ Failed to save HN metadata")
                    logger.warning(
                        f"Failed to save HN metadata for article {selected_article_id}"
                    )

            # Extract content using Firecrawl
            content_scraper = self._get_service("content_scraper")
            extracted_content = content_scraper.extract_content(url)

            if not extracted_content:
                raise RuntimeError("No content extracted from URL")

            # Save raw content to markdown file
            raw_content_path = content_dir / "raw_content.md"
            with open(raw_content_path, "w", encoding="utf-8") as f:
                f.write(extracted_content.get("content", ""))

            # Save processed content data
            processed_content_path = content_dir / "processed_content.json"
            with open(processed_content_path, "w", encoding="utf-8") as f:
                json.dump(extracted_content, f, indent=2, ensure_ascii=False)

            # Clear, high-level content extraction logging
            content_length = len(extracted_content.get("content", ""))
            print(f"   ✅ Content extracted: {content_length:,} characters")
            print(f"   📁 Saved to: {Path(content_dir).name}")

            logger.info(f"✅ Content extracted successfully")
            logger.info(f"📝 Content length: {content_length} characters")
            logger.info(f"📁 Saved to: {content_dir}")

            # Log what we're returning
            logger.debug(f"🔍 Firecrawl content outputs:")
            logger.debug(f"🔍 Title: {title}")
            logger.debug(f"🔍 Story dir: {story_dir}")
            logger.debug(f"🔍 Content dir: {content_dir}")

            return {
                "raw_content": extracted_content.get("content", ""),
                "title": title,
                "url": url,
                "story_dir": str(story_dir),
                "content_dir": str(content_dir),
                "raw_content_path": str(raw_content_path),
                "processed_content_path": str(processed_content_path),
                "hn_metadata_path": (
                    str(hn_metadata_path) if "hn_metadata_path" in locals() else None
                ),
            }

        except Exception as e:
            logger.error(f"Failed to extract content: {e}")
            raise RuntimeError(f"Content extraction failed: {e}")

    def _execute_content_processing(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Execute content processing step."""
        try:
            raw_content = inputs.get("raw_content")
            content_dir = inputs.get("content_dir")

            if not raw_content:
                raise RuntimeError("No raw content found in inputs")
            if not content_dir:
                raise RuntimeError("No content directory found in inputs")

            logger.debug("🧹 Processing and cleaning content...")

            # Use the existing content processor
            content_processor = self._get_service("content_processor")

            # Clean the markdown content
            cleaned_content = content_processor._clean_markdown(raw_content)

            # Extract meaningful paragraphs
            meaningful_paragraphs = content_processor.extract_meaningful_paragraphs(
                cleaned_content
            )

            # Save cleaned content to markdown file
            cleaned_content_path = Path(content_dir) / "cleaned_content.md"
            with open(cleaned_content_path, "w", encoding="utf-8") as f:
                f.write(cleaned_content)

            # Save meaningful paragraphs to JSON file
            meaningful_paragraphs_path = (
                Path(content_dir) / "meaningful_paragraphs.json"
            )
            with open(meaningful_paragraphs_path, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "paragraphs": meaningful_paragraphs,
                        "count": len(meaningful_paragraphs),
                        "processed_at": datetime.now().isoformat(),
                    },
                    f,
                    indent=2,
                    ensure_ascii=False,
                )

            # Clear, high-level content processing logging
            print(
                f"   ✅ Content processed: {len(cleaned_content):,} chars → {len(meaningful_paragraphs)} paragraphs"
            )
            print(f"   📁 Saved to: {Path(content_dir).name}")

            logger.info(f"✅ Content processed successfully")
            logger.info(f"📝 Cleaned content length: {len(cleaned_content)} characters")
            logger.info(f"📄 Meaningful paragraphs: {len(meaningful_paragraphs)}")
            logger.info(f"📁 Saved to: {content_dir}")

            # Log what we're passing through
            logger.debug(f"🔍 Content processing outputs:")
            logger.debug(f"🔍 Title: {inputs.get('title')}")
            logger.debug(f"🔍 Story dir: {inputs.get('story_dir')}")
            logger.debug(f"🔍 Content dir: {inputs.get('content_dir')}")

            return {
                "cleaned_content": cleaned_content,
                "meaningful_paragraphs": meaningful_paragraphs,
                "cleaned_content_path": str(cleaned_content_path),
                "meaningful_paragraphs_path": str(meaningful_paragraphs_path),
                "title": inputs.get("title"),  # Pass through the title
                "story_dir": inputs.get(
                    "story_dir"
                ),  # Pass through the story directory
                "content_dir": inputs.get(
                    "content_dir"
                ),  # Pass through the content directory
            }

        except Exception as e:
            logger.error(f"Failed to process content: {e}")
            raise RuntimeError(f"Content processing failed: {e}")

    def _execute_script_generation(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Execute script generation step."""
        try:
            meaningful_paragraphs = inputs.get("meaningful_paragraphs")
            title = inputs.get("title", "Unknown Title")
            content_dir = inputs.get("content_dir")

            # Debug logging to see what inputs we have
            logger.debug(f"Script generation inputs keys: {list(inputs.keys())}")
            logger.debug(f"Title from inputs: {title}")
            logger.debug(f"Content dir from inputs: {content_dir}")
            logger.debug(
                f"Meaningful paragraphs count: {len(meaningful_paragraphs) if meaningful_paragraphs else 'None'}"
            )

            if not meaningful_paragraphs:
                raise RuntimeError("No meaningful paragraphs found in inputs")
            if not content_dir:
                raise RuntimeError("No content directory found in inputs")

            logger.info("📝 Generating podcast script...")

            # Use the existing script generator
            script_generator = self._get_service("script_generator")

            # Generate script from content
            script_data = script_generator.generate_script_from_content(
                title, meaningful_paragraphs
            )

            # Save script to markdown file
            script_path = Path(content_dir) / "script.md"
            with open(script_path, "w", encoding="utf-8") as f:
                f.write(script_data.get("script", ""))

            # Save script metadata to JSON file
            script_metadata_path = Path(content_dir) / "script_metadata.json"
            with open(script_metadata_path, "w", encoding="utf-8") as f:
                json.dump(script_data, f, indent=2, ensure_ascii=False)

            # Clear, high-level script generation logging
            script_length = len(script_data.get("script", ""))
            print(f"   ✅ Script generated: {script_length:,} characters")
            print(f"   📁 Saved to: {Path(content_dir).name}")

            logger.info(f"✅ Script generated successfully")
            logger.info(f"📝 Script length: {script_length} characters")
            logger.info(f"📁 Saved to: {content_dir}")

            # Log what we're passing through
            logger.debug(f"🔍 Script generation outputs:")
            logger.debug(f"🔍 Title: {title}")
            logger.debug(f"🔍 Story dir: {inputs.get('story_dir')}")
            logger.debug(f"🔍 Content dir: {content_dir}")

            return {
                "script_path": str(script_path),
                "script_metadata_path": str(script_metadata_path),
                "script": script_data.get("script", ""),
                "title": title,  # Pass through the title
                "story_dir": inputs.get(
                    "story_dir"
                ),  # Pass through the story directory
                "content_dir": content_dir,  # Pass through the content directory
            }

        except Exception as e:
            logger.error(f"Failed to generate script: {e}")
            raise RuntimeError(f"Script generation failed: {e}")

    def _execute_tts_generation(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Execute TTS generation step."""
        try:
            script_content = inputs.get("script_content")
            content_id = inputs.get("content_id")

            if not script_content:
                raise RuntimeError("No script content found in inputs")

            logger.info("🎤 Generating TTS audio...")

            # Use the existing TTS service
            tts_service = self._get_service("tts_service")

            # Generate TTS audio
            tts_result = tts_service.generate_audio(script_content, content_id)

            logger.info(f"✅ TTS audio generated successfully")
            logger.info(f"🎵 Audio path: {tts_result.get('audio_path', 'N/A')}")

            return {
                "audio_path": tts_result.get("audio_path"),
                "tts_lines": tts_result.get("tts_lines", []),
                "content_id": content_id,
            }

        except Exception as e:
            logger.error(f"Failed to generate TTS audio: {e}")
            raise RuntimeError(f"TTS generation failed: {e}")

    def _execute_image_generation(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Execute image generation step."""
        try:
            script_content = inputs.get("script_content")
            content_id = inputs.get("content_id")

            if not script_content:
                raise RuntimeError("No script content found in inputs")

            logger.info("🖼️ Generating images...")

            # Use the existing image generation service
            image_generator = self._get_service("image_generator")

            # Generate images
            image_result = image_generator.generate_images(script_content, content_id)

            logger.info(f"✅ Images generated successfully")
            logger.info(f"🖼️ Image paths: {image_result.get('image_paths', [])}")

            return {
                "image_paths": image_result.get("image_paths", []),
                "content_id": content_id,
            }

        except Exception as e:
            logger.error(f"Failed to generate images: {e}")
            raise RuntimeError(f"Image generation failed: {e}")

    def _execute_video_generation(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Execute video generation step."""
        try:
            audio_path = inputs.get("audio_path")
            image_paths = inputs.get("image_paths", [])
            content_id = inputs.get("content_id")

            if not audio_path:
                raise RuntimeError("No audio path found in inputs")
            if not image_paths:
                raise RuntimeError("No image paths found in inputs")

            logger.info("🎬 Generating video...")

            # Use the existing video generator
            video_generator = self._get_service("video_generator")

            # Generate video
            video_result = video_generator.generate_video(
                audio_path, image_paths, content_id
            )

            logger.info(f"✅ Video generated successfully")
            logger.info(f"🎬 Video path: {video_result.get('video_path', 'N/A')}")

            return {
                "video_path": video_result.get("video_path"),
                "content_id": content_id,
            }

        except Exception as e:
            logger.error(f"Failed to generate video: {e}")
            raise RuntimeError(f"Video generation failed: {e}")
