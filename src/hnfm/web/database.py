"""Redis database interface for storing content data"""

import json
import logging
import os
from typing import List, Optional, Dict, Any
from datetime import datetime
import redis
from ..utils.config import config_manager

logger = logging.getLogger(__name__)


class ContentDatabase:
    """Redis-based database for storing content items"""

    def __init__(self):
        self.config = config_manager
        self.redis_client = None
        self._connect()

    def _connect(self):
        """Connect to Redis"""
        try:
            self.redis_client = redis.Redis(
                host=os.getenv('REDIS_HOST', 'localhost'),
                port=int(os.getenv('REDIS_PORT', 6379)),
                db=int(os.getenv('REDIS_DB', 0)),
                password=os.getenv('REDIS_PASSWORD'),
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5
            )
            # Test connection
            self.redis_client.ping()
            logger.info("Connected to Redis successfully")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            self.redis_client = None

    def _get_key(self, key_type: str, identifier: str) -> str:
        """Generate Redis key for different types"""
        return f"hnfm:{key_type}:{identifier}"

    def _serialize_datetime(self, obj: Any) -> Any:
        """Serialize datetime objects for JSON storage"""
        if isinstance(obj, datetime):
            return obj.isoformat()
        return obj

    def _deserialize_datetime(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Deserialize datetime strings from JSON"""
        for field in ['created_at', 'updated_at', 'last_completion']:
            if field in data and data[field]:
                try:
                    data[field] = datetime.fromisoformat(data[field])
                except ValueError:
                    logger.warning(f"Could not parse datetime for {field}: {data[field]}")
        return data

    def _serialize_datetime_for_json(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Convert datetime objects to ISO strings for JSON serialization"""
        if isinstance(data, dict):
            result = {}
            for key, value in data.items():
                if isinstance(value, datetime):
                    result[key] = value.isoformat()
                elif isinstance(value, dict):
                    result[key] = self._serialize_datetime_for_json(value)
                elif isinstance(value, list):
                    result[key] = [self._serialize_datetime_for_json(item) if isinstance(item, dict) else item for item in value]
                else:
                    result[key] = value
            return result
        return data

    def store_content(self, content_id: str, content_data: Dict[str, Any]) -> bool:
        """Store a content item in Redis"""
        if not self.redis_client:
            logger.error("Redis not connected")
            return False

        try:
            # Store content data
            content_key = self._get_key('content', content_id)

            # Convert datetime objects to ISO strings for storage
            content_data_copy = content_data.copy()
            if 'created_at' in content_data_copy and isinstance(content_data_copy['created_at'], datetime):
                content_data_copy['created_at'] = content_data_copy['created_at'].isoformat()
            if 'updated_at' in content_data_copy and isinstance(content_data_copy['updated_at'], datetime):
                content_data_copy['updated_at'] = content_data_copy['updated_at'].isoformat()

            # Store the content data
            content_json = json.dumps(content_data_copy, default=self._serialize_datetime)
            self.redis_client.set(content_key, content_json)

            # Store in sorted set for listing (by updated_at timestamp)
            list_key = self._get_key('content_list', 'all')
            updated_at = content_data.get('updated_at', content_data.get('created_at', datetime.now().isoformat()))
            if isinstance(updated_at, datetime):
                updated_at = updated_at.timestamp()
            self.redis_client.zadd(list_key, {content_id: updated_at})

            # Store metadata for quick access
            metadata_key = self._get_key('metadata', content_id)
            metadata = {
                'id': content_id,
                'title': content_data.get('title', ''),
                'url': content_data.get('url', ''),
                'content_type': content_data.get('content_type', ''),
                'status': content_data.get('status', ''),
                'created_at': content_data.get('created_at', datetime.now().isoformat()),
                'updated_at': updated_at
            }

            # Convert metadata datetime objects to ISO strings
            if isinstance(metadata['created_at'], datetime):
                metadata['created_at'] = metadata['created_at'].isoformat()
            if isinstance(metadata['updated_at'], datetime):
                metadata['updated_at'] = metadata['updated_at'].isoformat()

            metadata_json = json.dumps(metadata, default=self._serialize_datetime)
            self.redis_client.set(metadata_key, metadata_json)

            logger.info(f"Stored content item {content_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to store content {content_id}: {e}")
            return False

    def get_content(self, content_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a content item from Redis"""
        if not self.redis_client:
            logger.error("Redis not connected")
            return None

        try:
            content_key = self._get_key('content', content_id)
            content_data = self.redis_client.get(content_key)

            if content_data:
                data = json.loads(content_data)
                return data  # No need to deserialize datetime objects anymore

            return None

        except Exception as e:
            logger.error(f"Failed to retrieve content {content_id}: {e}")
            return None

    def list_content(self, page: int = 1, per_page: int = 20,
                    content_type: Optional[str] = None,
                    status: Optional[str] = None) -> Dict[str, Any]:
        """List content items with pagination and filtering"""
        if not self.redis_client:
            logger.error("Redis not connected")
            return {'items': [], 'total': 0, 'page': page, 'per_page': per_page}

        try:
            list_key = self._get_key('content_list', 'all')

            # Get all content IDs
            all_ids = self.redis_client.zrevrange(list_key, 0, -1)

            # Apply filters if specified
            filtered_ids = []
            for content_id in all_ids:
                metadata_key = self._get_key('metadata', content_id)
                metadata = self.redis_client.get(metadata_key)

                if metadata:
                    meta = json.loads(metadata)
                    if content_type and meta.get('content_type') != content_type:
                        continue
                    if status and meta.get('status') != status:
                        continue
                    filtered_ids.append(content_id)

            # Calculate pagination
            total = len(filtered_ids)
            start = (page - 1) * per_page
            end = start + per_page
            page_ids = filtered_ids[start:end]

            # Retrieve content items
            items = []
            for content_id in page_ids:
                content = self.get_content(content_id)
                if content:
                    items.append(content)

            return {
                'items': items,
                'total': total,
                'page': page,
                'per_page': per_page,
                'has_next': end < total,
                'has_prev': page > 1
            }

        except Exception as e:
            logger.error(f"Failed to list content: {e}")
            return {'items': [], 'total': 0, 'page': page, 'per_page': per_page}

    def _update_sorted_set_score(self, content_id: str, updated_at: datetime) -> bool:
        """Update the score (timestamp) for a content item in the sorted set"""
        if not self.redis_client:
            return False

        try:
            list_key = self._get_key('content_list', 'all')
            self.redis_client.zadd(list_key, {content_id: updated_at.timestamp()})
            return True
        except Exception as e:
            logger.error(f"Failed to update sorted set score for {content_id}: {e}")
            return False

    def update_content(self, content_id: str, updates: Dict[str, Any]) -> bool:
        """Update a content item"""
        if not self.redis_client:
            logger.error("Redis not connected")
            return False

        try:
            # Get existing content
            existing = self.get_content(content_id)
            if not existing:
                return False

            # Apply updates
            existing.update(updates)
            existing['updated_at'] = datetime.now().isoformat()

            # Update the sorted set score to reflect the new updated_at time
            self._update_sorted_set_score(content_id, datetime.now())

            # Store updated content
            return self.store_content(content_id, existing)

        except Exception as e:
            logger.error(f"Failed to update content {content_id}: {e}")
            return False

    def delete_content(self, content_id: str) -> bool:
        """Delete a content item"""
        if not self.redis_client:
            logger.error("Redis not connected")
            return False

        try:
            # Remove from content list
            list_key = self._get_key('content_list', 'all')
            self.redis_client.zrem(list_key, content_id)

            # Remove content and metadata
            content_key = self._get_key('content', content_id)
            metadata_key = self._get_key('metadata', content_id)

            self.redis_client.delete(content_key, metadata_key)

            logger.info(f"Deleted content item {content_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to delete content {content_id}: {e}")
            return False

    def get_pipeline_status(self) -> Dict[str, Any]:
        """Get pipeline status information"""
        if not self.redis_client:
            return {
                'is_running': False,
                'active_jobs': 0,
                'completed_today': 0,
                'total_processed': 0,
                'last_completion': None
            }

        try:
            # Get total processed
            list_key = self._get_key('content_list', 'all')
            total_processed = self.redis_client.zcard(list_key)

            # Get completed today
            today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            today_timestamp = today.timestamp()

            completed_today = 0
            all_ids = self.redis_client.zrange(list_key, 0, -1)
            for content_id in all_ids:
                metadata_key = self._get_key('metadata', content_id)
                metadata = self.redis_client.get(metadata_key)
                if metadata:
                    meta = json.loads(metadata)
                    if meta.get('created_at', 0) >= today_timestamp:
                        completed_today += 1

            # Get last completion
            last_completion = None
            if all_ids:
                last_id = all_ids[-1]
                content = self.get_content(last_id)
                if content and content.get('status') == 'completed':
                    last_completion = content.get('updated_at')

            return {
                'is_running': False,  # TODO: Implement actual pipeline status tracking
                'active_jobs': 0,     # TODO: Implement job queue tracking
                'completed_today': completed_today,
                'total_processed': total_processed,
                'last_completion': last_completion
            }

        except Exception as e:
            logger.error(f"Failed to get pipeline status: {e}")
            return {
                'is_running': False,
                'active_jobs': 0,
                'completed_today': 0,
                'total_processed': 0,
                'last_completion': None
            }

    def health_check(self) -> bool:
        """Check Redis connection health"""
        if not self.redis_client:
            return False

        try:
            self.redis_client.ping()
            return True
        except Exception:
            return False

    def is_hn_story_processed(self, story_id: int) -> bool:
        """
        Check if a Hacker News story has already been processed

        Args:
            story_id: The HN story ID to check

        Returns:
            True if story is already processed, False otherwise
        """
        if not self.redis_client:
            return False

        try:
            hn_key = self._get_key('hn_items', 'processed')
            return self.redis_client.zscore(hn_key, story_id) is not None
        except Exception as e:
            logger.error(f"Failed to check if HN story {story_id} is processed: {e}")
            return False

    def mark_hn_story_processed(self, story_id: int, content_id: str) -> bool:
        """
        Mark a Hacker News story as processed

        Args:
            story_id: The HN story ID
            content_id: The content ID it was processed into

        Returns:
            True if successful, False otherwise
        """
        if not self.redis_client:
            return False

        try:
            hn_key = self._get_key('hn_items', 'processed')
            # Store with timestamp and content_id as score
            timestamp = datetime.now().timestamp()
            self.redis_client.zadd(hn_key, {story_id: timestamp})

            # Also store mapping from story_id to content_id
            mapping_key = self._get_key('hn_mapping', str(story_id))
            self.redis_client.set(mapping_key, content_id)

            logger.info(f"Marked HN story {story_id} as processed -> content {content_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to mark HN story {story_id} as processed: {e}")
            return False

    def get_hn_story_mapping(self, story_id: int) -> Optional[str]:
        """
        Get the content ID that a HN story was processed into

        Args:
            story_id: The HN story ID

        Returns:
            Content ID if found, None otherwise
        """
        if not self.redis_client:
            return None

        try:
            mapping_key = self._get_key('hn_mapping', str(story_id))
            return self.redis_client.get(mapping_key)
        except Exception as e:
            logger.error(f"Failed to get HN story mapping for {story_id}: {e}")
            return None

    def get_hn_processing_stats(self) -> Dict[str, Any]:
        """
        Get statistics about HN story processing

        Returns:
            Dictionary with processing statistics
        """
        if not self.redis_client:
            return {
                'total_processed': 0,
                'total_skipped': 0,
                'last_processed': None
            }

        try:
            hn_key = self._get_key('hn_items', 'processed')
            total_processed = self.redis_client.zcard(hn_key)

            # Get last processed story
            last_processed = None
            if total_processed > 0:
                last_items = self.redis_client.zrevrange(hn_key, 0, 0, withscores=True)
                if last_items:
                    last_story_id, timestamp = last_items[0]
                    last_processed = {
                        'story_id': int(last_story_id),
                        'timestamp': datetime.fromtimestamp(timestamp).isoformat()
                    }

            return {
                'total_processed': total_processed,
                'total_skipped': 0,  # TODO: Track skipped stories if needed
                'last_processed': last_processed
            }
        except Exception as e:
            logger.error(f"Failed to get HN processing stats: {e}")
            return {
                'total_processed': 0,
                'total_skipped': 0,
                'last_processed': None
            }
