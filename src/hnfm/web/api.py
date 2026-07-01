"""FastAPI routes for the web API"""

import json
import logging
import os
from datetime import datetime
from fastapi import FastAPI, HTTPException, Body
from fastapi.responses import (
    JSONResponse,
    FileResponse,
    RedirectResponse,
    StreamingResponse,
)
from fastapi.middleware.cors import CORSMiddleware

from .models import (
    HealthCheck,
    ServiceStatus,
    ServicesStatusResponse,
    HNItem,
    ProcessedRun,
    RunsListResponse,
    CreateRunResponse,
    CreateRunRequest,
    RunSummary,
    Segment,
    SegmentSummary,
    SegmentsListResponse,
    CreateSegmentResponse,
    CreateSegmentRequest,
    DeleteSegmentResponse,
    BuildAudioResponse,
    SectionsListResponse,
    AllSegmentsListResponse,
)
from .celery_app import celery_app
from .tasks import (
    hn_fetch_item,
    process_hn_item_run,
    generate_segment,
    build_segment_audio,
    full_pipeline,
)
from ..utils.hn_utils import (
    get_top_story_ids,
    get_new_story_ids,
    get_item,
    list_items,
    count_items,
    exists_item,
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
    list_all_segments,
    count_all_segments,
    delete_segment,
)
from ..audio.audio_utils import (
    get_section_meta,
    list_section_numbers,
)

logger = logging.getLogger(__name__)


# Initialize FastAPI app
app = FastAPI(
    title="hn.fm API",
    description="API for managing Hacker News content pipeline",
    version="0.1.0",
)


