"""Simple Celery tasks for hn.fm"""

import logging
import uuid
from datetime import datetime
from typing import Dict, Any, Optional
from pathlib import Path

from .celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, name="process_content")
def process_content(self, content_id: str, options: Dict[str, Any] = None):
    """
    Single task that processes content through the entire pipeline.

    This task handles everything from content scraping to final output generation.
    No complex abstractions, just simple step-by-step execution with good logging.

    Args:
        content_id: Content item identifier
        options: Processing options (optional)
    """
    task_id = self.request.id
    logger.info(f"Starting process_content task for {content_id} (task: {task_id})")

    try:
        # Get content data from database
        from .database import ContentDatabase

        db = ContentDatabase()
        content_data = db.get_content(content_id)

        if not content_data:
            raise RuntimeError(f"Content {content_id} not found")

        url = content_data.get("url")
        title = content_data.get("title", "Unknown Title")

        logger.info(f"Processing content: {title} ({url})")

        # Update status to processing
        db.update_content(
            content_id, {"status": "processing", "processing_steps": ["task_started"]}
        )

        # Import pipeline manager
        from ..pipeline.pipeline_manager import PipelineManager

        # Initialize pipeline manager
        pipeline = PipelineManager()

        # Define all pipeline steps in order
        steps = [
            "system_check",
            "hn_scraping",
            "firecrawl_content",
            "content_processing",
            "script_generation",
            "tts_generation",
            "audio_cleaning",
            "audio_assembly",
            "image_generation",
            "video_generation",
        ]

        # Execute each step
        for step_name in steps:
            logger.info(f"Executing step: {step_name}")

            try:
                # Update processing steps
                current_steps = content_data.get("processing_steps", [])
                if step_name not in current_steps:
                    current_steps.append(step_name)
                    db.update_content(content_id, {"processing_steps": current_steps})

                # Execute the step
                if step_name == "firecrawl_content":
                    logger.info(f"Starting firecrawl_content for {content_id}")
                    logger.info(f"URL: {url}")
                    logger.info(f"Title: {title}")

                    result = pipeline.execute_step(
                        step_name,
                        {
                            "selected_article": {
                                "url": url,
                                "title": title,
                                "id": content_id,
                            }
                        },
                    )

                    logger.info(
                        f"Firecrawl completed. Result keys: {list(result.keys())}"
                    )

                else:
                    logger.info(f"Starting {step_name} for {content_id}")
                    result = pipeline.execute_step(step_name, {})
                    logger.info(
                        f"{step_name} completed. Result keys: {list(result.keys())}"
                    )

                logger.info(f"Step {step_name} completed successfully")

            except Exception as e:
                logger.error(f"Step {step_name} failed: {e}")
                db.update_content(
                    content_id,
                    {
                        "status": "failed",
                        "processing_steps": content_data.get("processing_steps", []),
                        "errors": [f"Step {step_name} failed: {str(e)}"],
                    },
                )
                raise

        # Extract the script content
        script_content = ""
        script_file = Path("cache") / "script.md"
        if script_file.exists():
            with open(script_file, "r", encoding="utf-8") as f:
                script_content = f.read()
            logger.info(f"Script loaded: {len(script_content)} characters")

        # Update content with final results
        db.update_content(
            content_id,
            {
                "status": "completed",
                "processing_steps": content_data.get("processing_steps", []) + steps,
                "script": script_content,
                "summary": f"Successfully processed content and generated full media with {len(script_content)} characters",
            },
        )

        logger.info(f"process_content task completed successfully for {content_id}")

        return {
            "task_id": task_id,
            "content_id": content_id,
            "status": "completed",
            "script_length": len(script_content),
            "timestamp": datetime.now().isoformat(),
        }

    except Exception as e:
        logger.error(f"process_content task failed for {content_id}: {e}")

        # Update status to failed
        db.update_content(content_id, {"status": "failed", "errors": [str(e)]})

        # Re-raise to mark task as failed
        raise


