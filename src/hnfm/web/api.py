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
    Segment,
    SegmentSummary,
    SegmentsListResponse,
    CreateSegmentResponse,
    DeleteSegmentResponse,
    BuildAudioResponse,
    SectionsListResponse,
)
from .celery_app import celery_app
from .tasks import (
    hn_fetch_item,
    process_hn_item_run,
    generate_segment,
    build_segment_audio,
)
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
from ..utils.segment_utils import (
    next_seg_id,
    get_segment,
    list_segments_for_run,
    delete_segment,
)
from ..audio.audio_utils import (
    get_section_meta,
    list_section_numbers,
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
@app.post(
    "/api/hn/items/{item_id}/runs",
    response_model=CreateRunResponse,
    tags=["hacker-news"],
)
async def create_and_queue_run(
    item_id: int, redis_client: redis.Redis = Depends(get_redis_client)
):
    """Create and queue a new run for an item"""
    try:
        # Get next run ID
        run = next_run_id(item_id, redis_client=redis_client)

        # Queue the task
        process_hn_item_run.apply_async(args=[item_id, run], queue="hnfm_tasks")

        return CreateRunResponse(item_id=item_id, run=run, status="queued")

    except Exception as e:
        logger.error(f"Failed to create run for item {item_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to create run")


@app.get(
    "/api/hn/items/{item_id}/runs",
    response_model=RunsListResponse,
    tags=["hacker-news"],
)
async def list_runs_for_item_endpoint(
    item_id: int,
    offset: int = 0,
    limit: int = 20,
    redis_client: redis.Redis = Depends(get_redis_client),
):
    """List runs for an item with pagination"""
    try:
        # Get run IDs
        run_ids = list_runs_for_item(
            item_id, redis_client=redis_client, offset=offset, limit=limit
        )

        # Fetch ProcessedRun objects and extract summaries
        runs = []
        for run_id in run_ids:
            processed_run = get_run(item_id, run_id, redis_client=redis_client)
            if processed_run:
                runs.append(RunSummary(run=run_id, summary=processed_run.summary))

        return RunsListResponse(
            item_id=item_id,
            runs=runs,
            pagination={"offset": offset, "limit": limit, "count": len(runs)},
        )

    except Exception as e:
        logger.error(f"Failed to list runs for item {item_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to list runs")


@app.get(
    "/api/hn/items/{item_id}/runs/{run}",
    response_model=ProcessedRun,
    tags=["hacker-news"],
)
async def get_single_run(
    item_id: int, run: int, redis_client: redis.Redis = Depends(get_redis_client)
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
    item_id: int, run: int, redis_client: redis.Redis = Depends(get_redis_client)
):
    """Delete a single run by item ID and run number"""
    try:
        outputs_root = os.getenv("OUTPUTS_ROOT", "outputs")
        success = delete_run(
            item_id, run, redis_client=redis_client, outputs_root=outputs_root
        )

        if not success:
            raise HTTPException(
                status_code=404, detail="Run not found or could not be deleted"
            )

        return {
            "message": f"Run {run} for item {item_id} deleted successfully",
            "success": True,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete run {run} for item {item_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete run")


# HN Item Segments API Endpoints
@app.post(
    "/api/hn/items/{item_id}/runs/{run}/segments",
    response_model=CreateSegmentResponse,
    tags=["hacker-news"],
)
async def create_and_queue_segment(
    item_id: int, run: int, redis_client: redis.Redis = Depends(get_redis_client)
):
    """Create and queue a new segment for a run"""
    try:
        # Get next segment ID
        seg = next_seg_id(item_id, run, redis_client=redis_client)

        # Queue the task
        generate_segment.apply_async(args=[item_id, run, seg], queue="hnfm_tasks")

        return CreateSegmentResponse(item_id=item_id, run=run, seg=seg, status="queued")

    except Exception as e:
        logger.error(f"Failed to create segment for item {item_id}, run {run}: {e}")
        raise HTTPException(status_code=500, detail="Failed to create segment")


@app.get(
    "/api/hn/items/{item_id}/runs/{run}/segments",
    response_model=SegmentsListResponse,
    tags=["hacker-news"],
)
async def list_segments_for_run_endpoint(
    item_id: int,
    run: int,
    offset: int = 0,
    limit: int = 20,
    redis_client: redis.Redis = Depends(get_redis_client),
):
    """List segments for a run with pagination"""
    try:
        # Get segment IDs
        seg_ids = list_segments_for_run(
            item_id, run, redis_client=redis_client, offset=offset, limit=limit
        )

        # Fetch Segment objects and extract previews
        segments = []
        for seg_id in seg_ids:
            segment = get_segment(item_id, run, seg_id, redis_client=redis_client)
            if segment:
                script_preview = (
                    segment.script[:200] + "..."
                    if len(segment.script) > 200
                    else segment.script
                )
                segments.append(
                    SegmentSummary(seg=seg_id, script_preview=script_preview)
                )

        return SegmentsListResponse(
            item_id=item_id,
            run=run,
            segments=segments,
            pagination={"offset": offset, "limit": limit, "count": len(segments)},
        )

    except Exception as e:
        logger.error(f"Failed to list segments for item {item_id}, run {run}: {e}")
        raise HTTPException(status_code=500, detail="Failed to list segments")


@app.get(
    "/api/hn/items/{item_id}/runs/{run}/segments/{seg}",
    response_model=Segment,
    tags=["hacker-news"],
)
async def get_single_segment(
    item_id: int,
    run: int,
    seg: int,
    redis_client: redis.Redis = Depends(get_redis_client),
):
    """Get a single segment by item ID, run number, and segment number"""
    try:
        segment = get_segment(item_id, run, seg, redis_client=redis_client)

        if segment is None:
            raise HTTPException(status_code=404, detail="Segment not found")

        return segment

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get segment {seg} for item {item_id}, run {run}: {e}")
        raise HTTPException(status_code=500, detail="Failed to get segment")


@app.delete(
    "/api/hn/items/{item_id}/runs/{run}/segments/{seg}",
    response_model=DeleteSegmentResponse,
    tags=["hacker-news"],
)
async def delete_single_segment(
    item_id: int,
    run: int,
    seg: int,
    redis_client: redis.Redis = Depends(get_redis_client),
):
    """Delete a single segment by item ID, run number, and segment number"""
    try:
        outputs_root = os.getenv("OUTPUTS_ROOT", "outputs")
        success = delete_segment(
            item_id, run, seg, redis_client=redis_client, outputs_root=outputs_root
        )

        if not success:
            raise HTTPException(
                status_code=404, detail="Segment not found or could not be deleted"
            )

        return DeleteSegmentResponse(
            item_id=item_id, run=run, seg=seg, status="deleted"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Failed to delete segment {seg} for item {item_id}, run {run}: {e}"
        )
        raise HTTPException(status_code=500, detail="Failed to delete segment")


# Audio API Endpoints
@app.post(
    "/api/hn/items/{item_id}/runs/{run}/segments/{seg}/audio",
    response_model=BuildAudioResponse,
    tags=["audio"],
)
async def build_segment_audio_all(item_id: int, run: int, seg: int):
    """Build or rebuild all sections and combined audio for a segment"""
    try:
        # Queue the task to build all sections
        build_segment_audio.apply_async(
            args=[item_id, run, seg], kwargs={"mode": "all"}, queue="hnfm_tasks"
        )

        return BuildAudioResponse(
            status="queued", item_id=item_id, run=run, seg=seg, mode="all"
        )

    except Exception as e:
        logger.error(
            f"Failed to queue audio build for segment {item_id}:{run}:{seg}: {e}"
        )
        raise HTTPException(status_code=500, detail="Failed to queue audio build")


@app.post(
    "/api/hn/items/{item_id}/runs/{run}/segments/{seg}/sections/{section}/audio",
    response_model=BuildAudioResponse,
    tags=["audio"],
)
async def build_segment_audio_one(
    item_id: int, run: int, seg: int, section: int, text_override: str = None
):
    """Regenerate one section (optionally with new text)"""
    try:
        # Prepare kwargs
        kwargs = {"mode": "one", "section": section}
        if text_override:
            kwargs["text_override"] = text_override

        # Queue the task to build one section
        build_segment_audio.apply_async(
            args=[item_id, run, seg], kwargs=kwargs, queue="hnfm_tasks"
        )

        return BuildAudioResponse(
            status="queued",
            item_id=item_id,
            run=run,
            seg=seg,
            mode="one",
            section=section,
        )

    except Exception as e:
        logger.error(
            f"Failed to queue audio build for section {item_id}:{run}:{seg}:{section}: {e}"
        )
        raise HTTPException(status_code=500, detail="Failed to queue audio build")


@app.get(
    "/api/hn/items/{item_id}/runs/{run}/segments/{seg}/sections",
    response_model=SectionsListResponse,
    tags=["audio"],
)
async def list_segment_sections(
    item_id: int,
    run: int,
    seg: int,
    redis_client: redis.Redis = Depends(get_redis_client),
):
    """List sections with metadata for a segment"""
    try:
        # Get section numbers in order
        section_numbers = list_section_numbers(
            item_id, run, seg, redis_client=redis_client
        )

        # Fetch section metadata
        sections = []
        for section_num in section_numbers:
            section_meta = get_section_meta(
                item_id, run, seg, section_num, redis_client=redis_client
            )
            if section_meta:
                sections.append(
                    {
                        "section": section_meta.section,
                        "text": section_meta.text,
                        "audio_path": section_meta.audio_path,
                        "cleaned": section_meta.cleaned,
                        "duration_ms": section_meta.duration_ms,
                    }
                )

        return SectionsListResponse(
            item_id=item_id, run=run, seg=seg, sections=sections
        )

    except Exception as e:
        logger.error(f"Failed to list sections for segment {item_id}:{run}:{seg}: {e}")
        raise HTTPException(status_code=500, detail="Failed to list sections")


@app.get("/api/audio/{item_id}/{run}/{seg}/{filename}")
async def serve_audio_file(item_id: int, run: int, seg: int, filename: str):
    """Serve audio files for segments and sections"""
    try:
        from fastapi.responses import FileResponse

        # Get outputs directory
        outputs_dir = os.getenv("OUTPUTS_DIR", "/app/outputs")

        # Construct the file path
        if filename == "segment.wav":
            # Combined segment audio
            audio_path = os.path.join(
                outputs_dir,
                "hn",
                "item",
                str(item_id),
                "runs",
                str(run),
                "segments",
                str(seg),
                "audio",
                "segment.wav",
            )
        elif filename.startswith("section_") and filename.endswith(".wav"):
            # Individual section audio
            section_num = filename.replace("section_", "").replace(".wav", "")
            audio_path = os.path.join(
                outputs_dir,
                "hn",
                "item",
                str(item_id),
                "runs",
                str(run),
                "segments",
                str(seg),
                "audio",
                "sections",
                section_num,
                "audio.wav",
            )
        else:
            raise HTTPException(status_code=400, detail="Invalid filename")

        # Check if file exists
        if not os.path.exists(audio_path):
            raise HTTPException(status_code=404, detail="Audio file not found")

        # Return the file
        return FileResponse(path=audio_path, media_type="audio/wav", filename=filename)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Failed to serve audio file {filename} for segment {item_id}:{run}:{seg}: {e}"
        )
        raise HTTPException(status_code=500, detail="Failed to serve audio file")
