"""Celery tasks for Hacker News operations"""

import os
import json
import logging
from typing import Dict
import redis
from datetime import datetime

from .celery_app import celery_app
from ..utils.hn_utils import exists_item, get_item_json_and_store
from ..utils.run_utils import (
    scrape_url_firecrawl,
    clean_content,
    summarize_text_v1,
    save_processed_run,
)
from ..content.content_enrichment import (
    generate_short_description,
    generate_tags,
    generate_emoji,
    generate_haiku,
)
from .models import ProcessedRun

logger = logging.getLogger(__name__)


@celery_app.task(name="src.hnfm.web.tasks.hn_fetch_item")
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
            decode_responses=False,  # Keep as bytes for JSON compatibility
        )

        # Check if item already exists
        if exists_item(item_id, redis_client=redis_client):
            logger.info(f"Item {item_id} already exists, skipping")
            return {"status": "exists", "id": item_id}

        # Get outputs directory
        outputs_dir = os.getenv("OUTPUTS_DIR", "/app/outputs")

        # Fetch and store the item
        get_item_json_and_store(
            item_id, redis_client=redis_client, outputs_dir=outputs_dir
        )

        logger.info(f"Successfully fetched and stored item {item_id}")
        return {"status": "fetched", "id": item_id}

    except Exception as e:
        logger.error(f"Failed to fetch item {item_id}: {e}")
        raise


@celery_app.task(name="hnfm.web.tasks.process_hn_item_run")
def process_hn_item_run(item_id: int, run: int) -> Dict[str, any]:
    """
    Process a HN item run: scrape, clean, summarize, and store.

    Steps:
    1) GET hn:item:{item_id} from Redis. If missing → raise.
    2) Parse JSON; read item['url']. If missing → raise.
    3) content_raw = scrape_url_firecrawl(url)
    4) content_clean = clean_content(content_raw)
    5) summary = summarize_text_v1(content_clean)
    6) Build ProcessedRun(...) with created_at=utcnow()
    7) save_processed_run(...)
    8) return {"status": "ok", "item_id": item_id, "run": run}
    """
    try:
        # Get Redis client
        redis_host = os.getenv("REDIS_HOST", "localhost")
        redis_port = int(os.getenv("REDIS_PORT", "6379"))
        redis_db = int(os.getenv("REDIS_DB", "0"))

        redis_client = redis.Redis(
            host=redis_host,
            port=redis_port,
            db=redis_db,
            decode_responses=False,  # Keep as bytes for JSON compatibility
        )

        # Get outputs directory
        outputs_dir = os.getenv("OUTPUTS_DIR", "/app/outputs")

        # Step 1: Get the HN item from Redis
        item_key = f"hnfm:item:{item_id}"
        item_json = redis_client.get(item_key)

        if not item_json:
            raise RuntimeError(f"Item {item_id} not found in Redis")

        # Step 2: Parse JSON and get URL
        item_data = json.loads(item_json)
        url = item_data.get('url')

        if not url:
            raise RuntimeError(f"Item {item_id} has no URL")

        # Step 3: Scrape content
        logger.info(f"Scraping content from {url}")
        content_raw = scrape_url_firecrawl(url)

        # Step 4: Clean content
        content_clean = clean_content(content_raw)

        # Step 5: Summarize content
        logger.info(f"Summarizing content for item {item_id}, run {run}")
        summary = summarize_text_v1(content_clean)

        # Step 6: Generate additional content fields
        logger.info(f"Generating short description for item {item_id}, run {run}")
        short_description = generate_short_description(summary)

        logger.info(f"Generating tags for item {item_id}, run {run}")
        tags = generate_tags(summary)

        logger.info(f"Generating emoji for item {item_id}, run {run}")
        emoji = generate_emoji(summary)

        logger.info(f"Generating haiku for item {item_id}, run {run}")
        haiku = generate_haiku(content_clean)

        # Step 7: Build ProcessedRun
        processed_run = ProcessedRun(
            key=f"hnfm:item:{item_id}:run:{run}",
            item_id=item_id,
            run=run,
            created_at=datetime.utcnow(),
            source_url=url,
            content_raw=content_raw,
            content_clean=content_clean,
            summary=summary,
            short_description=short_description,
            tags=tags,
            emoji=emoji,
            haiku=haiku
        )

        # Step 8: Save to Redis and disk
        save_processed_run(processed_run, redis_client=redis_client, outputs_root=outputs_dir)

        logger.info(f"Successfully processed run {run} for item {item_id}")
        return {"status": "ok", "item_id": item_id, "run": run}

    except Exception as e:
        logger.error(f"Failed to process run {run} for item {item_id}: {e}")
        raise