@app.on_event("startup")
async def _init_db_schema():
    """Dev convenience: create tables if missing (see db.engine.ensure_schema)."""
    from ..db import ensure_schema

    ensure_schema()

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
    # Field is still named redis_status for frontend compatibility; it now
    # reports the Postgres connection.
    try:
        from sqlalchemy import text
        from ..db import db_session

        with db_session() as s:
            s.execute(text("SELECT 1"))
        db_status = "healthy"
    except Exception:
        db_status = "unhealthy"

    return HealthCheck(
        status="healthy",
        timestamp=datetime.now(),
        version="0.1.0",
        redis_status=db_status,
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


# Helper functions
def _serve_media(local_path: str, media_type: str, filename: str, proxy: bool = False):
    """Serve a media artifact, preferring the object store.

    Redirects to a presigned MinIO URL when the object exists (MinIO handles
    Range requests for video scrubbing). `proxy=True` streams through the API
    instead — needed for subtitles, where <track> requires same-origin/CORS.
    Falls back to the local outputs/ file during transition.
    """
    from ..storage import object_store

    key = object_store.key_for_path(local_path)
    if key and object_store.object_exists(key):
        if proxy:
            body, ctype = object_store.get_object_stream(key)
            return StreamingResponse(body.iter_chunks(), media_type=ctype)
        return RedirectResponse(object_store.presigned_url(key), status_code=307)

    if not os.path.exists(local_path):
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(path=local_path, media_type=media_type, filename=filename)


def queue_item_if_not_exists(item_id: int) -> dict:
    """Queue an item for processing only if it doesn't already exist in the database"""
    if exists_item(item_id):
        logger.info(f"Item {item_id} already exists, skipping queue")
        return {"status": "exists", "id": item_id}

    # Queue the task to fetch the item
    task = hn_fetch_item.apply_async(args=[item_id], queue="hnfm_tasks")
    logger.info(f"Item {item_id} queued for fetching")
    return {"status": "queued", "id": item_id, "task_id": task.id}


# HN API Endpoints
@app.post("/api/hn/queue-top", tags=["hacker-news"])
async def queue_top_stories(limit: int = 50):
    """Queue top stories for processing"""
    try:
        # Get top story IDs
        top_ids = get_top_story_ids()

        # Take the first limit IDs
        ids_to_queue = top_ids[:limit]

        # Queue each ID only if it doesn't exist
        queued_items = []
        skipped_items = []

        for item_id in ids_to_queue:
            result = queue_item_if_not_exists(item_id)
            if result["status"] == "queued":
                queued_items.append(item_id)
            else:
                skipped_items.append(item_id)

        return {
            "queued_count": len(queued_items),
            "skipped_count": len(skipped_items),
            "queued_ids": queued_items,
            "skipped_ids": skipped_items,
            "limit": limit,
        }

    except Exception as e:
        logger.error(f"Failed to queue top stories: {e}")
        raise HTTPException(status_code=500, detail="Failed to queue top stories")


@app.post("/api/hn/queue-new", tags=["hacker-news"])
async def queue_new_stories(limit: int = 50):
    """Queue new stories for processing"""
    try:
        # Get new story IDs
        new_ids = get_new_story_ids()

        # Take the first limit IDs
        ids_to_queue = new_ids[:limit]

        # Queue each ID only if it doesn't exist
        queued_items = []
        skipped_items = []

        for item_id in ids_to_queue:
            result = queue_item_if_not_exists(item_id)
            if result["status"] == "queued":
                queued_items.append(item_id)
            else:
                skipped_items.append(item_id)

        return {
            "queued_count": len(queued_items),
            "skipped_count": len(skipped_items),
            "queued_ids": queued_items,
            "skipped_ids": skipped_items,
            "limit": limit,
        }

    except Exception as e:
        logger.error(f"Failed to queue new stories: {e}")
        raise HTTPException(status_code=500, detail="Failed to queue new stories")


@app.post("/api/hn/process-item", tags=["hacker-news"])
async def process_single_item(item_id: int):
    """Process a single Hacker News item by ID"""
    try:
        # Queue the item only if it doesn't exist
        result = queue_item_if_not_exists(item_id)

        if result["status"] == "exists":
            return {
                "status": "exists",
                "item_id": item_id,
                "message": f"Item {item_id} already exists in database",
            }
        else:
            return {
                "status": "queued",
                "item_id": item_id,
                "task_id": result["task_id"],
                "message": f"Item {item_id} queued for fetching",
            }

    except Exception as e:
        logger.error(f"Failed to queue item {item_id} for processing: {e}")
        raise HTTPException(
            status_code=500, detail="Failed to queue item for processing"
        )


@app.get("/api/hn/items", tags=["hacker-news"])
async def list_downloaded_items(offset: int = 0, limit: int = 50):
    """List downloaded items with pagination"""
    try:
        items = list_items(offset=offset, limit=limit)

        return {
            "items": [item.model_dump() for item in items],
            "pagination": {
                "offset": offset,
                "limit": limit,
                "count": len(items),
                "total": count_items(),
            },
        }

    except Exception as e:
        logger.error(f"Failed to list items: {e}")
        raise HTTPException(status_code=500, detail="Failed to list items")


@app.get("/api/hn/items/{item_id}", tags=["hacker-news"])
async def get_single_item(item_id: int):
    """Get a single item by ID"""
    try:
        item = get_item(item_id)

        if item is None:
            raise HTTPException(status_code=404, detail="Item not found")

        return item.model_dump()

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get item {item_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to get item")


# Mission-control endpoints (stories with aggregates, generations, activity)
@app.get("/api/stories", tags=["stories"])
async def list_stories_endpoint(
    offset: int = 0,
    limit: int = 50,
    sort: str = "id",
    dir: str = "desc",
    q: str = None,
    has_video: bool = None,
    has_runs: bool = None,
):
    """Stories joined with generation aggregates — the mission-control table.

    Sort keys: id | time | score | comments | runs | segments | videos | latest.
    Pagination contract matches the rest of the API:
    {items, pagination: {offset, limit, count, total}}.
    """
    try:
        from ..db import repo

        rows, total = repo.list_stories(
            offset=offset, limit=limit, sort=sort, direction=dir,
            q=q, has_video=has_video, has_runs=has_runs,
        )
        return {
            "items": rows,
            "pagination": {
                "offset": offset, "limit": limit, "count": len(rows), "total": total,
            },
        }
    except Exception as e:
        logger.error(f"Failed to list stories: {e}")
        raise HTTPException(status_code=500, detail="Failed to list stories")


@app.get("/api/hn/items/{item_id}/generations", tags=["stories"])
async def list_generations_endpoint(item_id: int):
    """Every generation (segment) for a story across all runs, newest first,
    with run summaries and readiness flags — one flat table for the UI."""
    try:
        from ..db import repo

        return {"item_id": item_id, "generations": repo.list_generations(item_id)}
    except Exception as e:
        logger.error(f"Failed to list generations for item {item_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to list generations")


@app.get("/api/activity", tags=["activity"])
async def activity_endpoint():
    """Running + recently finished pipeline steps (sidebar activity light)."""
    try:
        from ..db import steps

        return steps.activity()
    except Exception as e:
        logger.error(f"activity failed: {e}")
        return {"running": [], "recent": []}


# Pipeline audit trail (steps) endpoints
@app.get(
    "/api/hn/items/{item_id}/runs/{run}/segments/{seg}/steps", tags=["steps"]
)
async def list_segment_steps(item_id: int, run: int, seg: int):
    """Full audit trail for a segment: every step with its inputs/outputs,
    timing, tokens, and status — including the run-scoped steps that fed it."""
    from ..db import steps

    step_list = steps.list_steps(item_id, run, seg)
    return {
        "item_id": item_id,
        "run": run,
        "seg": seg,
        "steps": step_list,
        "stale_count": sum(1 for s in step_list if s["status"] == "stale"),
        "rerunnable": {s["id"]: steps.rerun_supported(s["step_key"]) for s in step_list},
    }


@app.get("/api/hn/items/{item_id}/runs/{run}/steps", tags=["steps"])
async def list_run_steps(item_id: int, run: int):
    """Audit trail for a whole run (all segments)."""
    from ..db import steps

    return {"item_id": item_id, "run": run, "steps": steps.list_steps(item_id, run)}


@app.post("/api/steps/{step_id}/rerun", tags=["steps"])
async def rerun_step_endpoint(step_id: int, request: dict = Body(None)):
    """Re-execute a step, optionally with edited inputs.

    Body (all optional, step-kind dependent): {"prompt": …, "line_text": …,
    "text": …, "script": …, "regenerate_prompt": true}
    """
    from ..db import steps
    from .tasks import rerun_step

    step = steps.get_step(step_id)
    if not step:
        raise HTTPException(status_code=404, detail="Step not found")
    if not steps.rerun_supported(step["step_key"]):
        raise HTTPException(
            status_code=400,
            detail=f"Rerun not supported for step '{step['step_key']}'",
        )

    task = rerun_step.apply_async(
        args=[step_id], kwargs={"overrides": request or {}}, queue="hnfm_tasks"
    )
    return {
        "status": "queued",
        "step_id": step_id,
        "step_key": step["step_key"],
        "task_id": task.id,
    }


@app.post(
    "/api/hn/items/{item_id}/runs/{run}/segments/{seg}/rebuild-stale", tags=["steps"]
)
async def rebuild_stale_steps(item_id: int, run: int, seg: int):
    """Re-run what went stale. Today that resolves to reassembling the video
    (upstream reruns refresh stitch/ASR themselves); sequence frames are
    reported as skipped — regenerate the root image to refresh them."""
    from ..db import steps
    from .tasks import generate_segment_video

    stale = steps.list_stale(item_id, run, seg)
    stale_keys = sorted({s["step_key"] for s in stale})

    queued = []
    if any(k.startswith("video/") for k in stale_keys):
        task = generate_segment_video.apply_async(
            args=[item_id, run, seg], queue="hnfm_tasks"
        )
        queued.append({"step_key": "video/assemble", "task_id": task.id})

    skipped = [k for k in stale_keys if not k.startswith("video/")]
    return {"queued": queued, "skipped": skipped, "stale_keys": stale_keys}


@app.get("/api/metrics", tags=["metrics"])
async def list_metrics(limit: int = 200):
    """All pipeline metrics records (newest first) for the observability dashboard."""
    from ..utils import metrics
    try:
        return {"records": metrics.all_records(limit=limit)}
    except Exception as e:
        logger.error(f"metrics list failed: {e}")
        return {"records": []}


@app.get("/api/metrics/{item_id}/{run}/{seg}", tags=["metrics"])
async def get_metrics(item_id: int, run: int, seg: int):
    """Single run's metric breakdown."""
    from ..utils import metrics
    rec = metrics.get_record(item_id, run, seg)
    if not rec:
        raise HTTPException(status_code=404, detail="metrics not found")
    return rec


@app.post("/api/hn/single-task-pipeline", tags=["hacker-news"])
async def start_single_task_pipeline(request: dict = Body(...)):
    """Start the full pipeline as a single task for an item"""
    try:
        item_id = request.get("item_id")
        if not item_id:
            raise HTTPException(
                status_code=400, detail="item_id is required in request body"
            )

        # Optional per-take overrides (multi-take / multi-format)
        aspect_format = request.get("aspect_format")  # "16:9" | "1:1" | "9:16"
        style_theme = request.get("style_theme")  # art_direction theme key

        # Queue the full pipeline task
        task = full_pipeline.apply_async(
            args=[item_id],
            kwargs={"aspect_format": aspect_format, "style_theme": style_theme},
            queue="hnfm_tasks",
        )

        return {
            "status": "queued",
            "item_id": item_id,
            "aspect_format": aspect_format or "16:9",
            "style_theme": style_theme,
            "task_id": task.id,
            "message": f"Full pipeline queued for item {item_id}",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to queue full pipeline for item {item_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to queue full pipeline")


# HN Item Runs API Endpoints
@app.post(
    "/api/hn/items/{item_id}/runs",
    response_model=CreateRunResponse,
    tags=["hacker-news"],
)
async def create_and_queue_run(
    item_id: int,
    request: CreateRunRequest = Body(CreateRunRequest(continue_chain=False)),
):
    """Create and queue a new run for an item"""
    try:
        # Get next run ID
        run = next_run_id(item_id)

        # Queue the task with continue_chain parameter
        process_hn_item_run.apply_async(
            args=[item_id, run, request.continue_chain], queue="hnfm_tasks"
        )

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
):
    """List runs for an item with pagination"""
    try:
        # Get run IDs
        run_ids = list_runs_for_item(item_id, offset=offset, limit=limit)

        # Fetch ProcessedRun objects and extract summaries
        runs = []
        for run_id in run_ids:
            processed_run = get_run(item_id, run_id)
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
async def get_single_run(item_id: int, run: int):
    """Get a single run by item ID and run number"""
    try:
        processed_run = get_run(item_id, run)

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
async def delete_single_run(item_id: int, run: int):
    """Delete a single run by item ID and run number"""
    try:
        outputs_root = os.getenv("OUTPUTS_ROOT", "outputs")
        success = delete_run(item_id, run, outputs_root=outputs_root)

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
    item_id: int,
    run: int,
    request: CreateSegmentRequest = Body(CreateSegmentRequest(continue_chain=False)),
):
    """Create and queue a new segment for a run"""
    try:
        # Get next segment ID
        seg = next_seg_id(item_id, run)

        # Queue the task with continue_chain parameter
        generate_segment.apply_async(
            args=[item_id, run, seg, request.continue_chain], queue="hnfm_tasks"
        )

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
):
    """List segments for a run with pagination"""
    try:
        # Get segment IDs
        seg_ids = list_segments_for_run(item_id, run, offset=offset, limit=limit)

        # Fetch Segment objects and extract previews
        segments = []
        for seg_id in seg_ids:
            segment = get_segment(item_id, run, seg_id)
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
async def get_single_segment(item_id: int, run: int, seg: int):
    """Get a single segment by item ID, run number, and segment number"""
    try:
        segment = get_segment(item_id, run, seg)

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
async def delete_single_segment(item_id: int, run: int, seg: int):
    """Delete a single segment by item ID, run number, and segment number"""
    try:
        outputs_root = os.getenv("OUTPUTS_ROOT", "outputs")
        success = delete_segment(item_id, run, seg, outputs_root=outputs_root)

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


@app.get(
    "/api/segments",
    response_model=AllSegmentsListResponse,
    tags=["segments"],
)
async def list_all_segments_endpoint(offset: int = 0, limit: int = 50):
    """List all segments across all items and runs with pagination"""
    try:
        segments = list_all_segments(offset=offset, limit=limit)

        # Get total count for pagination
        total_count = count_all_segments()

        return AllSegmentsListResponse(
            segments=segments,
            pagination={
                "offset": offset,
                "limit": limit,
                "count": len(segments),
                "total": total_count,
            },
        )

    except Exception as e:
        logger.error(f"Failed to list all segments: {e}")
        raise HTTPException(status_code=500, detail="Failed to list segments")


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
async def list_segment_sections(item_id: int, run: int, seg: int):
    """List sections with metadata for a segment"""
    try:
        # Get section numbers in order
        section_numbers = list_section_numbers(item_id, run, seg)

        # Fetch section metadata
        sections = []
        for section_num in section_numbers:
            section_meta = get_section_meta(item_id, run, seg, section_num)
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


@app.get("/api/hn/items/{item_id}/runs/{run}/segments/{seg}/asr", tags=["audio"])
async def get_segment_asr(item_id: int, run: int, seg: int):
    """Get ASR data for a segment"""
    try:
        # Load Segment
        segment = get_segment(item_id, run, seg)

        if not segment:
            raise HTTPException(status_code=404, detail="Segment not found")

        # Check if ASR path exists and file is available
        if not segment.asr_json_path or not os.path.exists(segment.asr_json_path):
            raise HTTPException(status_code=404, detail="ASR not ready")

        # Read and return the ASR JSON
        with open(segment.asr_json_path, "r", encoding="utf-8") as f:
            asr_data = json.load(f)

        return {"item_id": item_id, "run": run, "seg": seg, "asr": asr_data}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get ASR for segment {item_id}:{run}:{seg}: {e}")
        raise HTTPException(status_code=500, detail="Failed to get ASR data")


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

        # Object store first, local outputs/ fallback
        return _serve_media(audio_path, "audio/wav", filename)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Failed to serve audio file {filename} for segment {item_id}:{run}:{seg}: {e}"
        )
        raise HTTPException(status_code=500, detail="Failed to serve audio file")


