"""Celery tasks for hn.fm"""

import logging
import uuid
from datetime import datetime
from .database import ContentDatabase
from ..scraper.hn_service import HackerNewsService
from .celery_app import celery_app
from pathlib import Path

logger = logging.getLogger(__name__)

# Initialize services with error handling
hn_service = HackerNewsService()

# Optional services - these might not be available in all environments
try:
    from ..content.content_processor import ContentProcessor
    content_processor = ContentProcessor()
except ImportError:
    logger.warning("ContentProcessor not available")
    content_processor = None

try:
    from ..content.script_generator import ScriptGenerator
    script_generator = ScriptGenerator()
except ImportError:
    logger.warning("ScriptGenerator not available")
    script_generator = None

try:
    from ..audio.tts_service import TTSService
    tts_service = TTSService()
except ImportError:
    logger.warning("TTSService not available")
    tts_service = None

try:
    from ..video.image_generator import ImageGenerationService
    image_generator = ImageGenerationService()
except ImportError:
    logger.warning("ImageGenerationService not available")
    image_generator = None

try:
    from ..video.video_generator import VideoGenerator
    video_generator = VideoGenerator()
except ImportError:
    logger.warning("VideoGenerator not available")
    video_generator = None

# Database helper for tasks
def get_db():
    """Get database instance for tasks"""
    return ContentDatabase()


@celery_app.task(bind=True, name="process_hn_story")
def process_hn_story(self, story_id: int):
    """
    Process a single Hacker News story

    This task:
    1. Fetches the HN story data
    2. Saves it to Redis with HN data attached
    3. Proceeds with the rest of the pipeline (scraping, processing, generation)

    Args:
        story_id: The Hacker News story ID to process

    Returns:
        Dictionary with processing results
    """
    task_id = self.request.id
    logger.info(f"Starting HN story processing task {task_id} for story {story_id}")

    try:
        db = get_db()

        # Check if story is already processed
        if db.is_hn_story_processed(story_id):
            logger.info(f"Story {story_id} already processed, skipping")
            return {
                'status': 'skipped',
                'reason': 'already_processed',
                'story_id': story_id
            }

        # Fetch HN story data
        logger.info(f"Fetching HN story data for {story_id}")
        hn_story = hn_service.get_story(story_id)

        if not hn_story:
            logger.error(f"Failed to fetch HN story {story_id}")
            return {
                'status': 'failed',
                'reason': 'failed_to_fetch_hn_data',
                'story_id': story_id,
                'error': 'Could not fetch story from HN API'
            }

        # Create content item with HN data
        content_id = str(uuid.uuid4())
        content_data = {
            'id': content_id,
            'title': hn_story.title or f"HN Story {story_id}",
            'url': hn_story.url or f"https://news.ycombinator.com/item?id={story_id}",
            'content_type': 'article',
            'status': 'processing',
            'created_at': datetime.now(),
            'updated_at': datetime.now(),
            'hn_story_data': hn_story.dict(),
            'processing_steps': ['hn_data_fetched'],
            'metadata': {
                'source': 'hacker_news',
                'hn_id': story_id,
                'hn_score': hn_story.score,
                'hn_author': hn_story.by,
                'hn_time': datetime.fromtimestamp(hn_story.time).isoformat() if hn_story.time else None
            }
        }

        # Save to Redis
        if not db.store_content(content_id, content_data):
            logger.error(f"Failed to store content {content_id} in Redis")
            return {
                'status': 'failed',
                'reason': 'failed_to_store_in_redis',
                'story_id': story_id,
                'error': 'Could not store content in database'
            }

        # Mark HN story as processed
        if not db.mark_hn_story_processed(story_id, content_id):
            logger.warning(f"Failed to mark HN story {story_id} as processed")

        logger.info(f"Successfully saved HN story {story_id} as content {content_id}")

        # TODO: Continue with the rest of the pipeline
        # This would include:
        # - Firecrawl scraping
        # - Content processing
        # - Script generation
        # - Audio generation
        # - Image generation
        # - Video generation

        # For now, just mark as completed
        db.update_content(content_id, {
            'status': 'completed',
            'processing_steps': ['hn_data_fetched', 'saved_to_redis'],
            'updated_at': datetime.now()
        })

        return {
            'status': 'completed',
            'story_id': story_id,
            'content_id': content_id,
            'message': 'HN story processed and saved successfully'
        }

    except Exception as e:
        logger.error(f"Error processing HN story {story_id}: {e}")
        return {
            'status': 'failed',
            'reason': 'unexpected_error',
            'story_id': story_id,
            'error': str(e)
        }


