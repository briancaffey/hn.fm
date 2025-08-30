#!/usr/bin/env python3
"""Start Celery worker for hn.fm"""

import os
import sys

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from hnfm.web.celery_app import celery_app

if __name__ == "__main__":
    print("Starting Celery worker for hn.fm...")
    print("Worker will process tasks from the 'hnfm_tasks' queue")
    print("Press Ctrl+C to stop the worker")

    # Start the worker
    celery_app.worker_main([
        "worker",
        "--loglevel=info",
        "--queues=hnfm_tasks",
        "--concurrency=2",
        "--hostname=hnfm-worker@%h"
    ])
