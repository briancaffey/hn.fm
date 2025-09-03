"""FastAPI routes for the web API"""

import logging
import os
from datetime import datetime
from fastapi import FastAPI, HTTPException, Depends
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import redis

from .models import (
    HealthCheck,
    ServiceStatus,
    ServicesStatusResponse,
    HNItem,
    ProcessedRun,
    RunsListResponse,
    CreateRunResponse,
    RunSummary,
)
from .celery_app import celery_app
from .tasks import hn_fetch_item, process_hn_item_run
from ..utils.hn_utils import (
    get_top_story_ids,
    get_item,
    list_items,
)
from ..utils.run_utils import (
    next_run_id,
    list_runs_for_item,
    get_run,
    delete_run,
)

logger = logging.getLogger(__name__)


def get_redis_client() -> redis.Redis:
    """Get Redis client for dependency injection"""
    redis_host = os.getenv("REDIS_HOST", "localhost")
    redis_port = int(os.getenv("REDIS_PORT", "6379"))
    redis_db = int(os.getenv("REDIS_DB", "0"))

    return redis.Redis(
        host=redis_host,
        port=redis_port,
        db=redis_db,
        decode_responses=False,  # Keep as bytes for JSON compatibility
    )


# Initialize FastAPI app
app = FastAPI(
    title="hn.fm API",
    description="API for managing Hacker News content pipeline",
    version="0.1.0",
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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

    return HealthCheck(
        status="healthy",
        timestamp=datetime.now(),
        version="0.1.0",
        redis_status="healthy",  # TOOD add redis db health check
    )


@app.get(
    "/api/services/status", response_model=ServicesStatusResponse, tags=["services"]
)
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


# HN API Endpoints
@app.post("/api/hn/queue-top", tags=["hacker-news"])
async def queue_top_stories(
    limit: int = 50, redis_client: redis.Redis = Depends(get_redis_client)
):
    """Queue top stories for processing"""
    try:
        # Get top story IDs
        top_ids = get_top_story_ids()

        # Take the first limit IDs
        ids_to_queue = top_ids[:limit]

        # Queue each ID using apply_async with explicit queue
        for item_id in ids_to_queue:
            hn_fetch_item.apply_async(args=[item_id], queue="hnfm_tasks")

        return {"queued_count": len(ids_to_queue), "ids": ids_to_queue, "limit": limit}

    except Exception as e:
        logger.error(f"Failed to queue top stories: {e}")
        raise HTTPException(status_code=500, detail="Failed to queue top stories")


@app.get("/api/hn/items", tags=["hacker-news"])
async def list_downloaded_items(
    offset: int = 0,
    limit: int = 50,
    redis_client: redis.Redis = Depends(get_redis_client),
):
    """List downloaded items with pagination"""
    try:
        items = list_items(offset=offset, limit=limit, redis_client=redis_client)

        return {
            "items": [item.model_dump() for item in items],
            "pagination": {"offset": offset, "limit": limit, "count": len(items)},
        }

    except Exception as e:
        logger.error(f"Failed to list items: {e}")
        raise HTTPException(status_code=500, detail="Failed to list items")


@app.get("/api/hn/items/{item_id}", tags=["hacker-news"])
async def get_single_item(
    item_id: int, redis_client: redis.Redis = Depends(get_redis_client)
):
    """Get a single item by ID"""
    try:
        item = get_item(item_id, redis_client=redis_client)

        if item is None:
            raise HTTPException(status_code=404, detail="Item not found")

        return item.model_dump()

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get item {item_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to get item")


# HN Item Runs API Endpoints
@app.post("/api/hn/items/{item_id}/runs", response_model=CreateRunResponse, tags=["hacker-news"])
async def create_and_queue_run(
    item_id: int, redis_client: redis.Redis = Depends(get_redis_client)
):
    """Create and queue a new run for an item"""
    try:
        # Get next run ID
        run = next_run_id(item_id, redis_client=redis_client)

        # Queue the task
        process_hn_item_run.apply_async(args=[item_id, run], queue="hnfm_tasks")

        return CreateRunResponse(
            item_id=item_id,
            run=run,
            status="queued"
        )

    except Exception as e:
        logger.error(f"Failed to create run for item {item_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to create run")


@app.get("/api/hn/items/{item_id}/runs", response_model=RunsListResponse, tags=["hacker-news"])
async def list_runs_for_item_endpoint(
    item_id: int,
    offset: int = 0,
    limit: int = 20,
    redis_client: redis.Redis = Depends(get_redis_client)
):
    """List runs for an item with pagination"""
    try:
        # Get run IDs
        run_ids = list_runs_for_item(
            item_id,
            redis_client=redis_client,
            offset=offset,
            limit=limit
        )

        # Fetch ProcessedRun objects and extract summaries
        runs = []
        for run_id in run_ids:
            processed_run = get_run(item_id, run_id, redis_client=redis_client)
            if processed_run:
                runs.append(RunSummary(
                    run=run_id,
                    summary=processed_run.summary
                ))

        return RunsListResponse(
            item_id=item_id,
            runs=runs,
            pagination={
                "offset": offset,
                "limit": limit,
                "count": len(runs)
            }
        )

    except Exception as e:
        logger.error(f"Failed to list runs for item {item_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to list runs")


@app.get("/api/hn/items/{item_id}/runs/{run}", response_model=ProcessedRun, tags=["hacker-news"])
async def get_single_run(
    item_id: int,
    run: int,
    redis_client: redis.Redis = Depends(get_redis_client)
):
    """Get a single run by item ID and run number"""
    try:
        processed_run = get_run(item_id, run, redis_client=redis_client)

        if processed_run is None:
            raise HTTPException(status_code=404, detail="Run not found")

        return processed_run

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get run {run} for item {item_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to get run")


# Error handlers
@app.exception_handler(404)
async def not_found_handler(request, exc):
    return JSONResponse(status_code=404, content={"detail": "Not found"})


@app.exception_handler(500)
async def internal_error_handler(request, exc):
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


@app.delete("/api/hn/items/{item_id}/runs/{run}", tags=["hacker-news"])
async def delete_single_run(
    item_id: int,
    run: int,
    redis_client: redis.Redis = Depends(get_redis_client)
):
    """Delete a single run by item ID and run number"""
    try:
        outputs_root = os.getenv("OUTPUTS_ROOT", "outputs")
        success = delete_run(item_id, run, redis_client=redis_client, outputs_root=outputs_root)

        if not success:
            raise HTTPException(status_code=404, detail="Run not found or could not be deleted")

        return {"message": f"Run {run} for item {item_id} deleted successfully", "success": True}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete run {run} for item {item_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete run")
