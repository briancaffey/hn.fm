"""Hacker News utilities for fetching, storing, and retrieving items"""

import json
import logging
import os
from typing import List, Optional
import requests
import redis

from ..web.models import HNItem

logger = logging.getLogger(__name__)


# HTTP (Firebase) functions
def get_top_story_ids() -> List[int]:
    """Get top story IDs from Hacker News Firebase API"""
    try:
        response = requests.get("https://hacker-news.firebaseio.com/v0/topstories.json")
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        logger.error(f"Failed to fetch top story IDs: {e}")
        raise


def get_new_story_ids() -> List[int]:
    """Get new story IDs from Hacker News Firebase API"""
    try:
        response = requests.get("https://hacker-news.firebaseio.com/v0/newstories.json")
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        logger.error(f"Failed to fetch new story IDs: {e}")
        raise


def get_item_json_and_store(
    item_id: int, *, redis_client: redis.Redis, outputs_dir: str
) -> HNItem:
    """Get item JSON from Firebase, validate, and store in Redis and file"""
    try:
        # Fetch from Firebase
        response = requests.get(
            f"https://hacker-news.firebaseio.com/v0/item/{item_id}.json"
        )
        response.raise_for_status()
        item_data = response.json()

        # Validate with HNItem
        hn_item = HNItem(**item_data)

        # Store in Redis
        redis_key = f"hnfm:item:{item_id}"
        redis_client.set(redis_key, hn_item.model_dump_json())

        # Store in file
        item_dir = os.path.join(outputs_dir, "hn", "item", str(item_id))
        os.makedirs(item_dir, exist_ok=True)
        item_file = os.path.join(item_dir, "item.json")

        with open(item_file, "w") as f:
            f.write(hn_item.model_dump_json())

        logger.info(f"Stored item {item_id} in Redis and file")
        return hn_item

    except requests.RequestException as e:
        logger.error(f"Failed to fetch item {item_id}: {e}")
        raise
    except Exception as e:
        logger.error(f"Failed to store item {item_id}: {e}")
        raise


# Redis helper functions
def exists_item(item_id: int, *, redis_client: redis.Redis) -> bool:
    """Check if item exists in Redis"""
    redis_key = f"hnfm:item:{item_id}"
    return redis_client.exists(redis_key) > 0


def get_item(item_id: int, *, redis_client: redis.Redis) -> Optional[HNItem]:
    """Get item from Redis"""
    redis_key = f"hnfm:item:{item_id}"
    item_json = redis_client.get(redis_key)

    if item_json is None:
        return None

    try:
        item_data = json.loads(item_json)
        return HNItem(**item_data)
    except (json.JSONDecodeError, ValueError) as e:
        logger.error(f"Failed to parse item {item_id} from Redis: {e}")
        return None


def list_item_ids(*, redis_client: redis.Redis) -> List[int]:
    """List all item IDs stored in Redis"""
    pattern = "hnfm:item:*"
    item_ids = []

    cursor = 0
    while True:
        cursor, keys = redis_client.scan(cursor, match=pattern, count=100)
        for key in keys:
            # Extract ID from key "hnfm:item:{id}"
            try:
                item_id = int(key.decode().split(":")[-1])
                item_ids.append(item_id)
            except (ValueError, IndexError) as e:
                logger.warning(f"Invalid Redis key format: {key}, error: {e}")

        if cursor == 0:
            break

    return item_ids


def list_items(offset: int, limit: int, *, redis_client: redis.Redis) -> List[HNItem]:
    """List items with pagination, ordered by ID descending"""
    # Get all item IDs
    all_ids = list_item_ids(redis_client=redis_client)

    # Sort descending (largest ID first)
    all_ids.sort(reverse=True)

    # Apply pagination
    end_index = min(offset + limit, len(all_ids))
    paginated_ids = all_ids[offset:end_index]

    # Fetch items using MGET for efficiency
    if paginated_ids:
        keys = [f"hnfm:item:{item_id}" for item_id in paginated_ids]
        item_jsons = redis_client.mget(keys)

        items = []
        for item_json in item_jsons:
            if item_json is not None:
                try:
                    item_data = json.loads(item_json)
                    items.append(HNItem(**item_data))
                except (json.JSONDecodeError, ValueError) as e:
                    logger.warning(f"Failed to parse item from Redis: {e}")

        return items

    return []