@app.get("/api/images/{item_id}/{run}/{seg}/{index}/{filename}")
async def serve_image_file(item_id: int, run: int, seg: int, index: int, filename: str):
    """Serve image files for segments"""
    try:
        from fastapi.responses import FileResponse

        # Get outputs directory
        outputs_dir = os.getenv("OUTPUTS_DIR", "/app/outputs")

        # Construct the file path
        if filename == "image.png":
            # Segment image
            image_path = os.path.join(
                outputs_dir,
                "hn",
                "item",
                str(item_id),
                "runs",
                str(run),
                "segments",
                str(seg),
                "images",
                str(index),
                "image.png",
            )
        else:
            raise HTTPException(status_code=400, detail="Invalid filename")

        # Object store first, local outputs/ fallback
        return _serve_media(image_path, "image/png", filename)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Failed to serve image file {filename} for segment {item_id}:{run}:{seg}:{index}: {e}"
        )
        raise HTTPException(status_code=500, detail="Failed to serve image file")


# Image endpoints


@app.post(
    "/api/hn/items/{item_id}/runs/{run}/segments/{seg}/images",
    response_model=dict,
    tags=["images"],
)
async def build_segment_images_endpoint(item_id: int, run: int, seg: int):
    """Trigger prompts+images for a segment (all)"""
    try:
        from .tasks import build_segment_images

        # Precheck: load Segment; if script empty → 400
        segment = get_segment(item_id, run, seg)
        if not segment:
            raise HTTPException(status_code=404, detail="Segment not found")

        if not segment.script.strip():
            raise HTTPException(status_code=400, detail="Script not ready")

        # Action: queue the task
        task = build_segment_images.apply_async(args=[item_id, run, seg, True])

        # Response
        return {
            "status": "queued",
            "item_id": item_id,
            "run": run,
            "seg": seg,
            "mode": "all",
            "task_id": task.id,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Failed to queue image generation for segment {item_id}:{run}:{seg}: {e}"
        )
        raise HTTPException(status_code=500, detail="Failed to queue image generation")


