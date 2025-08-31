"""Enhanced Celery tasks with Redis-first design and service locking"""

import logging
import uuid
from datetime import datetime
from typing import Dict, Any, Optional
from pathlib import Path

from .celery_app import celery_app
from .locks import ServiceLockManager
from .redis_repo import RedisRepository
from .models import VersionedSegment, ProcessingManifest

logger = logging.getLogger(__name__)


def execute_pipeline_step(
    step_name: str, manifest: ProcessingManifest, segment: VersionedSegment
) -> Dict[str, Any]:
    """
    Execute a single pipeline step using the existing pipeline manager

    Args:
        step_name: Name of the pipeline step to execute
        manifest: Processing manifest for the content
        segment: Versioned segment for this step

    Returns:
        Dictionary with step results including artifacts and metadata
    """
    try:
        # Import enhanced pipeline manager
        from ..pipeline.enhanced_pipeline_manager import EnhancedPipelineManager

        # Initialize enhanced pipeline manager in appropriate mode
        text_only = step_name not in [
            "tts_generation",
            "image_generation",
            "video_generation",
        ]
        pipeline = EnhancedPipelineManager(text_only=text_only, redis_integration=True)

        # Get content data from database
        content_id = manifest.content_id
        from .database import ContentDatabase

        db = ContentDatabase()
        content_data = db.get_content(content_id)

        if not content_data:
            raise RuntimeError(f"Content data not found for {content_id}")

        # Execute the specific step using enhanced pipeline manager
        if step_name == "firecrawl_content":
            logger.info(f"🔍 Starting firecrawl_content step for {content_id}")
            logger.info(f"🔍 Content data URL: {content_data.get('url', 'NO_URL')}")
            logger.info(
                f"🔍 Content data title: {content_data.get('title', 'NO_TITLE')}"
            )

            result = pipeline.execute_step_with_locking(
                step_name,
                {
                    "selected_article": {
                        "url": content_data.get("url", ""),
                        "title": content_data.get("title", "Unknown Title"),
                        "id": content_id,
                    }
                },
            )

            logger.info(f"🔍 Firecrawl result keys: {list(result.keys())}")
            logger.info(f"🔍 Raw content length: {len(result.get('raw_content', ''))}")
            logger.info(f"🔍 Content dir: {result.get('content_dir', 'NO_DIR')}")

            # Extract artifacts
            artifacts = {}
            if "raw_content" in result:
                artifacts["raw_content"] = result["raw_content"]
                logger.info(
                    f"🔍 Added raw_content to artifacts, length: {len(result['raw_content'])}"
                )
            if "content_dir" in result:
                artifacts["content_dir"] = result["content_dir"]
                logger.info(
                    f"🔍 Added content_dir to artifacts: {result['content_dir']}"
                )
            if "processed_content" in result:
                artifacts["processed_content"] = result["processed_content"]
                logger.info(f"🔍 Added processed_content to artifacts")

            logger.info(f"🔍 Final artifacts keys: {list(artifacts.keys())}")

            return {
                "artifacts": artifacts,
                "metadata": {
                    "content_length": len(result.get("raw_content", "")),
                    "extraction_method": "firecrawl",
                    "step_version": segment.version,
                },
            }

        elif step_name == "content_processing":
            # Get raw content from previous step - try multiple sources
            raw_content = ""

            logger.info(f"🔍 Starting content_processing step for {content_id}")
            logger.info(
                f"🔍 Manifest segments available: {list(manifest.segments.keys())}"
            )

            # Try to get from manifest segments first
            firecrawl_segment = manifest.segments.get("firecrawl_content")
            logger.info(f"🔍 Firecrawl segment found: {firecrawl_segment is not None}")

            if firecrawl_segment:
                logger.info(f"🔍 Firecrawl segment type: {type(firecrawl_segment)}")
                logger.info(
                    f"🔍 Firecrawl segment has artifacts: {hasattr(firecrawl_segment, 'artifacts')}"
                )
                if hasattr(firecrawl_segment, "artifacts"):
                    logger.info(
                        f"🔍 Firecrawl artifacts keys: {list(firecrawl_segment.artifacts.keys())}"
                    )
                    raw_content = firecrawl_segment.artifacts.get("raw_content", "")
                    logger.info(
                        f"🔍 Raw content length from artifacts: {len(raw_content)}"
                    )
                else:
                    logger.warning(
                        "🔍 Firecrawl segment does not have artifacts attribute"
                    )
            else:
                logger.warning("🔍 No firecrawl_segment found in manifest")

            # If not found in manifest, try to get from the previous step's result
            if not raw_content:
                logger.warning(
                    "🔍 Raw content not found in manifest, attempting to get from previous step"
                )
                # We can't easily get the previous step's result here, so we'll need to handle this differently

            # For now, let's try to get the content from the database or regenerate it
            if not raw_content:
                logger.info("🔍 Attempting to re-extract content from URL")
                # Try to get the URL and re-extract content
                content_data = db.get_content(content_id)
                logger.info(f"🔍 Content data found: {content_data is not None}")
                if content_data:
                    logger.info(f"🔍 Content data keys: {list(content_data.keys())}")
                    logger.info(f"🔍 Content URL: {content_data.get('url', 'NO_URL')}")

                if content_data and content_data.get("url"):
                    logger.info(
                        "🔍 Re-extracting content from URL for content_processing step"
                    )
                    try:
                        firecrawl_result = pipeline.execute_step_with_locking(
                            "firecrawl_content",
                            {
                                "selected_article": {
                                    "url": content_data.get("url", ""),
                                    "title": content_data.get("title", "Unknown Title"),
                                    "id": content_id,
                                }
                            },
                        )
                        logger.info(
                            f"🔍 Firecrawl result keys: {list(firecrawl_result.keys())}"
                        )
                        raw_content = firecrawl_result.get("raw_content", "")
                        logger.info(
                            f"🔍 Raw content length from re-extraction: {len(raw_content)}"
                        )
                    except Exception as e:
                        logger.error(f"🔍 Error during re-extraction: {e}")
                        raise
                else:
                    logger.error("🔍 No URL found in content data")

            if not raw_content:
                logger.error("🔍 No raw content available for content processing")
                logger.error(f"🔍 Content ID: {content_id}")
                logger.error(f"🔍 Manifest segments: {list(manifest.segments.keys())}")
                if "firecrawl_content" in manifest.segments:
                    firecrawl_seg = manifest.segments["firecrawl_content"]
                    logger.error(
                        f"🔍 Firecrawl segment status: {getattr(firecrawl_seg, 'status', 'NO_STATUS')}"
                    )
                    logger.error(
                        f"🔍 Firecrawl segment artifacts: {getattr(firecrawl_seg, 'artifacts', 'NO_ARTIFACTS')}"
                    )
                raise RuntimeError("No raw content available for content processing")

            # Get content directory from the firecrawl step or create one
            content_dir = ""
            firecrawl_segment = manifest.segments.get("firecrawl_content")
            if firecrawl_segment and hasattr(firecrawl_segment, "artifacts"):
                content_dir = firecrawl_segment.artifacts.get("content_dir", "")

            # If no content_dir from manifest, create one
            if not content_dir:
                content_data = db.get_content(content_id)
                if content_data:
                    # Create a content directory based on the content ID
                    from pathlib import Path

                    content_dir = str(Path("cache") / content_id / "content")
                    Path(content_dir).mkdir(parents=True, exist_ok=True)

            result = pipeline.execute_step_with_locking(
                step_name,
                {
                    "raw_content": raw_content,
                    "content_dir": content_dir,
                    "title": (
                        content_data.get("title", "Unknown Title")
                        if content_data
                        else "Unknown Title"
                    ),
                },
            )

            artifacts = {}
            if "cleaned_content" in result:
                artifacts["cleaned_content"] = result["cleaned_content"]
            if "meaningful_paragraphs" in result:
                artifacts["meaningful_paragraphs"] = result["meaningful_paragraphs"]

            return {
                "artifacts": artifacts,
                "metadata": {
                    "cleaned_length": len(result.get("cleaned_content", "")),
                    "paragraph_count": len(result.get("meaningful_paragraphs", [])),
                    "step_version": segment.version,
                },
            }

        elif step_name == "script_generation":
            # Get cleaned content from previous step - try multiple sources
            cleaned_content = ""

            # Try to get from manifest segments first
            content_processing_segment = manifest.segments.get("content_processing")
            if content_processing_segment and hasattr(
                content_processing_segment, "artifacts"
            ):
                cleaned_content = content_processing_segment.artifacts.get(
                    "cleaned_content", ""
                )

            # If not found in manifest, try to regenerate it
            if not cleaned_content:
                logger.warning(
                    "Cleaned content not found in manifest, attempting to regenerate"
                )
                # Get raw content and process it
                content_data = db.get_content(content_id)
                if content_data and content_data.get("url"):
                    # Re-extract and process content
                    firecrawl_result = pipeline.execute_step_with_locking(
                        "firecrawl_content",
                        {
                            "selected_article": {
                                "url": content_data.get("url", ""),
                                "title": content_data.get("title", "Unknown Title"),
                                "id": content_id,
                            }
                        },
                    )
                    raw_content = firecrawl_result.get("raw_content", "")

                    if raw_content:
                        # Process the raw content
                        processing_result = pipeline.execute_step_with_locking(
                            "content_processing",
                            {"raw_content": raw_content, "content_id": content_id},
                        )
                        cleaned_content = processing_result.get("cleaned_content", "")

            if not cleaned_content:
                raise RuntimeError("No cleaned content available for script generation")

            # Get content directory and other required parameters
            content_dir = ""
            meaningful_paragraphs = []
            title = "Unknown Title"

            # Try to get from manifest segments
            content_processing_segment = manifest.segments.get("content_processing")
            if content_processing_segment and hasattr(
                content_processing_segment, "artifacts"
            ):
                content_dir = content_processing_segment.artifacts.get(
                    "content_dir", ""
                )
                meaningful_paragraphs = content_processing_segment.artifacts.get(
                    "meaningful_paragraphs", []
                )
                title = content_processing_segment.artifacts.get(
                    "title", "Unknown Title"
                )

            # If not found in manifest, try to get from the fallback processing
            if not content_dir or not meaningful_paragraphs:
                content_data = db.get_content(content_id)
                if content_data:
                    title = content_data.get("title", "Unknown Title")
                    # Create content directory if needed
                    if not content_dir:
                        from pathlib import Path

                        content_dir = str(Path("cache") / content_id / "content")
                        Path(content_dir).mkdir(parents=True, exist_ok=True)

                    # If we don't have meaningful paragraphs, we need to process the content again
                    if not meaningful_paragraphs and cleaned_content:
                        # Extract meaningful paragraphs from cleaned content
                        content_processor = pipeline._get_service("content_processor")
                        meaningful_paragraphs = (
                            content_processor.extract_meaningful_paragraphs(
                                cleaned_content
                            )
                        )

            result = pipeline.execute_step_with_locking(
                step_name,
                {
                    "meaningful_paragraphs": meaningful_paragraphs,
                    "title": title,
                    "content_dir": content_dir,
                },
            )

            artifacts = {}
            if "script_path" in result:
                script_path = Path(result["script_path"])
                if script_path.exists():
                    with open(script_path, "r", encoding="utf-8") as f:
                        script_content = f.read()
                    artifacts["script_content"] = script_content
                    artifacts["script_path"] = str(script_path)

            return {
                "artifacts": artifacts,
                "metadata": {
                    "script_length": len(artifacts.get("script_content", "")),
                    "script_path": artifacts.get("script_path", ""),
                    "step_version": segment.version,
                },
            }

        elif step_name == "tts_generation":
            # Get script from previous step
            script_content = (
                manifest.segments.get("script_generation", {})
                .get("artifacts", {})
                .get("script_content", "")
            )

            if not script_content:
                raise RuntimeError("No script content available for TTS generation")

            # Execute TTS generation
            result = pipeline.execute_step_with_locking(
                step_name, {"script_content": script_content, "content_id": content_id}
            )

            artifacts = {}
            if "audio_path" in result:
                artifacts["audio_path"] = result["audio_path"]
            if "tts_lines" in result:
                artifacts["tts_lines"] = result["tts_lines"]

            return {
                "artifacts": artifacts,
                "metadata": {
                    "audio_path": artifacts.get("audio_path", ""),
                    "tts_lines_count": len(artifacts.get("tts_lines", [])),
                    "step_version": segment.version,
                },
            }

        elif step_name == "image_generation":
            # Get script from script generation step
            script_content = (
                manifest.segments.get("script_generation", {})
                .get("artifacts", {})
                .get("script_content", "")
            )

            if not script_content:
                raise RuntimeError("No script content available for image generation")

            # Execute image generation
            result = pipeline.execute_step_with_locking(
                step_name, {"script_content": script_content, "content_id": content_id}
            )

            artifacts = {}
            if "image_paths" in result:
                artifacts["image_paths"] = result["image_paths"]

            return {
                "artifacts": artifacts,
                "metadata": {
                    "image_count": len(artifacts.get("image_paths", [])),
                    "image_paths": artifacts.get("image_paths", []),
                    "step_version": segment.version,
                },
            }

        elif step_name == "video_generation":
            # Get audio and images from previous steps
            audio_path = (
                manifest.segments.get("tts_generation", {})
                .get("artifacts", {})
                .get("audio_path", "")
            )
            image_paths = (
                manifest.segments.get("image_generation", {})
                .get("artifacts", {})
                .get("image_paths", [])
            )

            if not audio_path:
                raise RuntimeError("No audio available for video generation")

            # Execute video generation
            result = pipeline.execute_step_with_locking(
                step_name,
                {
                    "audio_path": audio_path,
                    "image_paths": image_paths,
                    "content_id": content_id,
                },
            )

            artifacts = {}
            if "video_path" in result:
                artifacts["video_path"] = result["video_path"]

            return {
                "artifacts": artifacts,
                "metadata": {
                    "video_path": artifacts.get("video_path", ""),
                    "step_version": segment.version,
                },
            }

        else:
            raise ValueError(f"Unknown pipeline step: {step_name}")

    except Exception as e:
        logger.error(f"Error executing pipeline step {step_name}: {e}")
        raise