@celery_app.task(bind=True, name="process_content_text_only")
def process_content_text_only(self, content_id: str, options: Dict[str, Any] = None):
    """
    Single task that processes content through text-only pipeline (no audio/video).

    This task handles content scraping, processing, and script generation only.
    No complex abstractions, just simple step-by-step execution with good logging.

    Args:
        content_id: Content item identifier
        options: Processing options (optional)
    """
    task_id = self.request.id
    logger.info(
        f"Starting process_content_text_only task for {content_id} (task: {task_id})"
    )

    try:
        # Get content data from database
        from .database import ContentDatabase

        db = ContentDatabase()
        content_data = db.get_content(content_id)

        if not content_data:
            raise RuntimeError(f"Content {content_id} not found")

        url = content_data.get("url")
        title = content_data.get("title", "Unknown Title")

        logger.info(f"Processing content (text-only): {title} ({url})")

        # Update status to processing
        db.update_content(
            content_id, {"status": "processing", "processing_steps": ["task_started"]}
        )

        # Import pipeline manager
        from ..pipeline.pipeline_manager import PipelineManager

        # Initialize pipeline manager in text-only mode
        pipeline = PipelineManager(text_only=True)

        # Define text-only pipeline steps
        steps = [
            "system_check",
            "hn_scraping",
            "firecrawl_content",
            "content_processing",
            "script_generation",
        ]

        # Execute each step
        for step_name in steps:
            logger.info(f"Executing step: {step_name}")

            try:
                # Update processing steps
                current_steps = content_data.get("processing_steps", [])
                if step_name not in current_steps:
                    current_steps.append(step_name)
                    db.update_content(content_id, {"processing_steps": current_steps})

                # Execute the step
                if step_name == "firecrawl_content":
                    logger.info(f"Starting firecrawl_content for {content_id}")
                    logger.info(f"URL: {url}")
                    logger.info(f"Title: {title}")

                    result = pipeline.execute_step(
                        step_name,
                        {
                            "selected_article": {
                                "url": url,
                                "title": title,
                                "id": content_id,
                            }
                        },
                    )

                    logger.info(
                        f"Firecrawl completed. Result keys: {list(result.keys())}"
                    )

                else:
                    logger.info(f"Starting {step_name} for {content_id}")
                    result = pipeline.execute_step(step_name, {})
                    logger.info(
                        f"{step_name} completed. Result keys: {list(result.keys())}"
                    )

                logger.info(f"Step {step_name} completed successfully")

            except Exception as e:
                logger.error(f"Step {step_name} failed: {e}")
                db.update_content(
                    content_id,
                    {
                        "status": "failed",
                        "processing_steps": content_data.get("processing_steps", []),
                        "errors": [f"Step {step_name} failed: {str(e)}"],
                    },
                )
                raise

        # Extract the script content
        script_content = ""
        script_file = Path("cache") / "script.md"
        if script_file.exists():
            with open(script_file, "r", encoding="utf-8") as f:
                script_content = f.read()
            logger.info(f"Script loaded: {len(script_content)} characters")

        # Update content with final results
        db.update_content(
            content_id,
            {
                "status": "completed",
                "processing_steps": content_data.get("processing_steps", []) + steps,
                "script": script_content,
                "summary": f"Successfully processed content and generated script with {len(script_content)} characters",
            },
        )

        logger.info(
            f"process_content_text_only task completed successfully for {content_id}"
        )

        return {
            "task_id": task_id,
            "content_id": content_id,
            "status": "completed",
            "script_length": len(script_content),
            "timestamp": datetime.now().isoformat(),
        }

    except Exception as e:
        logger.error(f"process_content_text_only task failed for {content_id}: {e}")

        # Update status to failed
        db.update_content(content_id, {"status": "failed", "errors": [str(e)]})

        # Re-raise to mark task as failed
        raise