@app.get(
    "/api/hn/items/{item_id}/runs/{run}/segments/{seg}/images",
    response_model=dict,
    tags=["images"],
)
async def list_segment_images_endpoint(item_id: int, run: int, seg: int):
    """List images for a segment (ordered)"""
    try:
        from ..utils.segment_utils import list_segment_images, get_segment_image

        # Get list of image indexes
        indexes = list_segment_images(item_id, run, seg)

        # Get each image
        images = []
        for index in indexes:
            image = get_segment_image(item_id, run, seg, index)
            if image:
                images.append(
                    {
                        "index": image.index,
                        "line_text": image.line_text,
                        "prompt": image.prompt,
                        "image_path": image.image_path,
                        "start_ms": image.start_ms,
                        "duration_ms": image.duration_ms,
                    }
                )

        return {"item_id": item_id, "run": run, "seg": seg, "images": images}

    except Exception as e:
        logger.error(f"Failed to list images for segment {item_id}:{run}:{seg}: {e}")
        raise HTTPException(status_code=500, detail="Failed to list images")


@app.post(
    "/api/hn/items/{item_id}/runs/{run}/segments/{seg}/images/{index}",
    response_model=dict,
    tags=["images"],
)
async def rebuild_single_image_endpoint(
    item_id: int,
    run: int,
    seg: int,
    index: int,
    request_data: dict = Body(None),
):
    """Regenerate a single image (optional overrides)"""
    try:
        from .tasks import rebuild_single_image

        # Extract optional overrides from request body
        prompt_override = None
        line_override = None
        if request_data:
            prompt_override = request_data.get("prompt")
            line_override = request_data.get("line_text")

        # Action: queue the task
        task = rebuild_single_image.apply_async(
            args=[item_id, run, seg, index],
            kwargs={"prompt_override": prompt_override, "line_override": line_override},
        )

        # Response
        return {
            "status": "queued",
            "item_id": item_id,
            "run": run,
            "seg": seg,
            "index": index,
            "mode": "one",
            "task_id": task.id,
        }

    except Exception as e:
        logger.error(
            f"Failed to queue image regeneration for segment {item_id}:{run}:{seg}:{index}: {e}"
        )
        raise HTTPException(
            status_code=500, detail="Failed to queue image regeneration"
        )


