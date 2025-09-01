"""Simplified Redis operations for hn.fm"""

import json
import logging
from datetime import datetime
from typing import Dict, Any, Optional, List
from .models import ContentItem, AudioSegment, ImageSegment
from .database import ContentDatabase

logger = logging.getLogger(__name__)


class RedisRepository:
    """Simplified Redis operations for hn.fm"""

    def __init__(self):
        self.db = ContentDatabase()
        self.redis_client = self.db.redis_client

    def _get_key(self, key_type: str, *parts) -> str:
        """Generate Redis key for different types"""
        return f"hnfm:{key_type}:{':'.join(str(part) for part in parts)}"

    def _serialize_datetime(self, obj: Any) -> Any:
        """Serialize datetime objects for JSON storage"""
        if isinstance(obj, datetime):
            return obj.isoformat()
        return obj

    def _deserialize_datetime(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Deserialize datetime strings from JSON"""
        for field in ["created_at", "updated_at"]:
            if field in data and data[field]:
                try:
                    data[field] = datetime.fromisoformat(data[field])
                except ValueError:
                    logger.warning(
                        f"Could not parse datetime for {field}: {data[field]}"
                    )
        return data

    # Content Item operations
    def save_content_item(self, content_item: ContentItem) -> bool:
        """Save a content item to Redis"""
        try:
            key = self._get_key("content", content_item.id)
            data = content_item.dict()
            data = {k: self._serialize_datetime(v) for k, v in data.items()}
            self.redis_client.set(key, json.dumps(data))
            return True
        except Exception as e:
            logger.error(f"Error saving content item {content_item.id}: {e}")
            return False

    def get_content_item(self, content_id: str) -> Optional[ContentItem]:
        """Get a content item from Redis"""
        try:
            key = self._get_key("content", content_id)
            data = self.redis_client.get(key)
            if data:
                content_dict = json.loads(data)
                content_dict = self._deserialize_datetime(content_dict)
                return ContentItem(**content_dict)
            return None
        except Exception as e:
            logger.error(f"Error getting content item {content_id}: {e}")
            return None

    def get_all_content_items(self) -> List[ContentItem]:
        """Get all content items from Redis"""
        try:
            pattern = self._get_key("content", "*")
            keys = self.redis_client.keys(pattern)
            items = []
            for key in keys:
                data = self.redis_client.get(key)
                if data:
                    content_dict = json.loads(data)
                    content_dict = self._deserialize_datetime(content_dict)
                    items.append(ContentItem(**content_dict))
            return items
        except Exception as e:
            logger.error(f"Error getting all content items: {e}")
            return []

    def delete_content_item(self, content_id: str) -> bool:
        """Delete a content item from Redis"""
        try:
            key = self._get_key("content", content_id)
            self.redis_client.delete(key)
            return True
        except Exception as e:
            logger.error(f"Error deleting content item {content_id}: {e}")
            return False

    # HN Item operations (stored as JSON)
    def save_hn_item(self, hn_item_id: int, hn_data: Dict[str, Any]) -> bool:
        """Save HN item data as JSON"""
        try:
            key = self._get_key("hn_item", hn_item_id)
            self.redis_client.set(key, json.dumps(hn_data))
            return True
        except Exception as e:
            logger.error(f"Error saving HN item {hn_item_id}: {e}")
            return False

    def get_hn_item(self, hn_item_id: int) -> Optional[Dict[str, Any]]:
        """Get HN item data as JSON"""
        try:
            key = self._get_key("hn_item", hn_item_id)
            data = self.redis_client.get(key)
            if data:
                return json.loads(data)
            return None
        except Exception as e:
            logger.error(f"Error getting HN item {hn_item_id}: {e}")
            return None

    # Audio Segment operations
    def save_audio_segment(self, audio_segment: AudioSegment) -> bool:
        """Save an audio segment to Redis"""
        try:
            key = self._get_key("tts", audio_segment.content_item_id, audio_segment.id)
            data = audio_segment.dict()
            self.redis_client.set(key, json.dumps(data))
            return True
        except Exception as e:
            logger.error(f"Error saving audio segment {audio_segment.id}: {e}")
            return False

    def get_audio_segment(
        self, content_id: str, segment_id: str
    ) -> Optional[AudioSegment]:
        """Get an audio segment from Redis"""
        try:
            key = self._get_key("tts", content_id, segment_id)
            data = self.redis_client.get(key)
            if data:
                segment_dict = json.loads(data)
                return AudioSegment(**segment_dict)
            return None
        except Exception as e:
            logger.error(f"Error getting audio segment {segment_id}: {e}")
            return None

    def get_audio_segments_for_content(self, content_id: str) -> List[AudioSegment]:
        """Get all audio segments for a content item"""
        try:
            pattern = self._get_key("tts", content_id, "*")
            keys = self.redis_client.keys(pattern)
            segments = []
            for key in keys:
                data = self.redis_client.get(key)
                if data:
                    segment_dict = json.loads(data)
                    segments.append(AudioSegment(**segment_dict))
            # Sort by sequence number
            segments.sort(key=lambda x: x.sequence_number)
            return segments
        except Exception as e:
            logger.error(f"Error getting audio segments for content {content_id}: {e}")
            return []

    def delete_audio_segment(self, content_id: str, segment_id: str) -> bool:
        """Delete an audio segment from Redis"""
        try:
            key = self._get_key("tts", content_id, segment_id)
            self.redis_client.delete(key)
            return True
        except Exception as e:
            logger.error(f"Error deleting audio segment {segment_id}: {e}")
            return False

    # Image Segment operations
    def save_image_segment(self, image_segment: ImageSegment) -> bool:
        """Save an image segment to Redis"""
        try:
            key = self._get_key(
                "image", image_segment.content_item_id, image_segment.id
            )
            data = image_segment.dict()
            self.redis_client.set(key, json.dumps(data))
            return True
        except Exception as e:
            logger.error(f"Error saving image segment {image_segment.id}: {e}")
            return False

    def get_image_segment(
        self, content_id: str, segment_id: str
    ) -> Optional[ImageSegment]:
        """Get an image segment from Redis"""
        try:
            key = self._get_key("image", content_id, segment_id)
            data = self.redis_client.get(key)
            if data:
                segment_dict = json.loads(data)
                return ImageSegment(**segment_dict)
            return None
        except Exception as e:
            logger.error(f"Error getting image segment {segment_id}: {e}")
            return None

    def get_image_segments_for_content(self, content_id: str) -> List[ImageSegment]:
        """Get all image segments for a content item"""
        try:
            pattern = self._get_key("image", content_id, "*")
            keys = self.redis_client.keys(pattern)
            segments = []
            for key in keys:
                data = self.redis_client.get(key)
                if data:
                    segment_dict = json.loads(data)
                    segments.append(ImageSegment(**segment_dict))
            # Sort by sequence number
            segments.sort(key=lambda x: x.sequence_number)
            return segments
        except Exception as e:
            logger.error(f"Error getting image segments for content {content_id}: {e}")
            return []

    def delete_image_segment(self, content_id: str, segment_id: str) -> bool:
        """Delete an image segment from Redis"""
        try:
            key = self._get_key("image", content_id, segment_id)
            self.redis_client.delete(key)
            return True
        except Exception as e:
            logger.error(f"Error deleting image segment {segment_id}: {e}")
            return False

    # Utility methods
    def get_content_by_hn_id(self, hn_item_id: int) -> Optional[ContentItem]:
        """Get content item by HN item ID"""
        try:
            items = self.get_all_content_items()
            for item in items:
                if item.hn_item_id == hn_item_id:
                    return item
            return None
        except Exception as e:
            logger.error(f"Error getting content by HN ID {hn_item_id}: {e}")
            return None

    def update_content_status(self, content_id: str, status: str) -> bool:
        """Update content item status"""
        try:
            content_item = self.get_content_item(content_id)
            if content_item:
                content_item.status = status
                content_item.updated_at = datetime.now().isoformat()
                return self.save_content_item(content_item)
            return False
        except Exception as e:
            logger.error(f"Error updating content status {content_id}: {e}")
            return False
