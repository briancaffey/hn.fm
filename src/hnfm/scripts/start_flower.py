#!/usr/bin/env python3
"""Start Flower monitoring for hn.fm Celery tasks"""

import os
import sys
import subprocess

# Add src to path (scripts are now in src/hnfm/scripts/)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from hnfm.web.celery_app import celery_app

if __name__ == "__main__":
    print("Starting Flower monitoring for hn.fm...")
    print("Flower will be available at: http://localhost:5555")
    print("Press Ctrl+C to stop Flower")

    # Get Redis configuration
    redis_host = os.getenv("REDIS_HOST", "localhost")
    redis_port = os.getenv("REDIS_PORT", "6379")
    redis_db = os.getenv("REDIS_DB", "0")
    redis_password = os.getenv("REDIS_PASSWORD", "")

    # Build broker URL
    if redis_password:
        broker_url = f"redis://:{redis_password}@{redis_host}:{redis_port}/{redis_db}"
    else:
        broker_url = f"redis://{redis_host}:{redis_port}/{redis_db}"

    # Start Flower
    cmd = [
        "celery",
        "-A",
        "src.hnfm.web.celery_app:celery_app",
        "flower",
        "--broker=" + broker_url,
        "--port=5555",
        "--address=0.0.0.0",
    ]

    try:
        subprocess.run(cmd)
    except KeyboardInterrupt:
        print("\nFlower stopped")
    except Exception as e:
        print(f"Failed to start Flower: {e}")
        print("Make sure Flower is installed: pip install flower")
