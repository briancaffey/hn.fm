"""FastAPI routes for the web API"""

import logging
import uuid
from datetime import datetime
from typing import List, Optional
from fastapi import FastAPI, HTTPException, Query, Depends, Request
from fastapi.responses import JSONResponse

from .models import (
    ContentItem,
    ContentListResponse,
    ContentCreateRequest,
    ContentUpdateRequest,
    PipelineStatus,
    HealthCheck,
    ServiceStatus,
    ServicesStatusResponse,
)
from .database import ContentDatabase
from .celery_app import celery_app
from ..scraper.hn_service import HackerNewsService

logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="hn.fm API",
    description="API for managing Hacker News content pipeline",
    version="0.1.0",
)

# Initialize database and services
db = ContentDatabase()
hn_service = HackerNewsService()


@app.get("/")
async def root():
    """API root endpoint - frontend is served by Nuxt"""
    return {"message": "hn.fm API", "version": "0.1.0", "docs": "/docs"}


@app.get("/health")
async def simple_health_check():
    """Simple health check endpoint for Docker healthcheck"""
    return {"status": "healthy"}


# Health and Services Endpoints
@app.get("/api/health", response_model=HealthCheck, tags=["health"])
async def health_check():
    """Health check endpoint"""
    redis_status = "healthy" if db.health_check() else "unhealthy"

    return HealthCheck(
        status="healthy",
        timestamp=datetime.now(),
        version="0.1.0",
        redis_status=redis_status,
    )


