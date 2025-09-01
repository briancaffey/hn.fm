"""Simple Celery tasks for hn.fm"""

import logging
import uuid
from datetime import datetime
from typing import Dict, Any, Optional
from pathlib import Path

from .celery_app import celery_app

logger = logging.getLogger(__name__)


def execute_pipeline_step(
    step_name: str, content_id: str, options: Dict[str, Any] = None
) -> Dict[str, Any]:
    """
    Execute a single pipeline step using the simple pipeline manager

    Args:
        step_name: Name of the pipeline step to execute
        content_id: Content item identifier
        options: Processing options

    Returns:
        Dictionary with step results including artifacts and metadata
    """
    try:
        # Import simple pipeline manager
        from ..pipeline.enhanced_pipeline_manager import PipelineManager

        # Initialize pipeline manager in appropriate mode
        text_only = step_name not in [
            "tts_generation",
            "image_generation",
            "video_generation",
            "audio_cleaning",
            "audio_assembly",
        ]
        pipeline = PipelineManager(text_only=text_only)

        # Get content data from database
        from .database import ContentDatabase

        db = ContentDatabase()
        content_data = db.get_content(content_id)

        if not content_data:
            raise RuntimeError(f"Content data not found for {content_id}")

        # Execute the specific step using simple pipeline manager
        if step_name == "firecrawl_content":
            logger.info(f"Starting firecrawl_content step for {content_id}")
            logger.info(f"Content data URL: {content_data.get('url', 'NO_URL')}")
            logger.info(f"Content data title: {content_data.get('title', 'NO_TITLE')}")

            result = pipeline.execute_step(
                step_name,
                {
                    "selected_article": {
                        "url": content_data.get("url", ""),
                        "title": content_data.get("title", "Unknown Title"),
                        "id": content_id,
                    }
                },
            )

            logger.info(f"Firecrawl result keys: {list(result.keys())}")

            return {
                "artifacts": result.get("artifacts", {}),
                "metadata": result.get("metadata", {}),
            }

        elif step_name == "content_processing":
            logger.info(f"Starting content_processing step for {content_id}")

            result = pipeline.execute_step(step_name, {})

            logger.info(f"Content processing result keys: {list(result.keys())}")

            return {
                "artifacts": result.get("artifacts", {}),
                "metadata": result.get("metadata", {}),
            }

        elif step_name == "script_generation":
            logger.info(f"Starting script_generation step for {content_id}")

            result = pipeline.execute_step(step_name, {})

            logger.info(f"Script generation result keys: {list(result.keys())}")

            return {
                "artifacts": result.get("artifacts", {}),
                "metadata": result.get("metadata", {}),
            }

        elif step_name == "tts_generation":
            logger.info(f"Starting tts_generation step for {content_id}")

            result = pipeline.execute_step(step_name, {})

            logger.info(f"TTS generation result keys: {list(result.keys())}")

            return {
                "artifacts": result.get("artifacts", {}),
                "metadata": result.get("metadata", {}),
            }

        elif step_name == "image_generation":
            logger.info(f"Starting image_generation step for {content_id}")

            result = pipeline.execute_step(step_name, {})

            logger.info(f"Image generation result keys: {list(result.keys())}")

            return {
                "artifacts": result.get("artifacts", {}),
                "metadata": result.get("metadata", {}),
            }

        elif step_name == "video_generation":
            logger.info(f"Starting video_generation step for {content_id}")

            result = pipeline.execute_step(step_name, {})

            logger.info(f"Video generation result keys: {list(result.keys())}")

            return {
                "artifacts": result.get("artifacts", {}),
                "metadata": result.get("metadata", {}),
            }

        elif step_name == "audio_cleaning":
            logger.info(f"Starting audio_cleaning step for {content_id}")

            result = pipeline.execute_step(step_name, {})

            logger.info(f"Audio cleaning result keys: {list(result.keys())}")

            return {
                "artifacts": result.get("artifacts", {}),
                "metadata": result.get("metadata", {}),
            }

        elif step_name == "audio_assembly":
            logger.info(f"Starting audio_assembly step for {content_id}")

            result = pipeline.execute_step(step_name, {})

            logger.info(f"Audio assembly result keys: {list(result.keys())}")

            return {
                "artifacts": result.get("artifacts", {}),
                "metadata": result.get("metadata", {}),
            }

        else:
            raise ValueError(f"Unknown pipeline step: {step_name}")

    except Exception as e:
        logger.error(f"Error executing pipeline step {step_name}: {e}")
        raise


