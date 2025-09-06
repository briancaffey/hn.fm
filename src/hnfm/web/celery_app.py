"""Celery application configuration for hn.fm"""

import os
import logging
from celery import Celery

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

# Create Celery app
celery_app = Celery(
    "hnfm",
    broker=broker_url,
    backend=result_backend,
    include=["src.hnfm.web.tasks"],  # Include our HN tasks
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
    # Task routing - Route HN tasks to hnfm_tasks queue
    task_routes={
        "src.hnfm.web.tasks.*": {"queue": "hnfm_tasks"},
        "hnfm.web.tasks.*": {"queue": "hnfm_tasks"},
        "src.hnfm.web.tasks.process_hn_item_run": {"queue": "hnfm_tasks"},
        "hnfm.web.tasks.process_hn_item_run": {"queue": "hnfm_tasks"},
        "src.hnfm.web.tasks.generate_segment": {"queue": "hnfm_tasks"},
        "hnfm.web.tasks.generate_segment": {"queue": "hnfm_tasks"},
        "src.hnfm.web.tasks.build_segment_audio": {"queue": "hnfm_tasks"},
        "hnfm.web.tasks.build_segment_audio": {"queue": "hnfm_tasks"},
        "src.hnfm.web.tasks.build_segment_images": {"queue": "hnfm_tasks"},
        "hnfm.web.tasks.build_segment_images": {"queue": "hnfm_tasks"},
        "src.hnfm.web.tasks.rebuild_single_image": {"queue": "hnfm_tasks"},
        "hnfm.web.tasks.rebuild_single_image": {"queue": "hnfm_tasks"},
    },
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

# Log the registered tasks for debugging
logger.info(f"Registered tasks: {list(celery_app.tasks.keys())}")

# Optional: Configure Celery Beat for periodic tasks
# Removed cleanup task - simplified task system
celery_app.conf.beat_schedule = {}


if __name__ == "__main__":
    celery_app.start()
