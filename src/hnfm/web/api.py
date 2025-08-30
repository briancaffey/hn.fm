"""FastAPI routes for the web API"""

import logging
import uuid
from datetime import datetime
from typing import List, Optional
from fastapi import FastAPI, HTTPException, Query, Depends
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .models import (
    ContentItem, ContentListResponse, ContentCreateRequest,
    ContentUpdateRequest, PipelineStatus, HealthCheck, ServiceStatus, ServicesStatusResponse
)
from .database import ContentDatabase

logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="hn.fm API",
    description="API for managing Hacker News content pipeline",
    version="0.1.0"
)

# Initialize database
db = ContentDatabase()

# Templates for web UI
templates = Jinja2Templates(directory="src/hnfm/web/templates")

# Mount static files
app.mount("/static", StaticFiles(directory="src/hnfm/web/static"), name="static")


@app.get("/", response_class=HTMLResponse)
async def root(request):
    """Serve the main web UI"""
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/services", response_class=HTMLResponse)
async def services_page(request):
    """Serve the services status page"""
    return templates.TemplateResponse("services.html", {"request": request})


@app.get("/api/health", response_model=HealthCheck)
async def health_check():
    """Health check endpoint"""
    redis_status = "healthy" if db.health_check() else "unhealthy"

    return HealthCheck(
        status="healthy",
        timestamp=datetime.now(),
        version="0.1.0",
        redis_status=redis_status
    )


@app.get("/api/services/status", response_model=ServicesStatusResponse)
async def get_services_status():
    """Get status of all services"""
    try:
        from ..utils.system_checker import SystemChecker

        system_checker = SystemChecker()
        all_healthy, service_statuses = system_checker.check_all_services()

        # Convert ServiceStatus dataclass to our Pydantic model
        services = []
        for status in service_statuses:
            services.append(ServiceStatus(
                name=status.name,
                url=status.url,
                status=status.status,
                response_time=status.response_time,
                error_message=status.error_message,
                details=status.details
            ))

        return ServicesStatusResponse(
            all_healthy=all_healthy,
            services=services,
            timestamp=datetime.now()
        )

    except Exception as e:
        logger.error(f"Failed to get services status: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/api/content", response_model=ContentListResponse)
async def list_content(
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(20, ge=1, le=100, description="Items per page"),
    content_type: Optional[str] = Query(None, description="Filter by content type"),
    status: Optional[str] = Query(None, description="Filter by status")
):
    """List content items with pagination and filtering"""
    try:
        result = db.list_content(page, per_page, content_type, status)
        return ContentListResponse(**result)
    except Exception as e:
        logger.error(f"Failed to list content: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/api/content/{content_id}", response_model=ContentItem)
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


@app.post("/api/content", response_model=ContentItem)
async def create_content(request: ContentCreateRequest):
    """Create a new content item"""
    try:
        content_id = str(uuid.uuid4())
        now = datetime.now()

        content_data = {
            'id': content_id,
            'title': f"Processing: {request.url}",
            'url': request.url,
            'content_type': request.content_type,
            'status': 'pending',
            'created_at': now,
            'updated_at': now,
            'metadata': request.options,
            'processing_steps': [],
            'errors': []
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


@app.put("/api/content/{content_id}", response_model=ContentItem)
async def update_content(content_id: str, request: ContentUpdateRequest):
    """Update a content item"""
    try:
        updates = {}
        if request.title is not None:
            updates['title'] = request.title
        if request.status is not None:
            updates['status'] = request.status
        if request.metadata is not None:
            updates['metadata'] = request.metadata

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


@app.delete("/api/content/{content_id}")
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


@app.get("/api/pipeline/status", response_model=PipelineStatus)
async def get_pipeline_status():
    """Get pipeline status information"""
    try:
        status_data = db.get_pipeline_status()
        return PipelineStatus(**status_data)
    except Exception as e:
        logger.error(f"Failed to get pipeline status: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.post("/api/pipeline/process")
async def process_content(request: ContentCreateRequest):
    """Trigger content processing pipeline"""
    try:
        # Create content item
        content_id = str(uuid.uuid4())
        now = datetime.now()

        content_data = {
            'id': content_id,
            'title': f"Processing: {request.url}",
            'url': request.url,
            'content_type': request.content_type,
            'status': 'processing',
            'created_at': now,
            'updated_at': now,
            'metadata': request.options,
            'processing_steps': ['created'],
            'errors': []
        }

        if not db.store_content(content_id, content_data):
            raise HTTPException(status_code=500, detail="Failed to store content")

        # TODO: Trigger actual pipeline processing
        # This would integrate with your existing pipeline
        logger.info(f"Content processing triggered for {content_id}")

        return {
            "message": "Content processing started",
            "content_id": content_id,
            "status": "processing"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to trigger content processing: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


# Error handlers
@app.exception_handler(404)
async def not_found_handler(request, exc):
    return {"detail": "Not found"}


@app.exception_handler(500)
async def internal_error_handler(request, exc):
    return {"detail": "Internal server error"}
