"""FastAPI server entry point for hn.fm web interface"""

import os
import logging
import json
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from datetime import datetime
import uuid

from .database import ContentDatabase
from .models import (
    ContentItem,
    ContentListResponse,
    ContentCreateRequest,
    ContentUpdateRequest,
    PipelineStatus,
    HealthCheck,
    ServiceStatus,
    ServicesStatusResponse,
    TaskResponse,
    TaskStatus,
    ActiveTasksResponse,
    ErrorResponse,
)
from .celery_app import celery_app
from .tasks import (
    full_pipeline,
    content_pipeline,
    process_content_pipeline,
)
from ..scraper.hn_service import HackerNewsService

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    # Startup
    logger.info("Starting hn.fm web server...")

    # Test database connection
    try:
        db = ContentDatabase()
        if db.health_check():
            logger.info("Database connection established")
        else:
            logger.warning("Database connection failed")
    except Exception as e:
        logger.error(f"Database connection error: {e}")

    yield

    # Shutdown
    logger.info("Shutting down hn.fm web server...")


# Create main FastAPI app
app = FastAPI(
    title="hn.fm Web Interface",
    description="""
# hn.fm Web Interface API

A comprehensive web interface and API for managing the Hacker News content processing pipeline.

## Features

* **Content Management**: Create, read, update, and delete content items
* **Pipeline Processing**: Trigger content processing workflows using Celery
* **Service Monitoring**: Check the health and status of all backend services
* **Task Management**: Monitor and manage Celery background tasks
* **Real-time Updates**: Track processing progress and status changes

## Getting Started

1. **Health Check**: Start with `/api/health` to verify the service is running
2. **Content Creation**: Use `/api/pipeline/process` to start processing new content
3. **Status Monitoring**: Check `/api/pipeline/status` for pipeline health
4. **Service Health**: Monitor all services with `/api/services/status`

## Authentication

Currently, this API is designed for internal use. In production, consider adding authentication middleware.

## Rate Limiting

Be mindful of processing pipeline capacity. Each content processing request creates a new job.
    """,
    version="0.1.0",
    contact={
        "name": "hn.fm Development Team",
        "url": "https://github.com/your-org/hn.fm",
    },
    license_info={
        "name": "MIT",
        "url": "https://opensource.org/licenses/MIT",
    },
    servers=[
        {"url": "http://localhost:8000", "description": "Development server"},
        {"url": "https://api.hn.fm", "description": "Production server"},
    ],
    tags=[
        {"name": "health", "description": "Health check and monitoring endpoints"},
        {"name": "content", "description": "Content management operations"},
        {"name": "pipeline", "description": "Content processing pipeline operations"},
        {"name": "celery", "description": "Background task management"},
        {"name": "services", "description": "Backend service status monitoring"},
        {
            "name": "hacker-news",
            "description": "Hacker News story processing operations",
        },
    ],
    lifespan=lifespan,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Global exception handlers for better error responses
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Handle HTTP exceptions with consistent error format"""
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(
            detail=exc.detail,
            error_code=f"HTTP_{exc.status_code}",
            timestamp=datetime.now(),
        ).dict(),
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle general exceptions with consistent error format"""
    logger.error(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=500,
        content=ErrorResponse(
            detail="Internal server error",
            error_code="INTERNAL_ERROR",
            timestamp=datetime.now(),
        ).model_dump(),
    )


# Initialize database
db = ContentDatabase()
hn_service = HackerNewsService()

# Static files and templates removed - using Nuxt frontend instead


@app.get("/")
async def root():
    """API root endpoint - frontend is served by Nuxt"""
    return {"message": "hn.fm API", "version": "0.1.0", "docs": "/docs"}


@app.get("/health", tags=["health"])
async def health_check():
    """
    Simple health check endpoint for load balancers and basic monitoring.

    Returns a basic status response without database checks.
    """
    return {"status": "healthy", "service": "hn.fm-web"}


# API Routes
@app.get("/api/health", response_model=HealthCheck, tags=["health"])
async def api_health_check():
    """
    Comprehensive health check endpoint for the API.

    Performs database connectivity checks and returns detailed health information.

    Returns:
        HealthCheck: Detailed health status including Redis connectivity

    Raises:
        HTTPException: If health check fails
    """
    redis_status = "healthy" if db.health_check() else "unhealthy"

    return HealthCheck(
        status="healthy",
        timestamp=datetime.now(),
        version="0.1.0",
        redis_status=redis_status,
    )


@app.get(
    "/api/services/status", response_model=ServicesStatusResponse, tags=["services"]
)
async def get_services_status():
    """
    Get comprehensive status of all backend services.

    Checks the health and response time of all configured services including:
    - Local LLM services
    - Firecrawl scraping service
    - TTS (Text-to-Speech) services
    - Studio Voice services
    - ASR (Automatic Speech Recognition) services
    - Image generation services

    Returns:
        ServicesStatusResponse: Status of all services with health indicators

    Raises:
        HTTPException: If service status check fails
    """
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


@app.get("/api/content", response_model=ContentListResponse, tags=["content"])
async def list_content(
    page: int = Query(1, ge=1, description="Page number (starts from 1)"),
    per_page: int = Query(
        20, ge=1, le=100, description="Number of items per page (max 100)"
    ),
    content_type: str = Query(
        None, description="Filter by content type (e.g., 'article', 'podcast', 'video')"
    ),
    status: str = Query(
        None,
        description="Filter by processing status (e.g., 'pending', 'processing', 'completed', 'failed')",
    ),
):
    """
    List content items with pagination and filtering capabilities.

    Retrieves a paginated list of content items from the pipeline. Supports filtering
    by content type and processing status for easier content management.

    Args:
        page: Page number for pagination (1-based)
        per_page: Number of items per page (1-100)
        content_type: Optional filter for specific content types
        status: Optional filter for specific processing statuses

    Returns:
        ContentListResponse: Paginated list of content items with metadata

    Raises:
        HTTPException: If content retrieval fails
    """
    try:
        result = db.list_content(page, per_page, content_type, status)

        # Migrate old content items to new format
        migrated_items = []
        for item in result["items"]:
            try:
                # Add missing required fields for old items
                if "hn_item_id" not in item:
                    item["hn_item_id"] = 0  # Default value for old items
                if "post_text" not in item:
                    item["post_text"] = item.get("text", "")
                if "raw_content" not in item:
                    item["raw_content"] = item.get("raw_text", "")
                if "processed_content" not in item:
                    item["processed_content"] = item.get("processed_text", "")
                if "audio_file_path" not in item:
                    item["audio_file_path"] = item.get("audio_path", "")

                migrated_items.append(ContentItem(**item))
            except Exception as e:
                logger.warning(
                    f"Failed to migrate content item {item.get('id', 'unknown')}: {e}"
                )
                # Skip items that can't be migrated
                continue

        result["items"] = migrated_items
        return ContentListResponse(**result)
    except Exception as e:
        logger.error(f"Failed to list content: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/api/content/{content_id}", response_model=ContentItem, tags=["content"])
async def get_content(content_id: str):
    """
    Retrieve a specific content item by its unique identifier.

    Returns detailed information about a content item including its current
    processing status, generated content, and any errors encountered.

    Args:
        content_id: Unique identifier of the content item

    Returns:
        ContentItem: Complete content item information

    Raises:
        HTTPException: If content is not found or retrieval fails
    """
    try:
        content = db.get_content(content_id)
        if not content:
            raise HTTPException(status_code=404, detail="Content not found")

        # Migrate old content item to new format
        if "hn_item_id" not in content:
            content["hn_item_id"] = 0  # Default value for old items
        if "post_text" not in content:
            content["post_text"] = content.get("text", "")
        if "raw_content" not in content:
            content["raw_content"] = content.get("raw_text", "")
        if "processed_content" not in content:
            content["processed_content"] = content.get("processed_text", "")
        if "audio_file_path" not in content:
            content["audio_file_path"] = content.get("audio_path", "")

        return ContentItem(**content)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get content {content_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.post("/api/content", response_model=ContentItem, tags=["content"])
async def create_content(request: ContentCreateRequest):
    """
    Create a new content item in the pipeline.

    Creates a new content item with the specified URL and content type.
    The item is initially created with 'pending' status and will need
    to be processed separately using the pipeline endpoints.

    Args:
        request: Content creation request with URL and options

    Returns:
        ContentItem: The newly created content item

    Raises:
        HTTPException: If content creation fails
    """
    try:
        content_id = str(uuid.uuid4())
        now = datetime.now()

        content_data = {
            "id": content_id,
            "title": f"Processing: {request.url}",
            "url": request.url,
            "content_type": request.content_type,
            "status": "pending",
            "created_at": now,
            "updated_at": now,
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
    """
    Update an existing content item.

    Allows modification of content item properties such as title, status,
    and metadata. Only the fields provided in the request will be updated.

    Args:
        content_id: Unique identifier of the content item to update
        request: Update request containing fields to modify

    Returns:
        ContentItem: The updated content item

    Raises:
        HTTPException: If content is not found or update fails
    """
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
    """
    Delete a content item from the pipeline.

    Permanently removes a content item and all associated data including
    generated content, audio, video, and images. This action cannot be undone.

    Args:
        content_id: Unique identifier of the content item to delete

    Returns:
        dict: Confirmation message

    Raises:
        HTTPException: If content is not found or deletion fails
    """
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


@app.post("/api/content/{content_id}/process", tags=["content"])
async def process_content(content_id: str):
    """Process a content item through the pipeline"""
    try:
        # Get the content item first
        content = db.get_content(content_id)
        if not content:
            raise HTTPException(status_code=404, detail="Content not found")

        # Check if content is already being processed
        if content.get("status") == "processing":
            raise HTTPException(
                status_code=400, detail="Content is already being processed"
            )

        # Update status to processing
        db.update_content(content_id, {"status": "processing"})

        # Start the processing task
        from .tasks import process_content_pipeline

        task = process_content_pipeline.delay(content_id)

        logger.info(f"Started processing task {task.id} for content {content_id}")

        return {
            "message": "Processing started",
            "task_id": task.id,
            "content_id": content_id,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to start processing for content {content_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/api/pipeline/status", response_model=PipelineStatus, tags=["pipeline"])
async def get_pipeline_status():
    """
    Get comprehensive pipeline status information.

    Returns current pipeline metrics including running jobs, completion statistics,
    and overall health indicators. Useful for monitoring pipeline performance
    and identifying bottlenecks.

    Returns:
        PipelineStatus: Current pipeline status and metrics

    Raises:
        HTTPException: If status retrieval fails
    """
    try:
        status_data = db.get_pipeline_status()
        return PipelineStatus(**status_data)
    except Exception as e:
        logger.error(f"Failed to get pipeline status: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.post("/api/pipeline/process-full", response_model=TaskResponse, tags=["pipeline"])
async def process_full_pipeline(request: ContentCreateRequest):
    """
    Trigger full content processing pipeline using Celery.

    Creates a new content item and queues it for complete processing through
    the entire pipeline including scraping, text processing, script generation,
    audio generation, and video creation. This is the most comprehensive
    processing option.

    Args:
        request: Content processing request with URL and options

    Returns:
        TaskResponse: Processing status with content ID and task ID

    Raises:
        HTTPException: If processing initiation fails
    """
    try:
        # Create content item
        content_id = str(uuid.uuid4())
        now = datetime.now()

        content_data = {
            "id": content_id,
            "title": f"Processing: {request.url}",
            "url": request.url,
            "content_type": request.content_type,
            "status": "queued",
            "created_at": now,
            "updated_at": now,
            "metadata": request.options,
            "processing_steps": ["created"],
            "errors": [],
        }

        if not db.store_content(content_id, content_data):
            raise HTTPException(status_code=500, detail="Failed to store content")

        # Queue the full pipeline task
        task = full_pipeline.delay(content_id, request.url, request.content_type)

        logger.info(f"Full pipeline queued for {content_id} with task {task.id}")

        return TaskResponse(
            message="Full pipeline queued", task_id=task.id, status="queued"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to trigger full pipeline: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.post("/api/celery/debug", response_model=TaskResponse, tags=["celery"])
async def trigger_debug_task():
    """
    Trigger a debug Celery task for testing purposes.

    Queues a simple debug task to verify Celery worker connectivity
    and task execution. Useful for debugging worker setup and
    monitoring task lifecycle.

    Returns:
        TaskResponse: Task status with task ID

    Raises:
        HTTPException: If task queuing fails
    """
    try:
        task = debug_task.delay()
        logger.info(f"Debug task queued with ID: {task.id}")

        return TaskResponse(
            message="Debug task queued", task_id=task.id, status="queued"
        )

    except Exception as e:
        logger.error(f"Failed to queue debug task: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


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


@app.get("/api/celery/task/{task_id}", response_model=TaskStatus, tags=["celery"])
async def get_task_status(task_id: str):
    """
    Get the current status and details of a Celery task.

    Retrieves comprehensive information about a specific task including
    its current status, progress information, and results or errors.
    Useful for monitoring long-running tasks and debugging failures.

    Args:
        task_id: Unique identifier of the Celery task

    Returns:
        TaskStatus: Task status, progress, and result information

    Raises:
        HTTPException: If task status retrieval fails
    """
    try:
        task_result = celery_app.AsyncResult(task_id)

        response = {
            "task_id": task_id,
            "status": task_result.status,
            "ready": task_result.ready(),
            "successful": task_result.successful(),
            "failed": task_result.failed(),
        }

        if task_result.ready():
            if task_result.successful():
                response["result"] = task_result.result
            else:
                response["error"] = str(task_result.info)
        else:
            # Task is still running, get progress info
            if hasattr(task_result, "info") and task_result.info:
                response["info"] = task_result.info

        return TaskStatus(**response)

    except Exception as e:
        logger.error(f"Failed to get task status for {task_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/api/celery/active", response_model=ActiveTasksResponse, tags=["celery"])
async def get_active_tasks():
    """
    Get list of currently active Celery tasks.

    Returns information about all tasks currently being processed
    by Celery workers. Useful for monitoring system load and
    identifying long-running or stuck tasks.

    Returns:
        ActiveTasksResponse: List of active tasks with worker information

    Raises:
        HTTPException: If task list retrieval fails
    """
    try:
        inspector = celery_app.control.inspect()
        active_tasks = inspector.active()

        if not active_tasks:
            return ActiveTasksResponse(active_tasks=[])

        # Flatten the active tasks from all workers
        all_active = []
        for worker, tasks in active_tasks.items():
            for task in tasks:
                task["worker"] = worker
                all_active.append(task)

        return ActiveTasksResponse(active_tasks=all_active)

    except Exception as e:
        logger.error(f"Failed to get active tasks: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


# Media and Artifact API Endpoints
@app.get("/api/content/{content_id}/artifacts", tags=["content"])
async def get_content_artifacts(content_id: str):
    """
    Get all artifacts (audio, images, video) for a content item

    Returns file paths and metadata for all generated media files
    """
    try:
        content = db.get_content(content_id)
        if not content:
            raise HTTPException(status_code=404, detail="Content not found")

        # Get content item and related segments
        from .redis_repo import RedisRepository

        redis_repo = RedisRepository()
        content_item = redis_repo.get_content_item(content_id)
        audio_segments = redis_repo.get_audio_segments_for_content(content_id)
        image_segments = redis_repo.get_image_segments_for_content(content_id)

        artifacts = {
            "content_id": content_id,
            "audio_files": [],
            "image_files": [],
            "script_files": [],
            "raw_files": [],
        }

        # Add audio segments
        for segment in audio_segments:
            if segment.audio_file_path:
                artifacts["audio_files"].append(
                    {
                        "path": segment.audio_file_path,
                        "step": "tts_generation",
                        "type": "audio",
                        "sequence": segment.sequence_number,
                    }
                )

        # Add image segments
        for segment in image_segments:
            if segment.image_file_path:
                artifacts["image_files"].append(
                    {
                        "path": segment.image_file_path,
                        "step": "image_generation",
                        "type": "image",
                        "sequence": segment.sequence_number,
                    }
                )

        # Add content item files
        if content_item:
            if content_item.audio_file_path:
                artifacts["audio_files"].append(
                    {
                        "path": content_item.audio_file_path,
                        "step": "audio_assembly",
                        "type": "audio",
                        "sequence": 0,
                    }
                )
            if content_item.script:
                artifacts["script_files"].append(
                    {
                        "content": content_item.script,
                        "step": "script_generation",
                        "type": "script",
                    }
                )
            if content_item.raw_content:
                artifacts["raw_files"].append(
                    {
                        "content": content_item.raw_content,
                        "step": "content_processing",
                        "type": "raw_text",
                    }
                )

        return artifacts

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get artifacts for content {content_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/api/content/{content_id}/media/{media_type}/{filename}", tags=["content"])
async def serve_media_file(content_id: str, media_type: str, filename: str):
    """
    Serve media files (audio, images, video) for a content item

    Returns the actual media file content
    """
    try:
        from fastapi.responses import FileResponse
        from pathlib import Path
        import os

        # Get content to verify it exists
        content = db.get_content(content_id)
        if not content:
            raise HTTPException(status_code=404, detail="Content not found")

        # Construct file path based on the outputs structure
        file_path = Path(f"outputs/{content_id}/{media_type}/{filename}")

        if not file_path.exists():
            raise HTTPException(status_code=404, detail="Media file not found")

        # Determine media type for proper headers
        media_type_map = {
            "audio": "audio/mpeg",
            "images": "image/png",
            "video": "video/mp4",
            "content": "text/plain",
        }

        media_type_header = media_type_map.get(media_type, "application/octet-stream")

        return FileResponse(
            path=str(file_path), media_type=media_type_header, filename=filename
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Failed to serve media file {filename} for content {content_id}: {e}"
        )
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get(
    "/api/content/{content_id}/pipeline-status",
    response_model=dict,
    tags=["content"],
)
async def get_content_pipeline_status(content_id: str):
    """
    Get pipeline status for a content item

    Returns simplified processing status
    """
    try:
        from .redis_repo import RedisRepository

        redis_repo = RedisRepository()
        content_item = redis_repo.get_content_item(content_id)

        if not content_item:
            raise HTTPException(status_code=404, detail="Content item not found")

        return {
            "content_id": content_id,
            "status": content_item.status,
            "created_at": content_item.created_at,
            "updated_at": content_item.updated_at,
            "has_script": bool(content_item.script),
            "has_audio": bool(content_item.audio_file_path),
            "has_asr": bool(content_item.asr_data),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get pipeline status for content {content_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


# Pipeline API Endpoints
@app.post("/api/pipeline/process", response_model=TaskResponse, tags=["pipeline"])
async def content_pipeline_endpoint(request: ContentCreateRequest):
    """
    Trigger simplified content processing pipeline.

    Creates a new content item and queues it for processing through the
    simplified pipeline.

    Args:
        request: Content processing request with HN item ID and options

    Returns:
        TaskResponse: Processing status with content ID and task ID

    Raises:
        HTTPException: If processing initiation fails
    """
    try:
        # Create content item
        content_id = str(uuid.uuid4())
        now = datetime.now().isoformat()

        # Get HN item data
        from .redis_repo import RedisRepository

        redis_repo = RedisRepository()
        hn_data = redis_repo.get_hn_item(request.hn_item_id)

        if not hn_data:
            raise HTTPException(
                status_code=404, detail=f"HN item {request.hn_item_id} not found"
            )

        content_item = ContentItem(
            id=content_id,
            hn_item_id=request.hn_item_id,
            title=hn_data.get("title", f"Processing HN item {request.hn_item_id}"),
            url=hn_data.get("url", ""),
            post_text=hn_data.get("text", ""),
            status="queued",
            created_at=now,
            updated_at=now,
        )

        if not redis_repo.save_content_item(content_item):
            raise HTTPException(status_code=500, detail="Failed to store content")

        # Queue the processing task
        task = content_pipeline.apply_async(args=[content_id, request.options])

        logger.info(f"Content processing queued for {content_id} with task {task.id}")

        return TaskResponse(
            message="Content processing queued", task_id=task.id, status="queued"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to trigger content processing: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get(
    "/api/pipeline/status/{content_id}",
    response_model=dict,
    tags=["pipeline"],
)
async def get_pipeline_status(content_id: str):
    """
    Get simplified pipeline status for a content item.

    Returns basic status information for the content item.

    Args:
        content_id: Content item identifier

    Returns:
        dict: Simplified pipeline status

    Raises:
        HTTPException: If status retrieval fails
    """
    try:
        from .redis_repo import RedisRepository

        redis_repo = RedisRepository()
        content_item = redis_repo.get_content_item(content_id)

        if not content_item:
            raise HTTPException(status_code=404, detail="Content item not found")

        return {
            "content_id": content_id,
            "status": content_item.status,
            "created_at": content_item.created_at,
            "updated_at": content_item.updated_at,
            "has_script": bool(content_item.script),
            "has_audio": bool(content_item.audio_file_path),
            "has_asr": bool(content_item.asr_data),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get pipeline status for {content_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.post(
    "/api/enhanced-pipeline/retry/{content_id}/{step_name}",
    response_model=TaskResponse,
    tags=["enhanced-pipeline"],
)
async def retry_failed_pipeline_step(content_id: str, step_name: str):
    """
    Retry a failed pipeline step for a content item.

    Creates a new versioned segment and re-executes the failed step
            with proper dependency checking.

    Args:
        content_id: Content item identifier
        step_name: Name of the pipeline step to retry

    Returns:
        TaskResponse: Retry task status with task ID

    Raises:
        HTTPException: If retry initiation fails
    """
    try:
        # Get the failed segment ID first
        from .redis_repo import RedisRepository

        redis_repo = RedisRepository()
        manifest = redis_repo.get_or_create_manifest(content_id)
        segment = manifest.segments.get(step_name)

        if not segment or segment.status != "failed":
            raise HTTPException(
                status_code=400, detail=f"No failed segment found for step {step_name}"
            )

        # Queue the retry task
        task = retry_failed_segment.apply_async(args=[segment.segment_id])

        logger.info(
            f"Retry task queued for {content_id}:{step_name} with task {task.id}"
        )

        return TaskResponse(
            message=f"Retry task queued for step {step_name}",
            task_id=task.id,
            status="queued",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to trigger retry for {content_id}:{step_name}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.post(
    "/api/enhanced-pipeline/cleanup/{content_id}",
    response_model=TaskResponse,
    tags=["enhanced-pipeline"],
)
async def cleanup_old_pipeline_versions(
    content_id: str, keep_versions: int = Query(2, ge=1, le=10)
):
    """
    Clean up old versions of pipeline steps for a content item.

    Removes old completed segments while keeping the specified number
    of recent versions for each step.

    Args:
        content_id: Content item identifier
        keep_versions: Number of versions to keep for each step

    Returns:
        TaskResponse: Cleanup task status with task ID

    Raises:
        HTTPException: If cleanup initiation fails
    """
    try:
        # Queue the cleanup task
        task = cleanup_completed_segments.apply_async(args=[content_id, keep_versions])

        logger.info(f"Cleanup task queued for {content_id} with task {task.id}")

        return TaskResponse(
            message=f"Cleanup task queued (keeping {keep_versions} versions)",
            task_id=task.id,
            status="queued",
        )

    except Exception as e:
        logger.error(f"Failed to trigger cleanup for {content_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/api/pipeline/status", tags=["pipeline"])
async def get_pipeline_status():
    """
    Get status of the pipeline system.

    Returns:
        Dictionary with pipeline status information

    Raises:
        HTTPException: If status retrieval fails
    """
    try:
        return {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "message": "Pipeline system is running without locking",
        }

    except Exception as e:
        logger.error(f"Failed to get pipeline status: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


if __name__ == "__main__":
    import uvicorn

    # Get configuration from environment
    host = os.getenv("WEB_HOST", "0.0.0.0")
    port = int(os.getenv("WEB_PORT", "8000"))
    reload = os.getenv("WEB_RELOAD", "true").lower() == "true"

    logger.info(f"Starting server on {host}:{port}")

    uvicorn.run(
        "src.hnfm.web.server:app", host=host, port=port, reload=reload, log_level="info"
    )
