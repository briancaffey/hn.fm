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
        self.cache_dir = Path(cache_dir or config_manager.get("pipeline.cache.directory", "cache"))
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
                self._services[service_name] = ContentScraper(api_key=None, base_url=base_url)
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
            else:
                raise ValueError(f"Unknown service: {service_name}")

        return self._services[service_name]

    def _define_pipeline_steps(self) -> Dict[str, PipelineStep]:
        """Define the pipeline steps and their dependencies."""
        return {
            "hn_scraping": PipelineStep(
                name="hn_scraping",
                description="Scrape Hacker News articles",
                dependencies=[],
                cache_key="hn_articles",
                output_files=["hn_articles.json"]
            ),
            "firecrawl_content": PipelineStep(
                name="firecrawl_content",
                description="Extract content using Firecrawl",
                dependencies=["hn_scraping"],
                cache_key="firecrawl_content",
                output_files=["raw_content.md", "processed_content.json"]
            ),
            "content_processing": PipelineStep(
                name="content_processing",
                description="Process and clean content",
                dependencies=["firecrawl_content"],
                cache_key="processed_content",
                output_files=["cleaned_content.md", "meaningful_paragraphs.json"]
            ),
            "script_generation": PipelineStep(
                name="script_generation",
                description="Generate podcast script",
                dependencies=["content_processing"],
                cache_key="script",
                output_files=["script.txt", "tts_lines.txt", "script_meta.json"]
            ),
            "tts_generation": PipelineStep(
                name="tts_generation",
                description="Generate TTS audio",
                dependencies=["script_generation"],
                cache_key="tts_audio",
                output_files=["batch_*.wav"]
            ),
            "audio_cleaning": PipelineStep(
                name="audio_cleaning",
                description="Clean audio using Studio Voice",
                dependencies=["tts_generation"],
                cache_key="cleaned_audio",
                output_files=["cleaned_batch_*.wav"]
            ),
            "audio_assembly": PipelineStep(
                name="audio_assembly",
                description="Assemble final audio",
                dependencies=["audio_cleaning"],
                cache_key="final_audio",
                output_files=["final_audio.wav"]
            )
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
        max_age = timedelta(hours=config_manager.get("pipeline.cache.expiration_hours", 24))

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
            with open(cache_path, 'r') as f:
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
            with open(cache_path, 'w') as f:
                json.dump(data, f, indent=2)
            logger.info(f"Saved to cache: {cache_key}")
        except Exception as e:
            logger.error(f"Failed to save to cache {cache_key}: {e}")

    def _execute_step(self, step_name: str, inputs: Dict[str, Any],
                     start_from_step: Optional[str] = None) -> Dict[str, Any]:
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
        if start_from_step and step_name in config_manager.get("pipeline.skippable_steps", []):
            # Check cache
            cache_key = self._generate_cache_key(step_name, inputs)
            if self._is_cache_valid(cache_key):
                cached_data = self._load_from_cache(cache_key)
                if cached_data:
                    step.completed = True
                    logger.info(f"Skipping {step_name} (using cached data)")
                    return cached_data

        # Mark step as started
        step.start_time = datetime.now()
        step.completed = False
        step.error = None

        logger.info(f"🚀 Executing step: {step_name}")

        try:
            # Execute the step
            if step_name == "hn_scraping":
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

            logger.info(f"✅ Completed step: {step_name}")
            return output

        except Exception as e:
            step.error = str(e)
            step.end_time = datetime.now()
            logger.error(f"❌ Failed step {step_name}: {e}")
            raise

    def _execute_hn_scraping(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Execute Hacker News scraping step."""
        try:
            hn_scraper = self._get_service("hn_scraper")
            logger.info("📰 Fetching Hacker News front page...")

            # Get front page articles
            articles = hn_scraper.get_front_page_articles()

            if not articles:
                raise RuntimeError("No articles found on HN front page")

            # Select a random article (avoiding stickied posts and requiring URLs)
            import random
            valid_articles = [a for a in articles if not a.get('sticky', False) and a.get('url')]
            if not valid_articles:
                # Fallback to any article with a URL
                valid_articles = [a for a in articles if a.get('url')]

            if not valid_articles:
                raise RuntimeError("No articles with URLs found on HN front page")

            selected_article = random.choice(valid_articles)

            logger.info(f"🎯 Selected article: {selected_article.get('title', 'Unknown')}")
            logger.info(f"🔗 URL: {selected_article.get('url', 'Unknown')}")
            logger.info(f"📊 Score: {selected_article.get('score', 'Unknown')}")

            return {
                "articles": articles,
                "selected_article": selected_article,
                "article_count": len(articles)
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

            if not url:
                raise RuntimeError("No URL found in selected article")

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
            with open(raw_content_path, 'w', encoding='utf-8') as f:
                f.write(extracted_content.get("content", ""))

            # Save processed content data
            processed_content_path = content_dir / "processed_content.json"
            with open(processed_content_path, 'w', encoding='utf-8') as f:
                json.dump(extracted_content, f, indent=2, ensure_ascii=False)

            logger.info(f"✅ Content extracted successfully")
            logger.info(f"📝 Content length: {len(extracted_content.get('content', ''))} characters")
            logger.info(f"📁 Saved to: {content_dir}")

            return {
                "raw_content": extracted_content.get("content", ""),
                "title": title,
                "url": url,
                "story_dir": str(story_dir),
                "content_dir": str(content_dir),
                "raw_content_path": str(raw_content_path),
                "processed_content_path": str(processed_content_path)
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

            logger.info("🧹 Processing and cleaning content...")

            # Use the existing content processor
            content_processor = self._get_service("content_processor")

            # Clean the markdown content
            cleaned_content = content_processor._clean_markdown(raw_content)

            # Extract meaningful paragraphs
            meaningful_paragraphs = content_processor.extract_meaningful_paragraphs(cleaned_content)

            # Save cleaned content to markdown file
            cleaned_content_path = Path(content_dir) / "cleaned_content.md"
            with open(cleaned_content_path, 'w', encoding='utf-8') as f:
                f.write(cleaned_content)

            # Save meaningful paragraphs to JSON file
            meaningful_paragraphs_path = Path(content_dir) / "meaningful_paragraphs.json"
            with open(meaningful_paragraphs_path, 'w', encoding='utf-8') as f:
                json.dump({
                    "paragraphs": meaningful_paragraphs,
                    "count": len(meaningful_paragraphs),
                    "processed_at": datetime.now().isoformat()
                }, f, indent=2, ensure_ascii=False)

            logger.info(f"✅ Content processed successfully")
            logger.info(f"📝 Cleaned content length: {len(cleaned_content)} characters")
            logger.info(f"📄 Meaningful paragraphs: {len(meaningful_paragraphs)}")
            logger.info(f"📁 Saved to: {content_dir}")

            return {
                "cleaned_content": cleaned_content,
                "meaningful_paragraphs": meaningful_paragraphs,
                "cleaned_content_path": str(cleaned_content_path),
                "meaningful_paragraphs_path": str(meaningful_paragraphs_path)
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
            with open(script_path, 'w', encoding='utf-8') as f:
                f.write(script_data.get("script", ""))

            # Save TTS lines to text file
            tts_lines_path = Path(content_dir) / "tts_lines.txt"
            with open(tts_lines_path, 'w', encoding='utf-8') as f:
                for line in script_data.get("tts_lines", []):
                    f.write(line + '\n')

            # Save script metadata to JSON file
            script_meta_path = Path(content_dir) / "script_meta.json"
            with open(script_meta_path, 'w', encoding='utf-8') as f:
                json.dump({
                    "title": title,
                    "script_length": len(script_data.get("script", "")),
                    "tts_lines_count": len(script_data.get("tts_lines", [])),
                    "generated_at": datetime.now().isoformat()
                }, f, indent=2, ensure_ascii=False)

            logger.info(f"✅ Script generated successfully")
            logger.info(f"📝 Script length: {len(script_data.get('script', ''))} characters")
            logger.info(f"🎙️ TTS lines: {len(script_data.get('tts_lines', []))}")
            logger.info(f"📁 Saved to: {content_dir}")

            return {
                "script": script_data.get("script", ""),
                "tts_lines": script_data.get("tts_lines", []),
                "script_path": str(script_path),
                "tts_lines_path": str(tts_lines_path),
                "script_meta_path": str(script_meta_path)
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

            logger.info("🎵 Generating TTS audio...")

            # Create audio directory
            audio_dir = Path(story_dir) / "audio"
            audio_dir.mkdir(exist_ok=True)

            # Create a temporary TTS lines file
            import tempfile
            import os

            with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
                for line in tts_lines:
                    f.write(line + '\n')
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
                    for cleaned_batch_file in story_output_dir.glob("audio/cleaned_batch_*.wav"):
                        cleaned_batch_files.append(str(cleaned_batch_file))

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
                    "audio_dir": str(audio_dir)
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
            total_size = sum(os.path.getsize(f) for f in cleaned_audio_files if os.path.exists(f))
            total_size_mb = total_size / (1024 * 1024)

            logger.info(f"✅ Audio cleaning validation completed")
            logger.info(f"📁 Cleaned files: {len(cleaned_audio_files)}")
            logger.info(f"💾 Total size: {total_size_mb:.2f} MB")

            return {
                "cleaned_files": cleaned_audio_files,
                "enhancement_stats": {
                    "processed_chunks": batch_count,
                    "total_files": len(cleaned_audio_files),
                    "total_size_mb": total_size_mb
                }
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

            logger.info("🎵 Validating final audio assembly...")

            # Get file metadata
            file_size = os.path.getsize(final_audio)
            file_size_mb = file_size / (1024 * 1024)

            # TODO: Calculate actual duration using audio processing library
            # For now, estimate based on file size (rough approximation)
            estimated_duration = file_size_mb * 0.5  # Rough estimate: 0.5 MB per minute

            logger.info(f"✅ Audio assembly validation completed")
            logger.info(f"🎵 Final audio: {final_audio}")
            logger.info(f"💾 File size: {file_size_mb:.2f} MB")
            logger.info(f"⏱️ Estimated duration: {estimated_duration:.1f} minutes")

            return {
                "final_audio": final_audio,
                "total_duration": estimated_duration,
                "file_size_mb": file_size_mb,
                "status": "completed"
            }

        except Exception as e:
            logger.error(f"Failed to validate audio assembly: {e}")
            raise RuntimeError(f"Audio assembly validation failed: {e}")

    def _create_story_directory(self, story_title: str) -> Path:
        """Create a directory for a story, ensuring it's unique."""
        base_dir = Path("outputs")
        base_dir.mkdir(exist_ok=True)

        # Generate a unique name for the story directory
        # Clean the title to only allow letters and underscores
        safe_title = "".join(c.lower() for c in story_title if c.isalpha() or c == ' ').rstrip()
        safe_title = safe_title.replace(' ', '_')

        # Remove any consecutive underscores and leading/trailing underscores
        safe_title = '_'.join(filter(None, safe_title.split('_')))

        # Add timestamp-based hex suffix for uniqueness
        import time
        timestamp_hex = hex(int(time.time()))[2:8]  # 6-character hex from timestamp

        final_title = f"{safe_title}_{timestamp_hex}"

        story_dir = base_dir / final_title
        story_dir.mkdir(exist_ok=True)

        return story_dir

    def run_pipeline(self, story_id: str, story_title: str,
                    start_from_step: Optional[str] = None,
                    inputs: Optional[Dict[str, Any]] = None) -> PipelineState:
        """Run the complete pipeline.

        Args:
            story_id: Unique identifier for the story
            story_title: Title of the story
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
            updated_at=datetime.now()
        )

        logger.info(f"🎬 Starting pipeline for story: {story_title}")
        logger.info(f"📁 Story ID: {story_id}")

        if start_from_step:
            logger.info(f"🔄 Resuming from step: {start_from_step}")

        # Execute steps in order
        current_inputs = inputs or {}

        for step_name in self.pipeline_steps:
            # Skip steps before start_from_step
            if start_from_step and step_name != start_from_step:
                if step_name not in [start_from_step] + self.pipeline_steps[start_from_step].dependencies:
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