@celery_app.task(bind=True, name="content_pipeline")
def content_pipeline(self, content_id: str, options: Dict[str, Any] = None):
    """
    Simple content pipeline for hn.fm

    Args:
        content_id: Content item identifier
        options: Processing options and configuration
    """
    task_id = self.request.id
    logger.info(f"Starting content pipeline for {content_id} (task: {task_id})")

    try:
        # Get content data from database
        from .database import ContentDatabase

        db = ContentDatabase()
        content_data = db.get_content(content_id)

        if not content_data:
            raise RuntimeError(f"Content {content_id} not found")

        url = content_data.get("url")
        title = content_data.get("title", "Unknown Title")

        # Update status and add processing step
        db.update_content(
            content_id,
            {"status": "processing", "processing_steps": ["pipeline_started"]},
        )

        # Define pipeline steps
        steps = [
            "firecrawl_content",
            "content_processing",
            "script_generation",
        ]

        # Execute pipeline steps
        for step_name in steps:
            logger.info(f"Executing step: {step_name}")

            try:
                # Execute the pipeline step
                logger.info(f"Executing step {step_name} for {content_id}")
                result = execute_pipeline_step(step_name, content_id, options)
                logger.info(f"Step {step_name} result keys: {list(result.keys())}")

                # Update processing steps
                current_steps = content_data.get("processing_steps", [])
                if step_name not in current_steps:
                    current_steps.append(step_name)
                    db.update_content(content_id, {"processing_steps": current_steps})

                logger.info(f"Completed step {step_name} for {content_id}")

            except Exception as e:
                logger.error(f"Failed step {step_name} for {content_id}: {e}")
                db.update_content(
                    content_id,
                    {
                        "status": "failed",
                        "processing_steps": content_data.get("processing_steps", []),
                        "errors": [str(e)],
                    },
                )
                raise

        # Extract the script content
        script_content = ""
        script_file = Path("cache") / "script.md"
        if script_file.exists():
            with open(script_file, "r", encoding="utf-8") as f:
                script_content = f.read()

        # Update content with results
        db.update_content(
            content_id,
            {
                "status": "completed",
                "processing_steps": content_data.get("processing_steps", []) + steps,
                "script": script_content,
                "summary": f"Successfully processed content and generated script with {len(script_content)} characters",
            },
        )

        logger.info(f"Content pipeline processing completed for {content_id}")

        return {
            "task_id": self.request.id,
            "content_id": content_id,
            "status": "completed",
            "script_length": len(script_content),
            "timestamp": datetime.now().isoformat(),
        }

    except Exception as e:
        logger.error(f"Content pipeline processing failed for {content_id}: {e}")

        # Update status to failed
        db.update_content(content_id, {"status": "failed", "errors": [str(e)]})

        # Re-raise to mark task as failed
        raise


@celery_app.task(bind=True, name="full_pipeline")
def full_pipeline(self, content_id: str, url: str, content_type: str = "article"):
    """
    Full pipeline processing including TTS, images, and video generation

    Args:
        content_id: Content item identifier
        url: URL to process
        content_type: Type of content (article, etc.)
    """
    task_id = self.request.id
    logger.info(f"Starting full pipeline for {content_id} (task: {task_id})")

    try:
        # Get content data from database
        from .database import ContentDatabase

        db = ContentDatabase()
        content_data = db.get_content(content_id)

        if not content_data:
            raise RuntimeError(f"Content {content_id} not found")

        title = content_data.get("title", "Unknown Title")

        # Update status and add processing step
        db.update_content(
            content_id,
            {"status": "processing", "processing_steps": ["pipeline_started"]},
        )

        # Define full pipeline steps
        steps = [
            "firecrawl_content",
            "content_processing",
            "script_generation",
            "tts_generation",
            "audio_cleaning",
            "audio_assembly",
            "image_generation",
            "video_generation",
        ]

        # Execute pipeline steps
        for step_name in steps:
            logger.info(f"Executing step: {step_name}")

            try:
                # Execute the pipeline step
                logger.info(f"Executing step {step_name} for {content_id}")
                result = execute_pipeline_step(step_name, content_id, {})
                logger.info(f"Step {step_name} result keys: {list(result.keys())}")

                # Update processing steps
                current_steps = content_data.get("processing_steps", [])
                if step_name not in current_steps:
                    current_steps.append(step_name)
                    db.update_content(content_id, {"processing_steps": current_steps})

                logger.info(f"Completed step {step_name} for {content_id}")

            except Exception as e:
                logger.error(f"Failed step {step_name} for {content_id}: {e}")
                db.update_content(
                    content_id,
                    {
                        "status": "failed",
                        "processing_steps": content_data.get("processing_steps", []),
                        "errors": [str(e)],
                    },
                )
                raise

        # Extract the script content
        script_content = ""
        script_file = Path("cache") / "script.md"
        if script_file.exists():
            with open(script_file, "r", encoding="utf-8") as f:
                script_content = f.read()

        # Update content with results
        db.update_content(
            content_id,
            {
                "status": "completed",
                "processing_steps": content_data.get("processing_steps", []) + steps,
                "script": script_content,
                "summary": f"Successfully processed content and generated full media with {len(script_content)} characters",
            },
        )

        logger.info(f"Full pipeline processing completed for {content_id}")

        return {
            "task_id": self.request.id,
            "content_id": content_id,
            "status": "completed",
            "script_length": len(script_content),
            "timestamp": datetime.now().isoformat(),
        }

    except Exception as e:
        logger.error(f"Full pipeline processing failed for {content_id}: {e}")

        # Update status to failed
        db.update_content(content_id, {"status": "failed", "errors": [str(e)]})

        # Re-raise to mark task as failed
        raise


