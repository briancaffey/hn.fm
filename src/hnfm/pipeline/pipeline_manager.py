"""Pipeline manager for hn.fm workflow."""

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
    """Represents a pipeline step."""

    name: str
    description: str
    dependencies: List[str]
    cache_key: str
    output_files: List[str]
    completed: bool = False
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    error: Optional[str] = None


@dataclass
class PipelineState:
    """Represents the current state of the pipeline."""

    story_id: str
    story_title: str
    current_step: str
    steps: Dict[str, PipelineStep]
    metadata: Dict[str, Any]
    created_at: datetime
    updated_at: datetime


class PipelineManager:
    """Manages the hn.fm pipeline workflow."""

    def __init__(self, cache_dir: Optional[str] = None, text_only: bool = False):
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
            logger.info("Running in text-only mode - TTS, image, and video generation will be skipped")

    def _get_service(self, service_name: str):
        """Get a service instance, creating it if needed.

        Args:
            service_name: Name of the service

        Returns:
            Service instance
        """
        if service_name not in self._services:
            if service_name == "hn_scraper":
                self._services[service_name] = HNScraper()
            elif service_name == "content_scraper":
                # For local Firecrawl, don't pass API key
                base_url = config_manager.get("apis.firecrawl.base_url")
                self._services[service_name] = ContentScraper(
                    api_key=None, base_url=base_url
                )
            elif service_name == "content_processor":
                self._services[service_name] = ContentProcessor()
            elif service_name == "script_generator":
                self._services[service_name] = ScriptGenerator()
            elif service_name == "tts_service":
                self._services[service_name] = TTSService()
            elif service_name == "studio_voice_service":
                # Get Studio Voice configuration
                studio_voice_config = config_manager.get("studio_voice", {})
                target = studio_voice_config.get("target")
                model_type = studio_voice_config.get("model_type", "48k-hq")
                streaming = studio_voice_config.get("streaming", False)
                ssl_mode = studio_voice_config.get("ssl_mode")

                if not target:
                    raise ValueError("STUDIO_VOICE_TARGET environment variable not set")

                self._services[service_name] = StudioVoiceService(
                    target=target,
                    model_type=model_type,
                    streaming=streaming,
                    ssl_mode=ssl_mode,
                )
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

    def _define_pipeline_steps(self) -> Dict[str, PipelineStep]:
        """Define the pipeline steps and their dependencies."""
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
                description="Generate podcast script",
                dependencies=["content_processing"],
                cache_key="script",
                output_files=["script.txt", "tts_lines.txt", "script_meta.json"],
            ),
            "image_prompt_generation": PipelineStep(
                name="image_prompt_generation",
                description="Generate image prompts using LLM",
                dependencies=["script_generation"],
                cache_key="image_prompts",
                output_files=["content/main.yaml"],
            ),
        }

        # Add media generation steps only if not in text-only mode
        if not self.text_only:
            media_steps = {
                "image_generation": PipelineStep(
                    name="image_generation",
                    description="Generate images for script segments",
                    dependencies=["script_generation"],
                    cache_key="images",
                    output_files=["images/*.png"],
                ),
                "tts_generation": PipelineStep(
                    name="tts_generation",
                    description="Generate TTS audio",
                    dependencies=["image_generation"],
                    cache_key="tts_audio",
                    output_files=["batch_*.wav"],
                ),
                "audio_cleaning": PipelineStep(
                    name="audio_cleaning",
                    description="Clean audio using Studio Voice",
                    dependencies=["tts_generation"],
                    cache_key="cleaned_audio",
                    output_files=["cleaned_batch_*.wav"],
                ),
                "audio_assembly": PipelineStep(
                    name="audio_assembly",
                    description="Assemble final audio",
                    dependencies=["audio_cleaning"],
                    cache_key="final_audio",
                    output_files=["final_audio.wav"],
                ),
                "asr_processing": PipelineStep(
                    name="asr_processing",
                    description="Process audio through ASR service",
                    dependencies=["audio_assembly"],
                    cache_key="asr_results",
                    output_files=["content/asr.json"],
                ),
                "video_generation": PipelineStep(
                    name="video_generation",
                    description="Generate video with spoken words",
                    dependencies=["asr_processing"],
                    cache_key="video_results",
                    output_files=["content/video.mp4"],
                ),
            }
            base_steps.update(media_steps)

        return base_steps

    def _generate_cache_key(self, step_name: str, inputs: Dict[str, Any]) -> str:
        """Generate a cache key for a step.

        Args:
            step_name: Name of the step
            inputs: Input data for the step

        Returns:
            Cache key string
        """
        # Create a hash of the inputs
        input_str = json.dumps(inputs, sort_keys=True)
        input_hash = hashlib.md5(input_str.encode()).hexdigest()

        return f"{step_name}_{input_hash}"

    def _get_cache_path(self, cache_key: str) -> Path:
        """Get cache file path for a cache key.

        Args:
            cache_key: Cache key

        Returns:
            Cache file path
        """
        return self.cache_dir / f"{cache_key}.json"

    def _is_cache_valid(self, cache_key: str) -> bool:
        """Check if cache is valid and not expired.

        Args:
            cache_key: Cache key

        Returns:
            True if cache is valid
        """
        if not config_manager.get("pipeline.cache.enabled", True):
            return False

        cache_path = self._get_cache_path(cache_key)
        if not cache_path.exists():
            return False

        # Check expiration
        cache_age = datetime.now() - datetime.fromtimestamp(cache_path.stat().st_mtime)
        max_age = timedelta(
            hours=config_manager.get("pipeline.cache.expiration_hours", 24)
        )

        return cache_age < max_age

    def _load_from_cache(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """Load data from cache.

        Args:
            cache_key: Cache key

        Returns:
            Cached data or None
        """
        cache_path = self._get_cache_path(cache_key)

        try:
            with open(cache_path, "r") as f:
                data = json.load(f)
                logger.info(f"Loaded from cache: {cache_key}")
                return data
        except Exception as e:
            logger.warning(f"Failed to load from cache {cache_key}: {e}")
            return None

    def _save_to_cache(self, cache_key: str, data: Dict[str, Any]):
        """Save data to cache.

        Args:
            cache_key: Cache key
            data: Data to cache
        """
        cache_path = self._get_cache_path(cache_key)

        try:
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            with open(cache_path, "w") as f:
                json.dump(data, f, indent=2)
            logger.debug(f"Saved to cache: {cache_key}")
        except Exception as e:
            logger.error(f"Failed to save to cache {cache_key}: {e}")

    def _execute_step(
        self,
        step_name: str,
        inputs: Dict[str, Any],
        start_from_step: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Execute a single pipeline step.

        Args:
            step_name: Name of the step to execute
            inputs: Input data for the step
            start_from_step: Step to start from (for resuming)

        Returns:
            Step output data
        """
        step = self.pipeline_steps[step_name]

        # Check if we should skip this step
        if start_from_step and step_name in config_manager.get(
            "pipeline.skippable_steps", []
        ):
            # Check cache
            cache_key = self._generate_cache_key(step_name, inputs)
            if self._is_cache_valid(cache_key):
                cached_data = self._load_from_cache(cache_key)
                if cached_data:
                    step.completed = True
                    logger.info(f"⏭️  Skipping {step_name} (using cached data)")
                    return cached_data

        # Mark step as started
        step.start_time = datetime.now()
        step.completed = False
        step.error = None

        # Clear, high-level step start logging
        print(f"\n🔵 STEP {step_name.upper().replace('_', ' ')}")
        print(f"   {'=' * (len(step_name) + 6)}")
        logger.info(f"🚀 Starting {step_name} step...")

        try:
            # Execute the step
            if step_name == "system_check":
                output = self._execute_system_check(inputs)
            elif step_name == "hn_scraping":
                output = self._execute_hn_scraping(inputs)
            elif step_name == "firecrawl_content":
                output = self._execute_firecrawl_content(inputs)
            elif step_name == "content_processing":
                output = self._execute_content_processing(inputs)
            elif step_name == "script_generation":
                output = self._execute_script_generation(inputs)
            elif step_name == "image_prompt_generation":
                output = self._execute_image_prompt_generation(inputs)
            elif step_name == "image_generation":
                output = self._execute_image_generation(inputs)
            elif step_name == "tts_generation":
                output = self._execute_tts_generation(inputs)
            elif step_name == "audio_cleaning":
                output = self._execute_audio_cleaning(inputs)
            elif step_name == "audio_assembly":
                output = self._execute_audio_assembly(inputs)
            elif step_name == "asr_processing":
                output = self._execute_asr_processing(inputs)
            elif step_name == "video_generation":
                output = self._execute_video_generation(inputs)
            else:
                raise ValueError(f"Unknown step: {step_name}")

            # Mark step as completed
            step.completed = True
            step.end_time = datetime.now()

            # Cache the output
            cache_key = self._generate_cache_key(step_name, inputs)
            self._save_to_cache(cache_key, output)

            # Clear, high-level step completion logging
            duration = step.end_time - step.start_time
            print(
                f"   ✅ {step_name.upper().replace('_', ' ')} COMPLETED ({duration.total_seconds():.1f}s)"
            )
            logger.info(
                f"✅ Completed {step_name} step in {duration.total_seconds():.1f}s"
            )
            return output

        except Exception as e:
            step.error = str(e)
            step.end_time = datetime.now()
            print(f"❌ {step_name.upper().replace('_', ' ')} FAILED")
            logger.error(f"❌ Failed {step_name} step: {e}")
            raise

    def _execute_system_check(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Execute system check step."""
        try:
            from ..utils.system_checker import SystemChecker

            print("   🔍 Checking system health...")
            logger.debug("🔍 Checking system health...")

            # Check all services
            system_checker = SystemChecker()
            all_healthy, service_statuses = system_checker.check_all_services()

            # Define critical services that must be online
            critical_services = ["Local LLM", "Firecrawl"]
            critical_offline = [s.name for s in service_statuses if s.name in critical_services and s.status != "online"]

            if critical_offline:
                # Critical services are down - fail the pipeline
                error_msg = f"Critical services offline: {', '.join(critical_offline)}"
                print(f"   ❌ {error_msg}")
                logger.error(error_msg)

                if logger.isEnabledFor(logging.DEBUG):
                    for status in service_statuses:
                        if status.name in critical_services and status.status != "online":
                            print(f"      ❌ {status.name}: {status.status}")
                            if status.error_message:
                                print(f"         Error: {status.error_message}")

                raise RuntimeError(error_msg)

            # Show status for all services
            if logger.isEnabledFor(logging.DEBUG):
                # DEBUG mode: show detailed info for each service
                logger.debug("✅ Critical services are online")
                for status in service_statuses:
                    emoji = "✅" if status.status == "online" else "⚠️"
                    logger.debug(f"      {emoji} {status.name}: {status.status} ({status.response_time:.2f}s)")
                    if status.details:
                        for key, value in status.details.items():
                            logger.debug(f"         {key}: {value}")
                    if status.error_message:
                        logger.debug(f"         Warning: {status.error_message}")
            else:
                # INFO mode: just say critical services are ready
                logger.info("✅ Critical services are online and ready")
                offline_services = [s.name for s in service_statuses if s.status != "online"]
                if offline_services:
                    logger.info(f"   ⚠️  Non-critical services offline: {', '.join(offline_services)}")

            # Save system status to cache
            system_status_path = self.cache_dir / "system_status.json"
            with open(system_status_path, "w", encoding="utf-8") as f:
                json.dump({
                    "timestamp": datetime.now().isoformat(),
                    "all_healthy": all_healthy,
                    "critical_healthy": len(critical_offline) == 0,
                    "services": [
                        {
                            "name": s.name,
                            "status": s.status,
                            "response_time": s.response_time,
                            "error_message": s.error_message,
                            "details": s.details
                        }
                        for s in service_statuses
                    ]
                }, f, indent=2, ensure_ascii=False)

            return {
                "system_healthy": all_healthy,
                "critical_services_healthy": len(critical_offline) == 0,
                "services_status": [
                    {
                        "name": s.name,
                        "status": s.status,
                        "response_time": s.response_time,
                        "error_message": s.error_message,
                        "details": s.details
                    }
                    for s in service_statuses
                ],
                "timestamp": datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Failed to perform system check: {e}")
            raise RuntimeError(f"System check failed: {e}")

    def _execute_hn_scraping(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Execute HN scraping step."""
        try:
            hn_scraper = self._get_service("hn_scraper")

            # Get story type from inputs, default to "top"
            story_type = inputs.get("story_type", "top")

            logger.info(f"📰 Fetching Hacker News {story_type} stories...")

            # Get stories based on type
            if story_type == "top":
                articles = hn_scraper.get_top_stories()
            elif story_type == "newest":
                articles = hn_scraper.get_newest_stories()
            elif story_type == "show":
                articles = hn_scraper.get_show_stories()
            elif story_type == "ask":
                articles = hn_scraper.get_ask_stories()
            else:
                # Fallback to top stories
                articles = hn_scraper.get_top_stories()

            if not articles:
                raise RuntimeError(f"No {story_type} articles found on HN")

            # Select a random article (avoiding stickied posts and requiring URLs)
            import random

            valid_articles = [
                a for a in articles if not a.get("sticky", False) and a.get("url")
            ]
            if not valid_articles:
                # Fallback to any article with a URL
                valid_articles = [a for a in articles if a.get("url")]

            if not valid_articles:
                raise RuntimeError(f"No {story_type} articles with URLs found on HN")

            selected_article = random.choice(valid_articles)

            # Clear, high-level story selection logging
            print(f"   🎯 Selected: {selected_article.get('title', 'Unknown')[:80]}...")
            print(f"   🔗 URL: {selected_article.get('url', 'Unknown')}")
            print(
                f"   📊 Score: {selected_article.get('score', 'Unknown')} | Comments: {selected_article.get('descendants', 'Unknown')}"
            )

            logger.info(
                f"🎯 Selected article: {selected_article.get('title', 'Unknown')}"
            )
            logger.info(f"🔗 URL: {selected_article.get('url', 'Unknown')}")
            logger.info(f"📊 Score: {selected_article.get('score', 'Unknown')}")

            return {
                "articles": articles,
                "selected_article": selected_article,
                "article_count": len(articles),
                "story_type": story_type,
            }

        except Exception as e:
            logger.error(f"Failed to scrape HN: {e}")
            raise RuntimeError(f"HN scraping failed: {e}")

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
                hn_metadata_path = hn_scraper.save_story_metadata(selected_article_id, content_dir)
                if hn_metadata_path:
                    print(f"   📊 Saved HN metadata to: {hn_metadata_path.name}")
                    logger.info(f"📊 Saved HN metadata to: {hn_metadata_path}")
                else:
                    print(f"   ⚠️ Failed to save HN metadata")
                    logger.warning(f"Failed to save HN metadata for article {selected_article_id}")

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
                "hn_metadata_path": str(hn_metadata_path) if 'hn_metadata_path' in locals() else None,
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
                "story_dir": inputs.get("story_dir"),  # Pass through the story directory
                "content_dir": inputs.get("content_dir"),  # Pass through the content directory
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
            logger.debug(f"Meaningful paragraphs count: {len(meaningful_paragraphs) if meaningful_paragraphs else 'None'}")

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

            # Save TTS lines to text file
            tts_lines_path = Path(content_dir) / "tts_lines.txt"
            with open(tts_lines_path, "w", encoding="utf-8") as f:
                for line in script_data.get("tts_lines", []):
                    f.write(line + "\n")

            # Save script metadata to JSON file
            script_meta_path = Path(content_dir) / "script_meta.json"
            with open(script_meta_path, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "title": title,
                        "script_length": len(script_data.get("script", "")),
                        "tts_lines_count": len(script_data.get("tts_lines", [])),
                        "generated_at": datetime.now().isoformat(),
                    },
                    f,
                    indent=2,
                    ensure_ascii=False,
                )

                        # Create main content structure (always, regardless of text-only mode)
            try:
                from ..content import ContentManager
                content_manager = ContentManager()

                # Get image style from config
                image_style = config_manager.get("image_generation.default_style", "detailed cartoon style")

                # Get story_dir from inputs with detailed logging
                story_dir = inputs.get("story_dir")
                logger.debug(f"🔍 Script generation inputs keys: {list(inputs.keys())}")
                logger.debug(f"🔍 Story dir from inputs: {story_dir}")
                logger.debug(f"🔍 Title from inputs: {title}")
                logger.debug(f"🔍 Content dir from inputs: {content_dir}")

                if story_dir:
                    logger.info(f"✅ Creating main content structure in: {story_dir}")
                    main_yaml_path = content_manager.create_main_content_structure(
                        title=title,
                        script=script_data.get("script", ""),
                        tts_lines=script_data.get("tts_lines", []),
                        story_dir=Path(story_dir),
                        image_style=image_style
                    )

                    logger.info(f"✅ Created main content structure: {main_yaml_path}")
                else:
                    logger.error(f"❌ No story_dir found in inputs! Available keys: {list(inputs.keys())}")
                    logger.error(f"❌ This means the pipeline data flow is broken")
                    # Try to create it in the content_dir as fallback
                    try:
                        logger.info(f"🔄 Attempting fallback: creating main content structure in content_dir: {content_dir}")
                        main_yaml_path = content_manager.create_main_content_structure(
                            title=title,
                            script=script_data.get("script", ""),
                            tts_lines=script_data.get("tts_lines", []),
                            story_dir=Path(content_dir).parent,  # Go up one level from content/ to story_dir
                            image_style=image_style
                        )
                        logger.info(f"✅ Fallback successful: {main_yaml_path}")
                    except Exception as fallback_e:
                        logger.error(f"❌ Fallback also failed: {fallback_e}")

            except Exception as e:
                logger.error(f"❌ Failed to create main content structure: {e}")
                logger.error(f"❌ Full error details: {type(e).__name__}: {str(e)}")
                import traceback
                logger.error(f"❌ Traceback: {traceback.format_exc()}")
                # Don't fail the script generation step for this

            # Clear, high-level script generation logging
            script_length = len(script_data.get("script", ""))
            tts_lines_count = len(script_data.get("tts_lines", []))

            logger.info(f"✅ Script generated successfully")
            logger.info(f"📝 Script length: {script_length:,} characters")
            logger.info(f"🎙️ TTS lines: {tts_lines_count}")
            logger.info(f"📁 Saved to: {content_dir}")

            return {
                "script": script_data.get("script", ""),
                "tts_lines": script_data.get("tts_lines", []),
                "script_path": str(script_path),
                "tts_lines_path": str(tts_lines_path),
                "script_meta_path": str(script_meta_path),
            }

        except Exception as e:
            logger.error(f"Failed to generate script: {e}")
            raise RuntimeError(f"Script generation failed: {e}")

    def _execute_image_prompt_generation(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Execute image prompt generation step using LLM."""
        try:
            script_data = inputs.get("script")
            tts_lines = inputs.get("tts_lines")
            story_dir = inputs.get("story_dir")

            if not script_data:
                raise RuntimeError("No script data found for image prompt generation")
            if not story_dir:
                raise RuntimeError("No story directory found for image prompt generation")

            logger.info("🎨 Generating image prompts using LLM...")

            # Load the main content structure
            from ..content import ContentManager
            content_manager = ContentManager()

            try:
                content_data = content_manager.load_main_content(Path(story_dir))
                logger.debug("✅ Loaded main content structure for image prompt generation")
            except Exception as e:
                logger.warning(f"⚠️ Could not load main content structure: {e}")
                content_data = None

            # Generate image prompts using LLM
            from ..content import ImagePromptGenerator
            prompt_generator = ImagePromptGenerator()

            if content_data:
                # Use the content structure for better prompts
                logger.debug("🚀 Starting LLM-powered image prompt generation...")
                image_prompts = prompt_generator.batch_generate_prompts(content_data)
                logger.debug(f"✅ Generated {len(image_prompts)} image prompts using LLM")

                # Update the content structure with prompts
                content_manager.update_image_prompts(Path(story_dir), image_prompts)
                logger.info("✅ Updated main content structure with image prompts")

                # Log summary of generated prompts
                logger.debug("📋 Generated image prompts summary:")
                for i, prompt_data in enumerate(image_prompts[:3], 1):  # Show first 3
                    prompt_preview = prompt_data["prompt"][:80] + "..." if len(prompt_data["prompt"]) > 80 else prompt_data["prompt"]
                    logger.debug(f"   {i}. Group {prompt_data['group_id']}: {prompt_preview}")
                if len(image_prompts) > 3:
                    logger.debug(f"   ... and {len(image_prompts) - 3} more prompts")
            else:
                logger.warning("⚠️ No content data available for image prompt generation")
                logger.debug("📝 Will use fallback text-based prompts during image generation")

            logger.info(f"🎉 Image prompt generation complete! Generated {len(image_prompts) if content_data else 0} prompts")
            return {
                "image_prompts_generated": True,
                "prompt_count": len(image_prompts) if content_data else 0,
            }

        except Exception as e:
            logger.error(f"Failed to generate image prompts: {e}")
            raise RuntimeError(f"Image prompt generation failed: {e}")

    def _execute_image_generation(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Execute image generation step."""
        try:
            script_data = inputs.get("script")
            tts_lines = inputs.get("tts_lines")
            story_dir = inputs.get("story_dir")

            if not script_data:
                raise RuntimeError("No script data found for image generation")
            if not story_dir:
                raise RuntimeError("No story directory found for image generation")

            logger.info("🎨 Generating images for script segments...")

            # Load the main content structure
            from ..content import ContentManager
            content_manager = ContentManager()

            try:
                content_data = content_manager.load_main_content(Path(story_dir))
                logger.debug("✅ Loaded main content structure for image generation")
            except Exception as e:
                logger.warning(f"⚠️ Could not load main content structure: {e}")
                content_data = None

            # Generate image prompts using LLM
            from ..content import ImagePromptGenerator
            prompt_generator = ImagePromptGenerator()

            if content_data:
                # Use the content structure for better prompts
                logger.debug("🚀 Starting LLM-powered image prompt generation...")
                image_prompts = prompt_generator.batch_generate_prompts(content_data)
                logger.debug(f"✅ Generated {len(image_prompts)} image prompts using LLM")

                # Update the content structure with prompts
                content_manager.update_image_prompts(Path(story_dir), image_prompts)

                # Use the generated prompts for image generation
                script_segments = []
                for prompt_data in image_prompts:
                    script_segments.append({
                        "text": prompt_data["prompt"],
                        "group_id": prompt_data["group_id"]
                    })

                logger.debug(f"📝 Created {len(script_segments)} script segments from LLM prompts")
            else:
                # Fallback to simple text-based prompts
                logger.debug("📝 Using fallback text-based image prompts")
                script_segments = [{"text": line} for line in tts_lines]
                logger.debug(f"📝 Created {len(script_segments)} script segments from TTS lines")

            # Use the image generation service
            image_service = self._get_service("image_generator")

            # Create images directory
            images_dir = Path(story_dir) / "images"
            images_dir.mkdir(exist_ok=True)

            logger.info(f"🎨 Starting image generation process")
            logger.debug(f"📁 Images will be saved to: {images_dir}")
            logger.debug(f"📊 Processing {len(script_segments)} script segments")

            # Generate images for each script segment
            generated_images = image_service.generate_images_for_script(
                script_segments=script_segments,
                output_dir=images_dir
            )

            # Update content structure with generated images if available
            if content_data:
                try:
                    content_manager.update_generated_images(Path(story_dir), generated_images)
                    logger.info("✅ Updated content structure with generated images")
                except Exception as e:
                    logger.warning(f"⚠️ Failed to update content structure with images: {e}")

            # Clear, high-level image generation logging
            print(f"   ✅ Generated {len(generated_images)} images")
            print(f"   📁 Saved to: {images_dir.name}")

            logger.info(f"🎉 Image generation completed successfully")
            logger.info(f"🖼️ Generated {len(generated_images)} images")
            logger.info(f"📁 Images saved to: {images_dir}")

            # Log summary of generated images
            if generated_images:
                logger.debug("📋 Generated image files:")
                for i, img_path in enumerate(generated_images, 1):
                    logger.debug(f"   {i}. {img_path.name}")

            return {
                "generated_images": [str(img) for img in generated_images],
                "images_dir": str(images_dir),
                "image_count": len(generated_images),
            }

        except Exception as e:
            logger.error(f"Failed to generate images: {e}")
            raise RuntimeError(f"Image generation failed: {e}")

    def _execute_tts_generation(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Execute TTS generation step."""
        try:
            tts_lines = inputs.get("tts_lines")
            title = inputs.get("title", "Unknown Title")
            story_dir = inputs.get("story_dir")

            if not tts_lines:
                raise RuntimeError("No TTS lines found in inputs")
            if not story_dir:
                raise RuntimeError("No story directory found in inputs")

            print(f"   🎵 Generating TTS audio for {len(tts_lines)} lines...")
            print(f"   📝 Lines to process:")
            for i, line in enumerate(tts_lines[:3], 1):  # Show first 3 lines
                first_words = line[:50].replace("\n", " ").strip()
                if len(first_words) >= 50:
                    first_words = first_words[:47] + "..."
                print(f"      {i}. {first_words}")
            if len(tts_lines) > 3:
                print(f"      ... and {len(tts_lines) - 3} more lines")

            # Log all lines for debugging
            logger.info(f"🎵 Generating TTS audio for {len(tts_lines)} lines...")
            for i, line in enumerate(tts_lines, 1):
                logger.info(f"📝 Line {i}: {line}")

            logger.info("🎵 Starting TTS generation process...")

            # Create audio directory
            audio_dir = Path(story_dir) / "audio"
            audio_dir.mkdir(exist_ok=True)

            # Create a temporary TTS lines file
            import tempfile
            import os

            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".txt", delete=False
            ) as f:
                for line in tts_lines:
                    f.write(line + "\n")
                temp_tts_file = f.name

            try:
                # Use the existing script generator to process TTS lines
                script_generator = self._get_service("script_generator")

                # Log TTS service status before starting
                tts_service = self._get_service("tts_service")
                if hasattr(tts_service, 'get_timeout_info'):
                    timeout_info = tts_service.get_timeout_info()
                    logger.info(f"🎵 TTS service configuration: {timeout_info}")

                final_audio_path = script_generator.process_tts_lines(
                    temp_tts_file, title, batch_size=2, story_dir=story_dir
                )

                # Move the final audio to the audio directory
                final_audio_name = f"{sanitize_filename(title)}_final.wav"
                final_audio_dest = audio_dir / final_audio_name

                if final_audio_path.exists():
                    import shutil

                    shutil.move(str(final_audio_path), str(final_audio_dest))
                    final_audio_path = final_audio_dest

                # Collect batch file paths
                batch_files = []
                cleaned_batch_files = []

                # Find all batch files in the story output directory
                # Use the actual story directory path that was created
                story_output_dir = Path(story_dir)
                if story_output_dir.exists():
                    for batch_file in story_output_dir.glob("audio/batch_*.wav"):
                        batch_files.append(str(batch_file))
                    for cleaned_batch_file in story_output_dir.glob(
                        "audio/cleaned_batch_*.wav"
                    ):
                        cleaned_batch_files.append(str(cleaned_batch_file))

                # Clear, high-level TTS completion logging
                print(
                    f"   ✅ TTS completed: {len(batch_files)} batches, {len(cleaned_batch_files)} cleaned"
                )
                print(f"   🎵 Final audio: {Path(final_audio_path).name}")

                logger.info(f"✅ TTS generation completed successfully")
                logger.info(f"🎵 Final audio: {final_audio_path}")
                logger.info(f"📁 Batch files: {len(batch_files)}")
                logger.info(f"🧹 Cleaned files: {len(cleaned_batch_files)}")
                logger.info(f"📁 Audio directory: {audio_dir}")

                return {
                    "final_audio": str(final_audio_path),
                    "batch_files": batch_files,
                    "cleaned_audio_files": [str(f) for f in cleaned_batch_files],
                    "batch_count": len(batch_files),
                    "audio_dir": str(audio_dir),
                }

            finally:
                # Clean up temporary file
                if os.path.exists(temp_tts_file):
                    os.unlink(temp_tts_file)

        except Exception as e:
            logger.error(f"Failed to generate TTS: {e}")
            raise RuntimeError(f"TTS generation failed: {e}")

    def _execute_audio_cleaning(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Execute audio cleaning step."""
        try:
            # Audio cleaning is already handled during TTS generation
            # This step validates the results and provides metadata
            cleaned_audio_files = inputs.get("cleaned_audio_files", [])
            batch_count = inputs.get("batch_count", 0)

            if not cleaned_audio_files:
                raise RuntimeError("No cleaned audio files found in inputs")

            logger.debug("🧹 Validating audio cleaning results...")

            # Calculate total size of cleaned files
            import os

            total_size = sum(
                os.path.getsize(f) for f in cleaned_audio_files if os.path.exists(f)
            )
            total_size_mb = total_size / (1024 * 1024)

            logger.info(f"✅ Audio cleaning validation completed")
            logger.info(f"📁 Cleaned files: {len(cleaned_audio_files)}")
            logger.info(f"💾 Total size: {total_size_mb:.2f} MB")

            return {
                "cleaned_files": cleaned_audio_files,
                "enhancement_stats": {
                    "processed_chunks": batch_count,
                    "total_files": len(cleaned_audio_files),
                    "total_size_mb": total_size_mb,
                },
            }

        except Exception as e:
            logger.error(f"Failed to validate audio cleaning: {e}")
            raise RuntimeError(f"Audio cleaning validation failed: {e}")

    def _execute_audio_assembly(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Execute audio assembly step."""
        try:
            # Audio assembly is already handled during TTS generation
            # This step validates the final result and provides metadata
            final_audio = inputs.get("final_audio")

            if not final_audio or not os.path.exists(final_audio):
                raise RuntimeError("Final audio file not found")

            print("   🎵 Validating final audio assembly...")
            logger.info("🎵 Validating final audio assembly...")

            # Get file metadata
            file_size = os.path.getsize(final_audio)
            file_size_mb = file_size / (1024 * 1024)

            # Calculate actual duration using wave library
            actual_duration = self._get_audio_duration(final_audio)
            if actual_duration:
                duration_minutes = actual_duration / 60
                print(f"   ✅ Final audio: {Path(final_audio).name}")
                print(f"   💾 File size: {file_size_mb:.2f} MB")
                print(
                    f"   ⏱️  Duration: {duration_minutes:.1f} minutes ({actual_duration:.1f}s)"
                )
            else:
                # Fallback to estimation
                estimated_duration = (
                    file_size_mb * 0.5
                )  # Rough estimate: 0.5 MB per minute
                print(f"   ✅ Final audio: {Path(final_audio).name}")
                print(f"   💾 File size: {file_size_mb:.2f} MB")
                print(f"   ⏱️  Estimated duration: {estimated_duration:.1f} minutes")

            logger.info(f"✅ Audio assembly validation completed")
            logger.info(f"🎵 Final audio: {final_audio}")
            logger.info(f"💾 File size: {file_size_mb:.2f} MB")
            if actual_duration:
                logger.info(
                    f"⏱️ Actual duration: {actual_duration:.1f} seconds ({actual_duration/60:.1f} minutes)"
                )
            else:
                logger.info(f"⏱️ Estimated duration: {estimated_duration:.1f} minutes")

            return {
                "final_audio": final_audio,
                "total_duration": actual_duration or estimated_duration,
                "file_size_mb": file_size_mb,
                "status": "completed",
            }

        except Exception as e:
            logger.error(f"Failed to validate audio assembly: {e}")
            raise RuntimeError(f"Audio assembly validation failed: {e}")

    def _execute_asr_processing(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Execute ASR processing step."""
        try:
            final_audio = inputs.get("final_audio")
            story_dir = inputs.get("story_dir")

            if not final_audio or not os.path.exists(final_audio):
                raise RuntimeError("Final audio file not found for ASR processing")
            if not story_dir:
                raise RuntimeError("No story directory found for ASR processing")

            logger.info("🎙️ Processing audio through ASR...")

            # Create a temporary audio file for ASR
            import tempfile

            with tempfile.NamedTemporaryFile(
                mode="wb", suffix=".wav", delete=False
            ) as f:
                with open(final_audio, "rb") as src_f:
                    f.write(src_f.read())
                temp_audio_file = f.name

            try:
                # Use the ASR service directly
                asr_service = self._get_service("asr_service")

                # Log ASR service status before starting
                if hasattr(asr_service, 'get_timeout_info'):
                    timeout_info = asr_service.get_timeout_info()
                    logger.info(f"🎙️ ASR service configuration: {timeout_info}")

                # Define the output path
                asr_results_path = Path(story_dir) / "content" / "asr.json"

                # Process and save the audio file
                asr_results = asr_service.process_and_save(
                    audio_file_path=temp_audio_file,
                    output_path=str(asr_results_path)
                )

                # Clear, high-level ASR completion logging
                logger.info(f"✅ ASR processing completed successfully")
                logger.info(f"📄 ASR results saved: {asr_results_path}")

                return {
                    "asr_results": asr_results,
                    "asr_results_path": str(asr_results_path),
                }

            finally:
                # Clean up temporary file
                if Path(temp_audio_file).exists():
                    Path(temp_audio_file).unlink()

        except Exception as e:
            logger.error(f"Failed to perform ASR processing: {e}")
            raise RuntimeError(f"ASR processing failed: {e}")

    def _execute_video_generation(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Execute video generation step."""
        try:
            asr_results_path = inputs.get("asr_results_path")
            final_audio = inputs.get("final_audio")
            story_dir = inputs.get("story_dir")

            if not asr_results_path or not os.path.exists(asr_results_path):
                raise RuntimeError("ASR results file not found for video generation")
            if not final_audio or not os.path.exists(final_audio):
                raise RuntimeError("Final audio file not found for video generation")
            if not story_dir:
                raise RuntimeError("No story directory found for video generation")

            logger.info("🎬 Generating video with spoken words...")

            # Use the video generator service
            video_service = self._get_service("video_generator")

            # Define the output path
            video_output_path = Path(story_dir) / "content" / "video.mp4"

            # Get the main.yaml path for content structure
            main_yaml_path = Path(story_dir) / "content" / "main.yaml"
            if not main_yaml_path.exists():
                raise RuntimeError(f"Main content file not found: {main_yaml_path}")

            # Generate the video
            video_results = video_service.process_and_save(
                asr_file_path=asr_results_path,
                audio_file_path=final_audio,
                main_yaml_path=str(main_yaml_path),
                output_path=str(video_output_path)
            )

            logger.info(f"✅ Video generation completed successfully")
            logger.info(f"🎥 Video saved: {video_output_path}")

            return {
                "video_results": video_results,
                "video_path": str(video_output_path),
            }

        except Exception as e:
            logger.error(f"Failed to perform video generation: {e}")
            raise RuntimeError(f"Video generation failed: {e}")

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

    def _create_story_directory(self, story_title: str) -> Path:
        """Create a directory for a story, ensuring it's unique."""
        base_dir = Path("outputs")
        base_dir.mkdir(exist_ok=True)

        # Safety check for None or empty title
        if not story_title or story_title == "Unknown Title":
            story_title = "unknown_article"
            logger.warning("Using fallback title 'unknown_article' for directory creation")

        # Generate a unique name for the story directory
        safe_title = self._sanitize_filename(story_title)

        # Add timestamp-based hex suffix for uniqueness
        import time

        timestamp_hex = hex(int(time.time()))[2:8]  # 6-character hex from timestamp

        final_title = f"{safe_title}_{timestamp_hex}"

        story_dir = base_dir / final_title
        story_dir.mkdir(exist_ok=True)

        return story_dir

    def _sanitize_filename(self, filename: str) -> str:
        """Sanitize a filename to be safe for file systems.

        Args:
            filename: Original filename to sanitize

        Returns:
            Sanitized filename safe for file systems
        """
        return sanitize_filename(filename)

    def run_pipeline(
        self,
        story_id: str,
        story_title: str,
        story_type: str = "top",
        start_from_step: Optional[str] = None,
        inputs: Optional[Dict[str, Any]] = None,
    ) -> PipelineState:
        """Run the complete pipeline.

        Args:
            story_id: Unique identifier for the story
            story_title: Title of the story
            story_type: Type of HN stories to scrape (top, newest, show, ask)
            start_from_step: Step to start from (for resuming)
            inputs: Initial inputs for the pipeline

        Returns:
            Pipeline state
        """
        # Initialize pipeline state
        state = PipelineState(
            story_id=story_id,
            story_title=story_title,
            current_step="",
            steps=self.pipeline_steps.copy(),
            metadata=inputs or {},
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

        if start_from_step:
            logger.info(f"🔄 Resuming from step: {start_from_step}")

        # Execute steps in order
        current_inputs = inputs or {}
        current_inputs["story_type"] = story_type

        for step_name in self.pipeline_steps:
            # Skip steps before start_from_step
            if start_from_step and step_name != start_from_step:
                if (
                    step_name
                    not in [start_from_step]
                    + self.pipeline_steps[start_from_step].dependencies
                ):
                    continue

            try:
                state.current_step = step_name
                state.updated_at = datetime.now()

                # Execute the step
                output = self._execute_step(step_name, current_inputs, start_from_step)

                # Log the data flow between steps
                logger.debug(f"🔍 Step {step_name} completed with {len(output)} outputs")
                logger.debug(f"🔍 Step {step_name} output keys: {list(output.keys())}")
                if "story_dir" in output:
                    logger.debug(f"🔍 Step {step_name} story_dir: {output['story_dir']}")
                if "title" in output:
                    logger.debug(f"🔍 Step {step_name} title: {output['title']}")

                # Update inputs for next step
                current_inputs.update(output)

                # Update state
                state.steps[step_name] = self.pipeline_steps[step_name]

            except Exception as e:
                logger.error(f"Pipeline failed at step {step_name}: {e}")
                state.current_step = step_name
                state.updated_at = datetime.now()
                raise

        logger.info(f"🎉 Pipeline completed successfully for story: {story_title}")
        return state

    def get_pipeline_status(self, story_id: str) -> Optional[PipelineState]:
        """Get the current status of a pipeline run.

        Args:
            story_id: Story identifier

        Returns:
            Pipeline state or None if not found
        """
        # This would load from persistent storage
        # For now, return None
        return None

    def list_pipeline_runs(self) -> List[PipelineState]:
        """List all pipeline runs.

        Returns:
            List of pipeline states
        """
        # This would load from persistent storage
        # For now, return empty list
        return []
