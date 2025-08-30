#!/usr/bin/env python3
"""Start Celery Beat for hn.fm periodic tasks"""

import os
import sys

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from hnfm.web.celery_app import celery_app

if __name__ == "__main__":
    print("Starting Celery Beat for hn.fm...")
    print("Beat will schedule periodic tasks")
    print("Press Ctrl+C to stop Beat")

    # Start Beat
    celery_app.start([
        "beat",
        "--loglevel=info",
        "--scheduler=celery.beat.PersistentScheduler"
    ])
