#!/usr/bin/env python3
"""Start Celery worker for hn.fm"""

import os
import sys

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

# Set environment variables for debugging
os.environ.setdefault("CELERY_WORKER_RUNNING", "1")

from hnfm.web.celery_app import celery_app

if __name__ == "__main__":
    print("Starting Celery worker for hn.fm...")
    print("Worker will process tasks from the 'hnfm_tasks' queue")
    print("Press Ctrl+C to stop the worker")

    # Print registered tasks for debugging
    print(f"Registered tasks: {list(celery_app.tasks.keys())}")
    print(f"Broker URL: {celery_app.conf.broker_url}")
    print(f"Result backend: {celery_app.conf.result_backend}")

    # Start the worker
    celery_app.worker_main(
        [
            "worker",
            "--loglevel=info",
            "--queues=hnfm_tasks",
            "--concurrency=2",
            "--hostname=hnfm-worker@%h",
        ]
    )