@app.get("/api/services/status", response_model=ServicesStatusResponse, tags=["services"])
async def get_services_status():
    """Get status of all services"""
    try:
        from ..utils.system_checker import SystemChecker

        system_checker = SystemChecker()
        all_healthy, service_statuses = system_checker.check_all_services()

        # Convert ServiceStatus dataclass to our Pydantic model
        services = []
        for status in service_statuses:
            services.append(
                ServiceStatus(
                    name=status.name,
                    url=status.url,
                    status=status.status,
                    response_time=status.response_time,
                    error_message=status.error_message,
                    details=status.details,
                )
            )

        return ServicesStatusResponse(
            all_healthy=all_healthy, services=services, timestamp=datetime.now()
        )

    except Exception as e:
        logger.error(f"Failed to get services status: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


# Content Endpoints
@app.get("/api/content", response_model=ContentListResponse, tags=["content"])
async def list_content(
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(20, ge=1, le=100, description="Items per page"),
    content_type: Optional[str] = Query(None, description="Filter by content type"),
    status: Optional[str] = Query(None, description="Filter by status"),
):
    """List content items with pagination and filtering"""
    try:
        result = db.list_content(page, per_page, content_type, status)
        return ContentListResponse(**result)
    except Exception as e:
        logger.error(f"Failed to list content: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/api/content/{content_id}", response_model=ContentItem, tags=["content"])
async def get_content(content_id: str):
    """Get a specific content item"""
    try:
        content = db.get_content(content_id)
        if not content:
            raise HTTPException(status_code=404, detail="Content not found")
        return ContentItem(**content)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get content {content_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.post("/api/content", response_model=ContentItem, tags=["content"])
async def create_content(request: ContentCreateRequest):
    """Create a new content item"""
    try:
        content_id = str(uuid.uuid4())
        now = datetime.now()

        content_data = {
            "id": content_id,
            "title": f"Processing: {request.url}",
            "url": request.url,
            "content_type": request.content_type,
            "status": "pending",
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
            "metadata": request.options,
            "processing_steps": [],
            "errors": [],
        }

        if db.store_content(content_id, content_data):
            return ContentItem(**content_data)
        else:
            raise HTTPException(status_code=500, detail="Failed to store content")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create content: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.put("/api/content/{content_id}", response_model=ContentItem, tags=["content"])
async def update_content(content_id: str, request: ContentUpdateRequest):
    """Update a content item"""
    try:
        updates = {}
        if request.title is not None:
            updates["title"] = request.title
        if request.status is not None:
            updates["status"] = request.status
        if request.metadata is not None:
            updates["metadata"] = request.metadata

        if not updates:
            raise HTTPException(status_code=400, detail="No updates provided")

        if db.update_content(content_id, updates):
            content = db.get_content(content_id)
            if content:
                return ContentItem(**content)
            else:
                raise HTTPException(status_code=404, detail="Content not found")
        else:
            raise HTTPException(status_code=500, detail="Failed to update content")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update content {content_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.delete("/api/content/{content_id}", tags=["content"])
async def delete_content(content_id: str):
    """Delete a content item"""
    try:
        if db.delete_content(content_id):
            return {"message": "Content deleted successfully"}
        else:
            raise HTTPException(status_code=404, detail="Content not found")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete content {content_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


# Pipeline Endpoints
@app.get("/api/pipeline/status", response_model=PipelineStatus, tags=["pipeline"])
async def get_pipeline_status():
    """Get pipeline status information"""
    try:
        status_data = db.get_pipeline_status()
        return PipelineStatus(**status_data)
    except Exception as e:
        logger.error(f"Failed to get pipeline status: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.post("/api/process", tags=["pipeline"])
async def process_content(request: ContentCreateRequest):
    """Process content through the pipeline"""
    try:
        # Create content item
        content_id = str(uuid.uuid4())
        now = datetime.now()

        content_data = {
            "id": content_id,
            "title": f"Processing: {request.url}",
            "url": request.url,
            "content_type": request.content_type,
            "status": "processing",
            "created_at": now,
            "updated_at": now,
            "metadata": request.options,
            "processing_steps": ["created"],
            "errors": [],
        }

        if not db.store_content(content_id, content_data):
            raise HTTPException(status_code=500, detail="Failed to store content")

        # Start the processing task
        from .tasks import process_content_text_only

        task = process_content_text_only.delay(content_id)

        logger.info(f"Started processing task {task.id} for content {content_id}")

        return {
            "message": "Processing started",
            "task_id": task.id,
            "content_id": content_id,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to start processing: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


# Hacker News Endpoints
@app.post("/api/hn/process-top-stories", tags=["hacker-news"])
async def process_top_hn_stories(
    limit: int = Query(50, ge=1, le=100, description="Number of top stories to process")
):
    """
    Fetch top stories from Hacker News and queue them for processing

    This endpoint:
    1. Fetches the top stories from HN API
    2. Checks which ones are already processed
    3. Queues new stories for processing
    4. Returns summary of what was queued vs skipped
    """
    try:
        logger.info(f"Processing top {limit} HN stories")

        # Fetch top stories from HN
        story_ids = hn_service.get_top_stories(limit)
        if not story_ids:
            raise HTTPException(
                status_code=500, detail="Failed to fetch top stories from HN API"
            )

        logger.info(f"Fetched {len(story_ids)} top stories from HN")

        # Check which stories are already processed
        queued_stories = []
        skipped_stories = []

        for story_id in story_ids:
            if db.is_hn_story_processed(story_id):
                skipped_stories.append(story_id)
                logger.debug(f"Story {story_id} already processed, skipping")
            else:
                queued_stories.append(story_id)
                logger.debug(f"Story {story_id} not processed, queuing")

        # Queue new stories for processing
        queued_tasks = []
        for story_id in queued_stories:
            try:
                # Queue the Celery task
                task = celery_app.send_task(
                    "process_hn_story", args=[story_id], queue="hnfm_tasks"
                )
                queued_tasks.append({"story_id": story_id, "task_id": task.id})
                logger.info(f"Queued story {story_id} for processing (task: {task.id})")
            except Exception as e:
                logger.error(f"Failed to queue story {story_id}: {e}")
                # Remove from queued list if we failed to queue it
                queued_stories.remove(story_id)
                skipped_stories.append(story_id)

        # Get HN processing statistics
        hn_stats = db.get_hn_processing_stats()

        return {
            "message": "Top stories processing initiated",
            "summary": {
                "total_fetched": len(story_ids),
                "queued_for_processing": len(queued_stories),
                "skipped_already_processed": len(skipped_stories),
                "failed_to_queue": len(story_ids)
                - len(queued_stories)
                - len(skipped_stories),
            },
            "queued_tasks": queued_tasks,
            "hn_processing_stats": hn_stats,
            "timestamp": datetime.now().isoformat(),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to process top HN stories: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@app.get("/api/hn/stats", tags=["hacker-news"])
async def get_hn_stats():
    """Get Hacker News processing statistics"""
    try:
        stats = db.get_hn_processing_stats()
        return {"hn_processing_stats": stats, "timestamp": datetime.now().isoformat()}
    except Exception as e:
        logger.error(f"Failed to get HN stats: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


# Celery Endpoints
@app.get("/api/celery/task/{task_id}", tags=["celery"])
async def get_task_status(task_id: str):
    """Get status of a specific Celery task"""
    try:
        task_result = celery_app.AsyncResult(task_id)
        return {
            "task_id": task_id,
            "status": task_result.status,
            "ready": task_result.ready(),
            "successful": task_result.successful(),
            "failed": task_result.failed(),
            "result": task_result.result if task_result.ready() else None,
            "error": str(task_result.info) if task_result.failed() else None,
        }
    except Exception as e:
        logger.error(f"Failed to get task status for {task_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/api/celery/active", tags=["celery"])
async def get_active_tasks():
    """Get list of active Celery tasks"""
    try:
        # Get active tasks from Celery
        active_tasks = celery_app.control.inspect().active()

        if not active_tasks:
            return {"active_tasks": []}

        # Flatten the active tasks
        all_active = []
        for worker, tasks in active_tasks.items():
            for task in tasks:
                all_active.append({
                    "task_id": task["id"],
                    "name": task["name"],
                    "worker": worker,
                    "started": task.get("time_start", 0),
                })

        return {"active_tasks": all_active}
    except Exception as e:
        logger.error(f"Failed to get active tasks: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


# Error handlers
@app.exception_handler(404)
async def not_found_handler(request, exc):
    return {"detail": "Not found"}


@app.exception_handler(500)
async def internal_error_handler(request, exc):
    return {"detail": "Internal server error"}
