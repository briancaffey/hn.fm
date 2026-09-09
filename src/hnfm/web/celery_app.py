"""Celery application configuration for hn.fm"""

import os
import logging
from celery import Celery, Task
from celery.signals import worker_ready

logger = logging.getLogger(__name__)

# Get Redis configuration from environment
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = os.getenv("REDIS_PORT", "6379")
REDIS_DB = os.getenv("REDIS_DB", "0")
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", "")

# Build Redis URLs
if REDIS_PASSWORD:
    broker_url = f"redis://:{REDIS_PASSWORD}@{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}"
    result_backend = f"redis://:{REDIS_PASSWORD}@{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}"
else:
    broker_url = f"redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}"
    result_backend = f"redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}"

class RecordedTask(Task):
    """Base task that leaves a trace when it dies outside a `step()` block.

    A task raising before its first `steps.step()` context opens produces no
    pipeline_steps row at all, so `/api/activity` and the Live page report a
    clean run while the only evidence sits in worker stdout. Recording it here
    catches every task without touching a single task body.
    """

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        try:
            from ..db import steps

            # Recorded even when a step block already logged an error: a
            # failing step does not always kill its task (see `soft_fail`), so
            # "the task died" is a separate fact. `stage="task"` keeps the two
            # distinguishable.
            steps.record_task_failure(
                self.name, args or (), kwargs or {}, str(exc),
                traceback=str(einfo) if einfo else "",
            )
        except Exception as e:  # never mask the original failure
            logger.warning(f"task failure recording failed: {e}")
        return super().on_failure(exc, task_id, args, kwargs, einfo)


# Create Celery app
celery_app = Celery(
    "hnfm",
    broker=broker_url,
    backend=result_backend,
    include=["src.hnfm.web.tasks"],  # Include our HN tasks
    task_cls=RecordedTask,
)

# Log the configuration for debugging
logger.info(f"Celery app created with broker: {broker_url}")
logger.info(f"Celery app created with backend: {result_backend}")
logger.info(f"Celery app includes: {celery_app.conf.include}")

# Import tasks AFTER creating the app to ensure they're registered
try:
    from . import tasks

    logger.info("Tasks imported successfully")
    logger.info(f"Available tasks after import: {list(celery_app.tasks.keys())}")
except ImportError as e:
    logger.error(f"Failed to import tasks: {e}")

# Celery configuration
celery_app.conf.update(
    # Task serialization
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    # Task execution
    task_always_eager=os.getenv("CELERY_ALWAYS_EAGER", "false").lower()
    == "true",  # Set to True for testing
    task_eager_propagates=True,
    # Result backend
    result_expires=3600,  # Results expire after 1 hour
    # Worker configuration
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=1000,
    # Task timeouts
    task_soft_time_limit=300,  # 5 minutes soft limit
    task_time_limit=600,  # 10 minutes hard limit
    # Retry configuration
    task_acks_late=True,
    worker_disable_rate_limits=False,
    # Monitoring
    worker_send_task_events=True,
    task_send_sent_event=True,
    # Redis specific
    broker_connection_retry_on_startup=True,
    broker_connection_max_retries=10,
    # Task result
    task_ignore_result=False,
    task_store_errors_even_if_ignored=True,
)

# Queue routing. One queue and one worker slot meant a 4-second scrape sat
# behind a 3-hour full_pipeline: during a diagnostic run, five generation tasks
# waited ~30 minutes for 46 ingest tasks to drain. Splitting by cost class lets
# each kind of work proceed at its own pace.
#
# Routing lives here rather than at the ~22 apply_async call sites so there is
# one place to reason about it. A task's queue is a property of the task, not
# of whoever happens to enqueue it.
QUEUE_INGEST = "hnfm_ingest"    # network-bound: scrape + a few LLM calls
QUEUE_TRIAGE = "hnfm_triage"    # LLM-bound scoring and briefs
QUEUE_RENDER = "hnfm_render"    # GPU/ffmpeg: images, video, audio
QUEUE_DIGEST = "hnfm_digest"    # long, self-contained, runs on a schedule
QUEUE_LEGACY = "hnfm_tasks"     # drained by the render worker, see below

