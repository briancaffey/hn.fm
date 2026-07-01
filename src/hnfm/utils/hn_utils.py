"""Hacker News utilities for fetching, storing, and retrieving items"""

import logging
import os
from typing import List, Optional
import requests

from ..db import repo
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


def get_item_json_and_store(item_id: int, *, outputs_dir: str) -> HNItem:
    """Get item JSON from Firebase, validate, and store in Postgres and file"""
    try:
        # Fetch from Firebase
        response = requests.get(
            f"https://hacker-news.firebaseio.com/v0/item/{item_id}.json"
        )
        response.raise_for_status()
        item_data = response.json()

        # Validate with HNItem
        hn_item = HNItem(**item_data)

        # Store in Postgres
        repo.upsert_item(hn_item)

        # Store in file
        item_dir = os.path.join(outputs_dir, "hn", "item", str(item_id))
        os.makedirs(item_dir, exist_ok=True)
        item_file = os.path.join(item_dir, "item.json")

        with open(item_file, "w") as f:
            f.write(hn_item.model_dump_json())

        logger.info(f"Stored item {item_id} in Postgres and file")
        return hn_item

    except requests.RequestException as e:
        logger.error(f"Failed to fetch item {item_id}: {e}")
        raise
    except Exception as e:
        logger.error(f"Failed to store item {item_id}: {e}")
        raise


def exists_item(item_id: int) -> bool:
    """Check if item exists in the database"""
    return repo.exists_item(item_id)


def get_item(item_id: int) -> Optional[HNItem]:
    """Get item from the database"""
    return repo.get_item(item_id)


def list_item_ids() -> List[int]:
    """List all item IDs, newest (largest) first"""
    return repo.list_item_ids()


def list_items(offset: int, limit: int) -> List[HNItem]:
    """List items with pagination, ordered by ID descending"""
    return repo.list_items(offset=offset, limit=limit)


def count_items() -> int:
    """Total number of stored items (for pagination)"""
    return repo.count_items()
