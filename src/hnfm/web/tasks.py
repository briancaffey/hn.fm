"""Celery tasks for hn.fm content processing"""

import time
import logging
import random
from datetime import datetime
from celery import current_task
from .celery_app import celery_app, get_db

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, name="debug_task")
def debug_task(self):
    """Debug task to test Celery setup"""
    logger.info(f"Debug task {self.request.id} executed")

    # Simulate some work
    time.sleep(2)

    # Update task state
    current_task.update_state(
        state="PROGRESS",
        meta={"current": 50, "total": 100, "status": "Debug task in progress"}
    )

    time.sleep(1)

    return {
        "task_id": self.request.id,
        "status": "completed",
        "message": "Debug task completed successfully",
        "timestamp": datetime.now().isoformat()
    }


@celery_app.task(bind=True, name="process_content")
def process_content(self, content_id: str, url: str, content_type: str = "article"):
    """Process content through the pipeline"""
    logger.info(f"Starting content processing for {content_id}")

    db = get_db()

    try:
        # Update status to processing
        db.update_content(content_id, {
            "status": "processing",
            "processing_steps": ["processing_started"]
        })

        # Simulate content processing steps
        steps = [
            "content_scraping",
            "text_processing",
            "script_generation",
            "audio_generation",
            "final_assembly"
        ]

        for i, step in enumerate(steps):
            # Update progress
            progress = int((i + 1) * 100 / len(steps))
            current_task.update_state(
                state="PROGRESS",
                meta={
                    "current": progress,
                    "total": 100,
                    "status": f"Processing: {step}",
                    "step": step
                }
            )

            # Simulate step processing time
            time.sleep(random.uniform(1, 3))

            # Update content with completed step
            current_steps = db.get_content(content_id).get("processing_steps", [])
            current_steps.append(step)
            db.update_content(content_id, {"processing_steps": current_steps})

            logger.info(f"Completed step {step} for {content_id}")

        # Mark as completed
        db.update_content(content_id, {
            "status": "completed",
            "processing_steps": ["completed"],
            "summary": f"Successfully processed {content_type} from {url}"
        })

        logger.info(f"Content processing completed for {content_id}")

        return {
            "task_id": self.request.id,
            "content_id": content_id,
            "status": "completed",
            "steps_completed": steps,
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"Content processing failed for {content_id}: {e}")

        # Update status to failed
        db.update_content(content_id, {
            "status": "failed",
            "errors": [str(e)]
        })

        # Re-raise to mark task as failed
        raise


@celery_app.task(bind=True, name="scrape_content")
def scrape_content(self, content_id: str, url: str):
    """Scrape content from URL"""
    logger.info(f"Starting content scraping for {content_id}")

    db = get_db()

    try:
        # Simulate scraping
        time.sleep(random.uniform(2, 5))

        # Mock scraped content
        scraped_text = f"Mock scraped content from {url}. This is a sample article content that would normally be extracted from the webpage."

        # Update content with scraped data
        db.update_content(content_id, {
            "raw_text": scraped_text,
            "processing_steps": ["scraping_completed"]
        })

        logger.info(f"Content scraping completed for {content_id}")

        return {
            "task_id": self.request.id,
            "content_id": content_id,
            "status": "scraped",
            "text_length": len(scraped_text)
        }

    except Exception as e:
        logger.error(f"Content scraping failed for {content_id}: {e}")
        raise


@celery_app.task(bind=True, name="generate_script")
def generate_script(self, content_id: str):
    """Generate script from scraped content"""
    logger.info(f"Starting script generation for {content_id}")

    db = get_db()

    try:
        # Get content
        content = db.get_content(content_id)
        if not content or not content.get("raw_text"):
            raise ValueError("No raw text available for script generation")

        # Simulate script generation
        time.sleep(random.uniform(3, 6))

        # Mock generated script
        script = f"""Welcome to today's episode. We're discussing an interesting article that caught our attention.

The main points are:
- This is a fascinating topic
- There are several key insights to consider
- The implications are significant

Let me break this down for you in detail..."""

        # Update content with script
        db.update_content(content_id, {
            "script": script,
            "processing_steps": ["script_generation_completed"]
        })

        logger.info(f"Script generation completed for {content_id}")

        return {
            "task_id": self.request.id,
            "content_id": content_id,
            "status": "script_generated",
            "script_length": len(script)
        }

    except Exception as e:
        logger.error(f"Script generation failed for {content_id}: {e}")
        raise