celery_app.conf.task_routes = {
    "hnfm.web.tasks.hn_fetch_item": {"queue": QUEUE_INGEST},
    "hnfm.web.tasks.process_hn_item_run": {"queue": QUEUE_INGEST},
    "hnfm.web.tasks.score_run": {"queue": QUEUE_TRIAGE},
    "hnfm.web.tasks.enrich_run": {"queue": QUEUE_INGEST},
    "hnfm.web.tasks.build_story_brief": {"queue": QUEUE_TRIAGE},
    "hnfm.web.tasks.score_backlog": {"queue": QUEUE_TRIAGE},
    "hnfm.web.tasks.build_digest": {"queue": QUEUE_DIGEST},
    # Network and a headless browser, no GPU — the ingest lane, not render.
    "hnfm.web.tasks.capture_link_thumbnail": {"queue": QUEUE_INGEST},
    "hnfm.web.tasks.scheduled_job": {"queue": QUEUE_INGEST},
    "hnfm.web.tasks.fetch_hn_list": {"queue": QUEUE_INGEST},
    "hnfm.web.tasks.probe_hn_churn": {"queue": QUEUE_INGEST},
    "hnfm.web.tasks.produce_top_story": {"queue": QUEUE_INGEST},
    # Everything below contends for the GPU or ffmpeg and must stay serial.
    "hnfm.web.tasks.full_pipeline": {"queue": QUEUE_RENDER},
    "hnfm.web.tasks.generate_segment": {"queue": QUEUE_RENDER},
    "hnfm.web.tasks.build_segment_audio": {"queue": QUEUE_RENDER},
    "hnfm.web.tasks.build_segment_images": {"queue": QUEUE_RENDER},
    "hnfm.web.tasks.build_segment_episode": {"queue": QUEUE_RENDER},
    "hnfm.web.tasks.generate_segment_video": {"queue": QUEUE_RENDER},
    "hnfm.web.tasks.rebuild_single_image": {"queue": QUEUE_RENDER},
    # rerun_step re-executes an arbitrary step, so it goes to the slowest lane.
    "hnfm.web.tasks.rerun_step": {"queue": QUEUE_RENDER},
}

# Log the registered tasks for debugging
logger.info(f"Registered tasks: {list(celery_app.tasks.keys())}")


@worker_ready.connect
def _reap_abandoned_steps(**_kwargs):
    """Close out steps whose worker died mid-flight.

    A worker killed mid-step leaves its pipeline_steps row `running` forever,
    and `/api/activity` replays it to every dashboard and SSE subscriber as
    though the work were still in progress. Startup is the natural moment to
    reconcile: whatever was running when we last died is not running now.
    """
    try:
        from ..db import steps

        steps.reap_abandoned()
    except Exception as e:  # never block worker startup on bookkeeping
        logger.warning(f"abandoned-step reap failed at startup: {e}")

# Celery beat. The table is data in config.yaml (`schedule:`), built by
# hnfm.schedule.beat_schedule(); every entry fires `scheduled_job(name)`, which
# does the gating against the pause switches and dispatches the real task to
# its own lane. SCHEDULE_ENABLED=false empties the table.
try:
    from ..schedule import beat_schedule as _beat_schedule

    celery_app.conf.beat_schedule = _beat_schedule()
    for _name, _entry in celery_app.conf.beat_schedule.items():
        logger.info(f"schedule: {_name} {_entry['schedule']}")
    if not celery_app.conf.beat_schedule:
        logger.info("schedule: nothing scheduled (SCHEDULE_ENABLED=false or no jobs)")
except Exception as _e:  # a broken schedule must not take the workers down
    logger.error(f"schedule: could not build beat table: {_e}")
    celery_app.conf.beat_schedule = {}


if __name__ == "__main__":
    celery_app.start()