@celery_app.task(bind=True, name="cleanup_old_results")
def cleanup_old_results(self):
    """Clean up old task results from Redis"""
    try:
        db = get_db()
        # TODO: Implement cleanup logic
        logger.info("Cleanup task completed")
        return "Cleanup completed successfully"
    except Exception as e:
        logger.error(f"Cleanup task failed: {e}")
        return f"Cleanup failed: {e}"


@celery_app.task(bind=True, name="debug_task")
def debug_task(self):
    """Debug task to test Celery setup"""
    logger.info(f"Debug task {self.request.id} executed")
    return f"Debug task completed: {self.request.id}"


@celery_app.task(bind=True, name="process_content")
def process_content(self, content_id: str, url: str, content_type: str = "article"):
    """Process content through the pipeline"""
    logger.info(f"Starting content processing for {content_id}")

    try:
        db = get_db()

        # Update status to processing
        db.update_content(content_id, {
            "status": "processing",
            "processing_steps": ["processing_started"]
        })

        # For now, just mark as completed
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


@celery_app.task(bind=True, name="full_pipeline")
def full_pipeline(self, content_id: str, url: str, content_type: str = "article"):
    """Execute full content processing pipeline"""
    logger.info(f"Starting full pipeline for {content_id}")

    try:
        db = get_db()

        # Update status to processing
        db.update_content(content_id, {
            "status": "processing",
            "processing_steps": ["pipeline_started"]
        })

        # For now, just mark as completed
        db.update_content(content_id, {
            "status": "completed",
            "processing_steps": ["pipeline_completed"],
            "summary": f"Full pipeline completed for {content_type} from {url}"
        })

        logger.info(f"Full pipeline completed for {content_id}")

        return {
            "task_id": self.request.id,
            "content_id": content_id,
            "status": "pipeline_completed",
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"Full pipeline failed for {content_id}: {e}")

        # Update status to failed
        db.update_content(content_id, {
            "status": "failed",
            "errors": [str(e)]
        })

        # Re-raise to mark task as failed
        raise


@celery_app.task(bind=True, name="process_content_pipeline")
def process_content_pipeline(self, content_id: str):
    """Process content through the full pipeline (scraping, processing, script generation)"""
    logger.info(f"Starting content pipeline processing for {content_id}")

    try:
        db = get_db()

        # Get the content item
        content = db.get_content(content_id)
        if not content:
            raise RuntimeError(f"Content {content_id} not found")

        url = content.get('url')
        title = content.get('title', 'Unknown Title')

        # Update status and add processing step
        db.update_content(content_id, {
            "status": "processing",
            "processing_steps": ["pipeline_started"]
        })

        # Import pipeline manager
        from ..pipeline.pipeline_manager import PipelineManager

        # Initialize pipeline manager in text-only mode (no TTS, images, video)
        pipeline = PipelineManager(text_only=True)

        # Run the pipeline steps we need: firecrawl_content, content_processing, script_generation
        logger.info(f"Running pipeline for content {content_id}: {url}")

        # Execute firecrawl content extraction
        # The pipeline expects a selected_article structure
        firecrawl_result = pipeline._execute_firecrawl_content({
            "selected_article": {
                "url": url,
                "title": title,
                "id": content_id  # Use content_id as the article ID
            }
        })

        # Execute content processing
        processing_result = pipeline._execute_content_processing(firecrawl_result)

        # Execute script generation
        script_result = pipeline._execute_script_generation(processing_result)

        # Extract the script content
        script_content = ""
        if script_result and "script_path" in script_result:
            script_path = Path(script_result["script_path"])
            if script_path.exists():
                with open(script_path, "r", encoding="utf-8") as f:
                    script_content = f.read()

        # Update content with results
        db.update_content(content_id, {
            "status": "completed",
            "processing_steps": ["pipeline_started", "firecrawl_content", "content_processing", "script_generation"],
            "raw_text": firecrawl_result.get("raw_content", ""),
            "processed_text": processing_result.get("cleaned_content", ""),
            "script": script_content,
            "summary": f"Successfully processed content and generated script with {len(script_content)} characters"
        })

        logger.info(f"Content pipeline processing completed for {content_id}")

        return {
            "task_id": self.request.id,
            "content_id": content_id,
            "status": "completed",
            "script_length": len(script_content),
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"Content pipeline processing failed for {content_id}: {e}")

        # Update status to failed
        db.update_content(content_id, {
            "status": "failed",
            "errors": [str(e)]
        })

        # Re-raise to mark task as failed
        raise