@celery_app.task(bind=True, name="enhanced_content_pipeline")
def enhanced_content_pipeline(self, content_id: str, options: Dict[str, Any] = None):
    """
    Enhanced content pipeline with Redis-first design and service locking

    Args:
        content_id: Content item identifier
        options: Processing options and configuration
    """
    task_id = self.request.id
    logger.info(
        f"Starting enhanced content pipeline for {content_id} (task: {task_id})"
    )

    redis_repo = RedisRepository()

    try:
        # Initialize or retrieve processing manifest
        manifest = redis_repo.get_or_create_manifest(content_id, options or {})
        logger.info(
            f"Using manifest for {content_id}: current_step={manifest.current_step}"
        )

        # Define pipeline steps with their service mappings
        steps = [
            ("firecrawl_content", "firecrawl"),
            ("content_processing", "llm"),
            ("script_generation", "llm"),
            ("tts_generation", "tts"),
            ("image_generation", "vision"),
            ("video_generation", "video"),
        ]

        # Execute pipeline steps with proper locking and versioning
        for step_name, service_name in steps:
            if step_name in manifest.completed_steps:
                logger.info(f"Skipping completed step: {step_name}")
                continue

            logger.info(f"Executing step: {step_name} (service: {service_name})")

            # Create new segment for this step
            segment = redis_repo.create_segment(content_id, step_name)
            logger.info(f"Created segment {segment.segment_id} for {step_name}")

            try:
                # Execute the pipeline step (enhanced pipeline manager handles its own locking)
                logger.info(f"🔍 Executing step {step_name} for {content_id}")
                result = execute_pipeline_step(step_name, manifest, segment)
                logger.info(f"🔍 Step {step_name} result keys: {list(result.keys())}")

                # Store the result in the segment artifacts
                segment.artifacts = result.get("artifacts", {})
                segment.metadata = result.get("metadata", {})
                logger.info(
                    f"🔍 Stored artifacts in segment: {list(segment.artifacts.keys())}"
                )

                # Mark segment as completed
                redis_repo.complete_segment(segment.segment_id, result)
                logger.info(f"Completed step {step_name} for {content_id}")

            except Exception as e:
                logger.error(f"Failed step {step_name} for {content_id}: {e}")
                redis_repo.fail_segment(segment.segment_id, str(e))
                raise

            finally:
                # Update manifest
                redis_repo.update_manifest(manifest)
                logger.info(f"🔍 Updated manifest for {content_id}")

        # Update content status to completed
        redis_repo.db.update_content(
            content_id,
            {
                "status": "completed",
                "processing_steps": manifest.completed_steps,
                "updated_at": datetime.now(),
            },
        )

        logger.info(f"Enhanced content pipeline completed for {content_id}")

        return {
            "task_id": task_id,
            "content_id": content_id,
            "status": "completed",
            "completed_steps": manifest.completed_steps,
            "timestamp": datetime.now().isoformat(),
        }

    except Exception as e:
        logger.error(f"Enhanced content pipeline failed for {content_id}: {e}")

        # Mark content as failed
        redis_repo.mark_content_failed(content_id, str(e))

        # Re-raise to mark task as failed
        raise