@celery_app.task(bind=True, name="process_hn_story")
def process_hn_story(self, story_id: int, options: Dict[str, Any] = None):
    """
    Process a Hacker News story through the entire pipeline.

    This task:
    1. Fetches the HN story details
    2. Creates a content item in the database
    3. Processes it through the pipeline
    4. Marks the HN story as processed

    Args:
        story_id: Hacker News story ID
        options: Processing options (optional)
    """
    task_id = self.request.id
    logger.info(
        f"Starting process_hn_story task for HN story {story_id} (task: {task_id})"
    )

    try:
        # Import services
        from .database import ContentDatabase
        from ..scraper.hn_service import HackerNewsService

        db = ContentDatabase()
        hn_service = HackerNewsService()

        # Fetch HN story details
        logger.info(f"Fetching HN story {story_id} details")
        story_data = hn_service.get_story(story_id)

        if not story_data:
            raise RuntimeError(f"Could not fetch HN story {story_id}")

        # Extract story information
        title = story_data.get("title", f"HN Story {story_id}")
        url = story_data.get("url", f"https://news.ycombinator.com/item?id={story_id}")
        text = story_data.get("text", "")

        logger.info(f"Processing HN story: {title} ({url})")

        # Create content item
        content_id = str(uuid.uuid4())
        now = datetime.now()

        content_data = {
            "id": content_id,
            "hn_item_id": story_id,
            "title": title,
            "url": url,
            "post_text": text,
            "content_type": "hn_story",
            "status": "processing",
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
            "metadata": options or {},
            "processing_steps": ["hn_story_created"],
            "errors": [],
        }

        # Store content in database
        if not db.store_content(content_id, content_data):
            raise RuntimeError(f"Failed to store content item {content_id}")

        logger.info(f"Created content item {content_id} for HN story {story_id}")

        # Import pipeline manager
        from ..pipeline.pipeline_manager import PipelineManager

        # Initialize pipeline manager
        pipeline = PipelineManager()

        # Define all pipeline steps in order
        steps = [
            "system_check",
            "hn_scraping",
            "firecrawl_content",
            "content_processing",
            "script_generation",
            "tts_generation",
            "audio_cleaning",
            "audio_assembly",
            "image_generation",
            "video_generation",
        ]

        # Execute each step
        for step_name in steps:
            logger.info(f"Executing step: {step_name}")

            try:
                # Update processing steps
                current_steps = content_data.get("processing_steps", [])
                if step_name not in current_steps:
                    current_steps.append(step_name)
                    db.update_content(content_id, {"processing_steps": current_steps})

                # Execute the step
                if step_name == "firecrawl_content":
                    logger.info(f"Starting firecrawl_content for {content_id}")
                    logger.info(f"URL: {url}")
                    logger.info(f"Title: {title}")

                    result = pipeline.execute_step(
                        step_name,
                        {
                            "selected_article": {
                                "url": url,
                                "title": title,
                                "id": content_id,
                            }
                        },
                    )

                    logger.info(
                        f"Firecrawl completed. Result keys: {list(result.keys())}"
                    )

                else:
                    logger.info(f"Starting {step_name} for {content_id}")
                    result = pipeline.execute_step(step_name, {})
                    logger.info(
                        f"{step_name} completed. Result keys: {list(result.keys())}"
                    )

                logger.info(f"Step {step_name} completed successfully")

            except Exception as e:
                logger.error(f"Step {step_name} failed: {e}")
                db.update_content(
                    content_id,
                    {
                        "status": "failed",
                        "processing_steps": content_data.get("processing_steps", []),
                        "errors": [f"Step {step_name} failed: {str(e)}"],
                    },
                )
                raise

        # Extract the script content
        script_content = ""
        script_file = Path("cache") / "script.md"
        if script_file.exists():
            with open(script_file, "r", encoding="utf-8") as f:
                script_content = f.read()
            logger.info(f"Script loaded: {len(script_content)} characters")

        # Update content with final results
        db.update_content(
            content_id,
            {
                "status": "completed",
                "processing_steps": content_data.get("processing_steps", []) + steps,
                "script": script_content,
                "summary": f"Successfully processed HN story {story_id} and generated full media with {len(script_content)} characters",
            },
        )

        # Mark HN story as processed
        db.mark_hn_story_processed(story_id, content_id)

        logger.info(
            f"process_hn_story task completed successfully for HN story {story_id} -> content {content_id}"
        )

        return {
            "task_id": task_id,
            "story_id": story_id,
            "content_id": content_id,
            "status": "completed",
            "script_length": len(script_content),
            "timestamp": datetime.now().isoformat(),
        }

    except Exception as e:
        logger.error(f"process_hn_story task failed for HN story {story_id}: {e}")

        # Update status to failed if we have a content_id
        if "content_id" in locals():
            db.update_content(content_id, {"status": "failed", "errors": [str(e)]})

        # Re-raise to mark task as failed
        raise
