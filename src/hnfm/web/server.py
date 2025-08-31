"""FastAPI server entry point for hn.fm web interface"""

import os
import logging
import json
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi import Request
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
    EnhancedPipelineStatus,
)
from .celery_app import celery_app
from .tasks import debug_task, process_content, full_pipeline
from .enhanced_tasks import (
    enhanced_content_pipeline,
    get_enhanced_pipeline_status,
    retry_failed_segment,
    cleanup_completed_segments,
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

# Mount static files
app.mount("/static", StaticFiles(directory="src/hnfm/web/static"), name="static")

# Templates
templates = Jinja2Templates(directory="src/hnfm/web/templates")


@app.get("/")
async def root(request: Request):
    """Serve the main dashboard"""
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/services")
async def services_page(request: Request):
    """Serve the services status page"""
    return templates.TemplateResponse("services.html", {"request": request})


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

        # Get enhanced pipeline status if available
        from .redis_repo import RedisRepository

        redis_repo = RedisRepository()
        enhanced_status = redis_repo.get_enhanced_pipeline_status(content_id)

        artifacts = {
            "content_id": content_id,
            "audio_files": [],
            "image_files": [],
            "video_files": [],
            "script_files": [],
            "raw_files": [],
        }

        # Extract artifacts from enhanced pipeline if available
        if enhanced_status:
            for step_status in enhanced_status.step_statuses:
                if step_status.status == "completed":
                    # Get segment artifacts
                    manifest = redis_repo.get_or_create_manifest(content_id)
                    segment = manifest.segments.get(step_status.step_name)
                    if segment and segment.artifacts:
                        if step_status.step_name == "tts_generation":
                            if "audio_path" in segment.artifacts:
                                artifacts["audio_files"].append(
                                    {
                                        "path": segment.artifacts["audio_path"],
                                        "step": step_status.step_name,
                                        "type": "audio",
                                    }
                                )
                        elif step_status.step_name == "image_generation":
                            if "image_paths" in segment.artifacts:
                                for img_path in segment.artifacts["image_paths"]:
                                    artifacts["image_files"].append(
                                        {
                                            "path": img_path,
                                            "step": step_status.step_name,
                                            "type": "image",
                                        }
                                    )
                        elif step_status.step_name == "video_generation":
                            if "video_path" in segment.artifacts:
                                artifacts["video_files"].append(
                                    {
                                        "path": segment.artifacts["video_path"],
                                        "step": step_status.step_name,
                                        "type": "video",
                                    }
                                )
                        elif step_status.step_name == "script_generation":
                            if "script_path" in segment.artifacts:
                                artifacts["script_files"].append(
                                    {
                                        "path": segment.artifacts["script_path"],
                                        "step": step_status.step_name,
                                        "type": "script",
                                    }
                                )
                        elif step_status.step_name == "firecrawl_content":
                            if "raw_content" in segment.artifacts:
                                artifacts["raw_files"].append(
                                    {
                                        "content": segment.artifacts["raw_content"],
                                        "step": step_status.step_name,
                                        "type": "raw_text",
                                    }
                                )

        # Fallback to basic content data if enhanced status not available
        if not enhanced_status:
            if content.get("audio_path"):
                artifacts["audio_files"].append(
                    {"path": content["audio_path"], "step": "legacy", "type": "audio"}
                )
            if content.get("video_path"):
                artifacts["video_files"].append(
                    {"path": content["video_path"], "step": "legacy", "type": "video"}
                )
            if content.get("image_paths"):
                for img_path in content["image_paths"]:
                    artifacts["image_files"].append(
                        {"path": img_path, "step": "legacy", "type": "image"}
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
    response_model=EnhancedPipelineStatus,
    tags=["content"],
)
async def get_content_pipeline_status(content_id: str):
    """
    Get pipeline status for a content item

    Returns detailed step-by-step processing status
    """
    try:
        from .redis_repo import RedisRepository

        redis_repo = RedisRepository()
        status = redis_repo.get_enhanced_pipeline_status(content_id)

        if not status:
            raise HTTPException(
                status_code=404, detail="Pipeline status not found for content"
            )

        return status

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get pipeline status for content {content_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


# Pipeline API Endpoints
@app.post("/api/pipeline/process", response_model=TaskResponse, tags=["pipeline"])
async def content_pipeline_endpoint(request: ContentCreateRequest):
    """
    Trigger enhanced content processing pipeline with Redis-first design.

    Creates a new content item and queues it for processing through the
    enhanced pipeline with service locking, versioned segments, and
    comprehensive state tracking.

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

        # Queue the processing task
        task = enhanced_content_pipeline.apply_async(args=[content_id, request.options])

        logger.info(f"Content processing queued for {content_id} with task {task.id}")

        return TaskResponse(
            message="Content processing queued", task_id=task.id, status="queued"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to trigger enhanced content processing: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get(
    "/api/pipeline/status/{content_id}",
    response_model=EnhancedPipelineStatus,
    tags=["pipeline"],
)
async def get_pipeline_status(content_id: str):
    """
    Get enhanced pipeline status for a content item.

    Returns comprehensive status information including step-level details,
    progress tracking, and versioned segment information.

    Args:
        content_id: Content item identifier

    Returns:
        EnhancedPipelineStatus: Enhanced pipeline status with step details

    Raises:
        HTTPException: If status retrieval fails
    """
    try:
        # Queue the status retrieval task
        task = get_enhanced_pipeline_status.apply_async(args=[content_id])

        # Wait for the task to complete (synchronous for now)
        result = task.get(timeout=30)

        if result and result.get("status") == "success":
            return EnhancedPipelineStatus(**result["pipeline_status"])
        else:
            raise HTTPException(
                status_code=500, detail="Failed to retrieve pipeline status"
            )

    except Exception as e:
        logger.error(f"Failed to get enhanced pipeline status for {content_id}: {e}")
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
    with proper service locking and dependency checking.

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


@app.get("/api/pipeline/service-locks", tags=["pipeline"])
async def get_service_lock_status():
    """
    Get status of all service locks.

    Returns information about which external services are currently
    locked and their lock details.

    Returns:
        Dictionary with service lock status information

    Raises:
        HTTPException: If lock status retrieval fails
    """
    try:
        from ..pipeline.enhanced_pipeline_manager import EnhancedPipelineManager

        # Create enhanced pipeline manager
        pipeline = EnhancedPipelineManager(redis_integration=True)

        # Get service lock status
        lock_status = pipeline.get_service_lock_status()

        # Debug: Log the structure of lock_status
        logger.info(f"Lock status type: {type(lock_status)}")
        logger.info(
            f"Lock status keys: {list(lock_status.keys()) if isinstance(lock_status, dict) else 'Not a dict'}"
        )

        # Ensure all datetime objects are converted to strings
        def convert_datetime_to_string(obj, path=""):
            if isinstance(obj, dict):
                result = {}
                for k, v in obj.items():
                    new_path = f"{path}.{k}" if path else k
                    result[k] = convert_datetime_to_string(v, new_path)
                return result
            elif isinstance(obj, list):
                result = []
                for i, v in enumerate(obj):
                    new_path = f"{path}[{i}]" if path else f"[{i}]"
                    result.append(convert_datetime_to_string(v, new_path))
                return result
            elif hasattr(obj, "isoformat"):  # datetime objects
                logger.info(
                    f"Found datetime object at {path}: {obj} (type: {type(obj)})"
                )
                return obj.isoformat()
            else:
                return obj

        # Convert any datetime objects to strings
        serializable_status = convert_datetime_to_string(lock_status)

        # Test JSON serialization before returning
        try:
            json.dumps(serializable_status)
            logger.info("JSON serialization successful")
        except Exception as e:
            logger.error(f"JSON serialization failed: {e}")

            # Find the problematic object
            def find_datetime_objects(obj, path=""):
                if isinstance(obj, dict):
                    for k, v in obj.items():
                        find_datetime_objects(v, f"{path}.{k}")
                elif isinstance(obj, list):
                    for i, v in enumerate(obj):
                        find_datetime_objects(v, f"{path}[{i}]")
                elif hasattr(obj, "__class__") and "datetime" in str(obj.__class__):
                    logger.error(
                        f"Found datetime object at {path}: {obj} (type: {type(obj)})"
                    )

            find_datetime_objects(serializable_status)
            raise

        return serializable_status

    except Exception as e:
        logger.error(f"Failed to get service lock status: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.post("/api/pipeline/force-release-lock/{service_name}", tags=["pipeline"])
async def force_release_service_lock(service_name: str):
    """
    Force release a service lock (use with caution).

    Releases a service lock that may be stuck or orphaned.
    This should only be used in emergency situations.

    Args:
        service_name: Name of the service whose lock should be released

    Returns:
        Dictionary with lock release status

    Raises:
        HTTPException: If lock release fails
    """
    try:
        from ..pipeline.enhanced_pipeline_manager import EnhancedPipelineManager

        # Create enhanced pipeline manager
        pipeline = EnhancedPipelineManager(redis_integration=True)

        # Force release the lock
        result = pipeline.force_release_service_lock(service_name)

        if "error" in result:
            raise HTTPException(status_code=500, detail=result["error"])

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to force release lock for {service_name}: {e}")
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