@celery_app.task(bind=True, name="generate_audio")
def generate_audio(self, content_id: str):
    """Generate audio from script"""
    logger.info(f"Starting audio generation for {content_id}")

    db = get_db()

    try:
        # Get content
        content = db.get_content(content_id)
        if not content or not content.get("script"):
            raise ValueError("No script available for audio generation")

        # Simulate audio generation
        time.sleep(random.uniform(5, 10))

        # Mock audio file path
        audio_path = f"outputs/audio/{content_id}.wav"

        # Update content with audio path
        db.update_content(content_id, {
            "audio_path": audio_path,
            "processing_steps": ["audio_generation_completed"]
        })

        logger.info(f"Audio generation completed for {content_id}")

        return {
            "task_id": self.request.id,
            "content_id": content_id,
            "status": "audio_generated",
            "audio_path": audio_path
        }

    except Exception as e:
        logger.error(f"Audio generation failed for {content_id}: {e}")
        raise


@celery_app.task(bind=True, name="cleanup_old_results")
def cleanup_old_results():
    """Clean up old task results (called by Celery Beat)"""
    logger.info("Running cleanup of old results")

    try:
        # This would clean up old task results from Redis
        # For now, just log the cleanup
        logger.info("Cleanup completed")
        return {"status": "cleanup_completed"}

    except Exception as e:
        logger.error(f"Cleanup failed: {e}")
        raise


@celery_app.task(bind=True, name="long_running_task")
def long_running_task(self, duration: int = 30):
    """Long running task for testing progress monitoring"""
    logger.info(f"Starting long running task for {duration} seconds")

    try:
        for i in range(duration):
            # Update progress every second
            progress = int((i + 1) * 100 / duration)
            current_task.update_state(
                state="PROGRESS",
                meta={
                    "current": progress,
                    "total": 100,
                    "status": f"Processing... {i+1}/{duration} seconds",
                    "elapsed": i + 1,
                    "remaining": duration - i - 1
                }
            )

            time.sleep(1)

        logger.info("Long running task completed")

        return {
            "task_id": self.request.id,
            "status": "completed",
            "duration": duration,
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"Long running task failed: {e}")
        raise


# Task chain example
@celery_app.task(bind=True, name="full_pipeline")
def full_pipeline(self, content_id: str, url: str, content_type: str = "article"):
    """Execute full content processing pipeline"""
    logger.info(f"Starting full pipeline for {content_id}")

    try:
        # Execute pipeline steps in sequence
        scrape_result = scrape_content.delay(content_id, url)
        scrape_result.get()  # Wait for completion

        script_result = generate_script.delay(content_id)
        script_result.get()  # Wait for completion

        audio_result = generate_audio.delay(content_id)
        audio_result.get()  # Wait for completion

        # Mark as completed
        db = get_db()
        db.update_content(content_id, {
            "status": "completed",
            "processing_steps": ["pipeline_completed"]
        })

        logger.info(f"Full pipeline completed for {content_id}")

        return {
            "task_id": self.request.id,
            "content_id": content_id,
            "status": "pipeline_completed",
            "steps": ["scraping", "script_generation", "audio_generation"]
        }

    except Exception as e:
        logger.error(f"Full pipeline failed for {content_id}: {e}")

        # Mark as failed
        db = get_db()
        db.update_content(content_id, {
            "status": "failed",
            "errors": [str(e)]
        })

        raise