# Video API Endpoints
@app.post(
    "/api/hn/items/{item_id}/runs/{run}/segments/{seg}/video",
    response_model=dict,
    tags=["video"],
)
async def generate_segment_video_endpoint(item_id: int, run: int, seg: int):
    """Generate video for a segment from audio, images, and timeline"""
    try:
        # Load segment and validate prerequisites
        segment = get_segment(item_id, run, seg)
        if not segment:
            raise HTTPException(status_code=404, detail="Segment not found")

        if not segment.script:
            raise HTTPException(
                status_code=400,
                detail="Segment script is empty - generate script first",
            )

        if not segment.audio_ready or not segment.audio_combined_path:
            raise HTTPException(
                status_code=400, detail="Segment audio not ready - generate audio first"
            )

        if not segment.images_ready:
            raise HTTPException(
                status_code=400,
                detail="Segment images not ready - generate images first",
            )

        # Import the task
        from .tasks import generate_segment_video

        # Queue the video generation task
        task = generate_segment_video.apply_async(args=[item_id, run, seg])

        logger.info(f"Queued video generation for segment {item_id}:{run}:{seg}")

        return {
            "status": "queued",
            "item_id": item_id,
            "run": run,
            "seg": seg,
            "task_id": task.id,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Failed to queue video generation for segment {item_id}:{run}:{seg}: {e}"
        )
        raise HTTPException(status_code=500, detail="Failed to queue video generation")