@celery_app.task(bind=True, name="retry_failed_segment")
def retry_failed_segment(self, segment_id: str):
    """
    Retry a failed pipeline segment

    Args:
        segment_id: ID of the failed segment to retry
    """
    task_id = self.request.id
    logger.info(f"Retrying failed segment {segment_id} (task: {task_id})")

    redis_repo = RedisRepository()

    try:
        # Retry the segment
        new_segment = redis_repo.retry_segment(segment_id)

        if not new_segment:
            raise RuntimeError(f"Failed to retry segment {segment_id}")

        logger.info(
            f"Successfully retried segment {segment_id} as {new_segment.segment_id}"
        )

        return {
            "task_id": task_id,
            "original_segment_id": segment_id,
            "new_segment_id": new_segment.segment_id,
            "status": "retry_initiated",
            "timestamp": datetime.now().isoformat(),
        }

    except Exception as e:
        logger.error(f"Failed to retry segment {segment_id}: {e}")
        raise


@celery_app.task(bind=True, name="get_enhanced_pipeline_status")
def get_enhanced_pipeline_status(self, content_id: str):
    """
    Get enhanced pipeline status for a content item

    Args:
        content_id: Content item identifier
    """
    task_id = self.request.id
    logger.info(f"Getting enhanced pipeline status for {content_id} (task: {task_id})")

    redis_repo = RedisRepository()

    try:
        # Get enhanced pipeline status
        status = redis_repo.get_enhanced_pipeline_status(content_id)

        if not status:
            raise RuntimeError(f"Could not retrieve pipeline status for {content_id}")

        return {
            "task_id": task_id,
            "content_id": content_id,
            "status": "success",
            "pipeline_status": status.dict(),
            "timestamp": datetime.now().isoformat(),
        }

    except Exception as e:
        logger.error(f"Failed to get pipeline status for {content_id}: {e}")
        raise