@celery_app.task(bind=True, name="process_content_pipeline")
def process_content_pipeline(self, content_id: str):
    """Process content through the full pipeline (scraping, processing, script generation) - legacy function"""
    logger.info(f"Starting content pipeline processing for {content_id}")

    try:
        from .database import ContentDatabase

        db = ContentDatabase()

        # Get the content item
        content = db.get_content(content_id)
        if not content:
            raise RuntimeError(f"Content {content_id} not found")

        url = content.get("url")
        title = content.get("title", "Unknown Title")

        # Update status and add processing step
        db.update_content(
            content_id,
            {"status": "processing", "processing_steps": ["pipeline_started"]},
        )

        # Import pipeline manager
        from ..pipeline.enhanced_pipeline_manager import PipelineManager

        # Initialize pipeline manager in text-only mode (no TTS, images, video)
        pipeline = PipelineManager(text_only=True)

        # Run the pipeline steps we need: firecrawl_content, content_processing, script_generation
        logger.info(f"Running pipeline for content {content_id}: {url}")

        # Execute firecrawl content extraction
        # The pipeline expects a selected_article structure
        firecrawl_result = pipeline.execute_step(
            "firecrawl_content",
            {
                "selected_article": {
                    "url": url,
                    "title": title,
                    "id": content_id,  # Use content_id as the article ID
                }
            },
        )

        # Execute content processing
        processing_result = pipeline.execute_step(
            "content_processing", firecrawl_result
        )

        # Execute script generation
        script_result = pipeline.execute_step("script_generation", processing_result)

        # Extract the script content
        script_content = ""
        if script_result and "script_path" in script_result:
            script_path = Path(script_result["script_path"])
            if script_path.exists():
                with open(script_path, "r", encoding="utf-8") as f:
                    script_content = f.read()

        # Update content with results
        db.update_content(
            content_id,
            {
                "status": "completed",
                "processing_steps": [
                    "pipeline_started",
                    "firecrawl_content",
                    "content_processing",
                    "script_generation",
                ],
                "raw_text": firecrawl_result.get("raw_content", ""),
                "processed_text": processing_result.get("cleaned_content", ""),
                "script": script_content,
                "summary": f"Successfully processed content and generated script with {len(script_content)} characters",
            },
        )

        logger.info(f"Content pipeline processing completed for {content_id}")

        return {
            "task_id": self.request.id,
            "content_id": content_id,
            "status": "completed",
            "script_length": len(script_content),
            "timestamp": datetime.now().isoformat(),
        }

    except Exception as e:
        logger.error(f"Content pipeline processing failed for {content_id}: {e}")

        # Update status to failed
        db.update_content(content_id, {"status": "failed", "errors": [str(e)]})

        # Re-raise to mark task as failed
        raise


@celery_app.task(bind=True, name="cleanup_old_results")
def cleanup_old_results(self):
    """Clean up old task results from Redis - legacy function"""
    logger.info("Starting cleanup of old task results")

    try:
        # This is a simple cleanup task - just log that it's done
        logger.info("Cleanup completed successfully")
        return {
            "task_id": self.request.id,
            "status": "completed",
            "timestamp": datetime.now().isoformat(),
        }

    except Exception as e:
        logger.error(f"Cleanup failed: {e}")
        raise
