"""Tests for API endpoints"""

import json
import pytest
import asyncio
from unittest.mock import Mock, patch
import fakeredis
from fastapi.testclient import TestClient

from ..web.api import app
from ..web.api import queue_top_stories, list_downloaded_items, get_single_item


class TestAPIEndpoints:
    """Test API endpoints"""

    @patch("hnfm.web.api.get_top_story_ids")
    @patch("hnfm.web.tasks.hn_fetch_item.apply_async")
    def test_queue_top_enqueues_apply_async(self, mock_apply_async, mock_get_top_ids):
        """Test queue top endpoint enqueues tasks with apply_async"""
        # Mock get_top_story_ids to return test data
        mock_get_top_ids.return_value = [1, 2, 3, 4, 5]

        # Mock apply_async to collect calls
        apply_async_calls = []

        def mock_apply_async_func(args=None, queue=None, **kwargs):
            apply_async_calls.append(args)
            return Mock()

        mock_apply_async.side_effect = mock_apply_async_func

        # Create fake Redis
        fake_redis = fakeredis.FakeRedis(decode_responses=False)

        # Call the function directly
        result = asyncio.run(queue_top_stories(limit=3, redis_client=fake_redis))

        # Assertions
        assert result["queued_count"] == 3
        assert result["ids"] == [1, 2, 3]
        assert result["limit"] == 3

        # Check apply_async was called correctly
        assert mock_apply_async.call_count == 3
        assert apply_async_calls == [[1], [2], [3]]

    def test_list_items_endpoint(self):
        """Test list items endpoint"""
        # Create fake Redis with test data
        fake_redis = fakeredis.FakeRedis(decode_responses=False)
        fake_redis.set("hnfm:item:2", json.dumps({"id": 2, "title": "Item 2"}))
        fake_redis.set("hnfm:item:1", json.dumps({"id": 1, "title": "Item 1"}))

        # Call the function directly
        result = asyncio.run(
            list_downloaded_items(offset=0, limit=2, redis_client=fake_redis)
        )

        # Assertions
        assert len(result["items"]) == 2
        assert result["items"][0]["id"] == 2  # Largest ID first
        assert result["items"][1]["id"] == 1
        assert result["pagination"]["offset"] == 0
        assert result["pagination"]["limit"] == 2
        assert result["pagination"]["count"] == 2

    def test_get_single_item_endpoint(self):
        """Test get single item endpoint"""
        # Create fake Redis with test data
        fake_redis = fakeredis.FakeRedis(decode_responses=False)
        fake_redis.set("hnfm:item:9", json.dumps({"id": 9, "title": "Test Item"}))

        # Test existing item
        result = asyncio.run(get_single_item(item_id=9, redis_client=fake_redis))
        assert result["id"] == 9
        assert result["title"] == "Test Item"

        # Test non-existing item
        with pytest.raises(Exception) as exc_info:
            asyncio.run(get_single_item(item_id=999999, redis_client=fake_redis))
        assert "Item not found" in str(exc_info.value)


class TestAPIEndpointsIntegration:
    """Integration tests using TestClient"""

    def test_queue_top_endpoint_integration(self):
        """Test the actual endpoint with mocked dependencies"""
        with patch("hnfm.web.api.get_top_story_ids") as mock_get_top_ids:
            mock_get_top_ids.return_value = [1, 2, 3, 4, 5]

            with patch("hnfm.web.tasks.hn_fetch_item.apply_async") as mock_apply_async:
                mock_apply_async.return_value = Mock()

                with patch("hnfm.web.api.get_redis_client") as mock_get_redis:
                    fake_redis = fakeredis.FakeRedis(decode_responses=False)
                    mock_get_redis.return_value = fake_redis

                    client = TestClient(app)
                    response = client.post("/api/hn/queue-top?limit=3")

                    assert response.status_code == 200
                    data = response.json()
                    assert data["queued_count"] == 3
                    assert data["ids"] == [1, 2, 3]
                    assert mock_apply_async.call_count == 3
