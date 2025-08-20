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
from hnfm.scraper.hn_scraper import HNScraper
from hnfm.scraper.content_scraper import ContentScraper
from hnfm.content.content_processor import ContentProcessor
from hnfm.content.script_generator import ScriptGenerator
from hnfm.audio.tts_service import TTSService
from hnfm.audio.studio_voice_service import StudioVoiceService
from hnfm.audio.audio_processor import AudioProcessor

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

    def __init__(self, cache_dir: Optional[str] = None):
        """Initialize pipeline manager.

        Args:
            cache_dir: Cache directory path
        """
        self.cache_dir = Path(
            cache_dir or config_manager.get("pipeline.cache.directory", "cache")
        )
        self.cache_dir.mkdir(exist_ok=True)

        # Initialize services lazily to avoid dependency issues
        self._services = {}

        # Pipeline steps definition
        self.pipeline_steps = self._define_pipeline_steps()

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
            else:
                raise ValueError(f"Unknown service: {service_name}")

        return self._services[service_name]

    def _define_pipeline_steps(self) -> Dict[str, PipelineStep]:
        """Define the pipeline steps and their dependencies."""
        return {
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
            "tts_generation": PipelineStep(
                name="tts_generation",
                description="Generate TTS audio",
                dependencies=["script_generation"],
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
        }

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
            logger.info(f"Saved to cache: {cache_key}")
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
            elif step_name == "tts_generation":
                output = self._execute_tts_generation(inputs)
            elif step_name == "audio_cleaning":
                output = self._execute_audio_cleaning(inputs)
            elif step_name == "audio_assembly":
                output = self._execute_audio_assembly(inputs)
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
                f"✅ {step_name.upper().replace('_', ' ')} COMPLETED ({duration.total_seconds():.1f}s)"
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
            logger.info("🔍 Checking system health...")

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
                print("   ✅ Critical services are online")
                for status in service_statuses:
                    emoji = "✅" if status.status == "online" else "⚠️"
                    print(f"      {emoji} {status.name}: {status.status} ({status.response_time:.2f}s)")
                    if status.details:
                        for key, value in status.details.items():
                            print(f"         {key}: {value}")
                    if status.error_message:
                        print(f"         Warning: {status.error_message}")
            else:
                # INFO mode: just say critical services are ready
                print("   ✅ Critical services are online and ready")
                offline_services = [s.name for s in service_statuses if s.status != "online"]
                if offline_services:
                    print(f"   ⚠️  Non-critical services offline: {', '.join(offline_services)}")

            logger.info("✅ Critical services are online and ready")

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

            print(f"   📰 Fetching Hacker News {story_type} stories...")
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

            return {
                "raw_content": extracted_content.get("content", ""),
                "title": title,
                "url": url,
                "story_dir": str(story_dir),
                "content_dir": str(content_dir),
                "raw_content_path": str(raw_content_path),
                "processed_content_path": str(processed_content_path),
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

            print("   🧹 Processing and cleaning content...")
            logger.info("🧹 Processing and cleaning content...")

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

            print("   📝 Generating podcast script using LLM...")
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

            # Clear, high-level script generation logging
            script_length = len(script_data.get("script", ""))
            tts_lines_count = len(script_data.get("tts_lines", []))
            print(
                f"   ✅ Script generated: {script_length:,} chars, {tts_lines_count} TTS lines"
            )
            print(f"   📁 Saved to: {Path(content_dir).name}")

            logger.info(f"✅ Script generated successfully")
            logger.info(f"📝 Script length: {script_length} characters")
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
            logger.info("🎵 Generating TTS audio...")

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
                final_audio_path = script_generator.process_tts_lines(
                    temp_tts_file, title, batch_size=2, story_dir=story_dir
                )

                # Move the final audio to the audio directory
                final_audio_name = f"{title.replace(' ', '_')}_final.wav"
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

            logger.info("🧹 Validating audio cleaning results...")

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
        import re

        # Replace problematic characters with safe alternatives
        replacements = {
            ':': ' - ',      # Colon -> dash
            '?': '',         # Question mark -> remove
            '!': '',         # Exclamation mark -> remove
            '"': '',         # Double quote -> remove
            "'": '',         # Single quote -> remove
            '<': '(',        # Less than -> parenthesis
            '>': ')',        # Greater than -> parenthesis
            '|': '-',        # Pipe -> dash
            '*': '',         # Asterisk -> remove
            '/': '-',        # Forward slash -> dash
            '\\': '-',       # Backslash -> dash
            '[': '(',        # Square bracket -> parenthesis
            ']': ')',        # Square bracket -> parenthesis
            '{': '(',        # Curly brace -> parenthesis
            '}': ')',        # Curly brace -> parenthesis
            '&': 'and',      # Ampersand -> 'and'
            '%': 'pct',      # Percent -> 'pct'
            '#': 'num',      # Hash -> 'num'
            '@': 'at',       # At symbol -> 'at'
            '+': 'plus',     # Plus -> 'plus'
            '=': 'equals',   # Equals -> 'equals'
            '$': 'dollar',   # Dollar -> 'dollar'
            ';': ',',        # Semicolon -> comma
        }

        # Apply replacements
        sanitized = filename
        for char, replacement in replacements.items():
            sanitized = sanitized.replace(char, replacement)

        # Remove any remaining non-alphanumeric characters except spaces, dashes, underscores, and dots
        sanitized = re.sub(r'[^\w\s\-_.]', '', sanitized)

        # Replace multiple spaces/dashes/underscores with single underscore
        sanitized = re.sub(r'[\s\-_]+', '_', sanitized)

        # Remove leading/trailing underscores
        sanitized = sanitized.strip('_')

        # Ensure the filename isn't too long (max 100 chars for directory names)
        if len(sanitized) > 100:
            sanitized = sanitized[:100].rstrip('_')

        # Ensure we have a valid filename
        if not sanitized:
            sanitized = "untitled_article"

        # Convert to lowercase for consistency
        sanitized = sanitized.lower()

        return sanitized

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

        logger.info(f"🎬 Starting pipeline for story: {story_title}")
        logger.info(f"📁 Story ID: {story_id}")
        logger.info(f"📰 Story Type: {story_type}")

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