@celery_app.task(bind=True, name="cleanup_completed_segments")
def cleanup_completed_segments(self, content_id: str, keep_versions: int = 2):
    """
    Clean up old completed segments, keeping only the specified number of versions

    Args:
        content_id: Content item identifier
        keep_versions: Number of versions to keep for each step
    """
    task_id = self.request.id
    logger.info(f"Cleaning up completed segments for {content_id} (task: {task_id})")

    redis_repo = RedisRepository()

    try:
        # Get manifest
        manifest = redis_repo.get_or_create_manifest(content_id)

        cleaned_count = 0
        for step_name, segment in manifest.segments.items():
            if segment.status == "completed" and segment.version > keep_versions:
                # Remove old segment
                segment_key = f"hnfm:segments:{content_id}:{step_name}"
                redis_repo.redis_client.delete(segment_key)
                cleaned_count += 1
                logger.info(f"Cleaned up old segment {segment.segment_id}")

        logger.info(f"Cleaned up {cleaned_count} old segments for {content_id}")

        return {
            "task_id": task_id,
            "content_id": content_id,
            "status": "completed",
            "cleaned_segments": cleaned_count,
            "timestamp": datetime.now().isoformat(),
        }

    except Exception as e:
        logger.error(f"Failed to cleanup segments for {content_id}: {e}")
        raise
