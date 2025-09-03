"""Celery tasks for Hacker News operations"""

import os
import logging
from typing import Dict
import redis

from .celery_app import celery_app
from ..utils.hn_utils import exists_item, get_item_json_and_store

logger = logging.getLogger(__name__)


@celery_app.task(name='src.hnfm.web.tasks.hn_fetch_item')
def hn_fetch_item(item_id: int) -> Dict[str, any]:
    """Fetch and store a Hacker News item"""
    try:
        # Get Redis client
        redis_host = os.getenv("REDIS_HOST", "localhost")
        redis_port = int(os.getenv("REDIS_PORT", "6379"))
        redis_db = int(os.getenv("REDIS_DB", "0"))

        redis_client = redis.Redis(
            host=redis_host,
            port=redis_port,
            db=redis_db,
            decode_responses=False  # Keep as bytes for JSON compatibility
        )

        # Check if item already exists
        if exists_item(item_id, redis_client=redis_client):
            logger.info(f"Item {item_id} already exists, skipping")
            return {"status": "exists", "id": item_id}

        # Get outputs directory
        outputs_dir = os.getenv("OUTPUTS_DIR", "/app/outputs")

        # Fetch and store the item
        get_item_json_and_store(
            item_id,
            redis_client=redis_client,
            outputs_dir=outputs_dir
        )

        logger.info(f"Successfully fetched and stored item {item_id}")
        return {"status": "fetched", "id": item_id}

    except Exception as e:
        logger.error(f"Failed to fetch item {item_id}: {e}")
        raise
