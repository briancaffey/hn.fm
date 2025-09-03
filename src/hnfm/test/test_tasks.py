"""Tests for Celery tasks"""

import json
import pytest
from unittest.mock import Mock, patch
import fakeredis
import os

from ..web.tasks import hn_fetch_item


class TestCeleryTask:
    """Test Celery task functionality"""

    @patch("requests.get")
    @patch("redis.Redis")
    def test_hn_fetch_item_exists_short_circuits(self, mock_redis_class, mock_get):
        """Test hn_fetch_item short circuits when item already exists"""
        # Create fake Redis with existing item
        fake_redis = fakeredis.FakeRedis(decode_responses=False)
        fake_redis.set("hnfm:item:7", json.dumps({"id": 7}))

        # Mock Redis client creation
        mock_redis_class.return_value = fake_redis

        # Mock requests.get to raise if called (ensure no HTTP)
        mock_get.side_effect = Exception("Should not be called")

        # Mock environment variables
        with patch.dict(
            os.environ,
            {
                "REDIS_HOST": "localhost",
                "REDIS_PORT": "6379",
                "REDIS_DB": "0",
                "OUTPUTS_DIR": "/tmp",
            },
        ):
            # Call the task directly (not via worker)
            result = hn_fetch_item(7)

        # Assertions
        assert result == {"status": "exists", "id": 7}
        mock_get.assert_not_called()

    @patch("requests.get")
    def test_hn_fetch_item_fetches_when_missing(self, mock_get):
        """Test hn_fetch_item fetches when item is missing"""
        # Create empty fake Redis
        fake_redis = fakeredis.FakeRedis(decode_responses=False)

        # Mock the HTTP response
        mock_response = Mock()
        mock_response.json.return_value = {"id": 8, "type": "story"}
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        # Mock environment variables
        with patch.dict(
            os.environ,
            {
                "REDIS_HOST": "localhost",
                "REDIS_PORT": "6379",
                "REDIS_DB": "0",
                "OUTPUTS_DIR": "/tmp",
            },
        ):
            # Mock the Redis client creation
            with patch("redis.Redis") as mock_redis_class:
                mock_redis_class.return_value = fake_redis

                # Call the task directly
                result = hn_fetch_item(8)

        # Assertions
        assert result == {"status": "fetched", "id": 8}

        # Check that item was stored in Redis
        redis_value = fake_redis.get("hnfm:item:8")
        assert redis_value is not None
        stored_data = json.loads(redis_value)
        assert stored_data["id"] == 8