@app.get("/api/video/{item_id}/{run}/{seg}/{filename}")
async def serve_video_file(item_id: int, run: int, seg: int, filename: str):
    """Serve video files for segments"""
    try:
        from fastapi.responses import FileResponse

        # Get outputs directory
        outputs_dir = os.getenv("OUTPUTS_DIR", "/app/outputs")

        if filename == "segment.mp4":
            file_path = os.path.join(
                outputs_dir,
                "hn",
                "item",
                str(item_id),
                "runs",
                str(run),
                "segments",
                str(seg),
                "video",
                "segment.mp4",
            )
        elif filename == "captions.vtt":
            file_path = os.path.join(
                outputs_dir,
                "hn",
                "item",
                str(item_id),
                "runs",
                str(run),
                "segments",
                str(seg),
                "video",
                "captions.vtt",
            )
        else:
            raise HTTPException(status_code=404, detail="File not found")

        # Object store first, local outputs/ fallback. Subtitles are proxied
        # (not redirected) so <track> stays same-origin.
        if filename.endswith(".vtt"):
            return _serve_media(file_path, "text/vtt", filename, proxy=True)
        return _serve_media(file_path, "video/mp4", filename)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to serve video file {filename}: {e}")
        raise HTTPException(status_code=500, detail="Failed to serve video file")
