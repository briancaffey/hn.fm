"""Tests for API endpoints (Postgres-backed data layer)"""

import asyncio
from unittest.mock import Mock, patch

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from ..db import repo
from ..web.api import (
    app,
    queue_top_stories,
    list_downloaded_items,
    get_single_item,
)
from ..web.models import HNItem


class TestAPIEndpoints:
    """Test API endpoints by calling the endpoint functions directly"""

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

        # Call the function directly (empty test DB: nothing exists yet)
        result = asyncio.run(queue_top_stories(limit=3))

        # Assertions
        assert result["queued_count"] == 3
        assert result["skipped_count"] == 0
        assert result["queued_ids"] == [1, 2, 3]
        assert result["limit"] == 3

        # Check apply_async was called correctly
        assert mock_apply_async.call_count == 3
        assert apply_async_calls == [[1], [2], [3]]

    @patch("hnfm.web.api.get_top_story_ids")
    @patch("hnfm.web.tasks.hn_fetch_item.apply_async")
    def test_queue_top_skips_existing_items(self, mock_apply_async, mock_get_top_ids):
        """Items already stored in the database are skipped, not re-queued"""
        mock_get_top_ids.return_value = [1, 2, 3]
        mock_apply_async.return_value = Mock()

        # Seed item 2 so it already exists
        repo.upsert_item(HNItem(id=2, title="Already stored"))

        result = asyncio.run(queue_top_stories(limit=3))

        assert result["queued_count"] == 2
        assert result["skipped_count"] == 1
        assert result["queued_ids"] == [1, 3]
        assert result["skipped_ids"] == [2]
        assert mock_apply_async.call_count == 2

    def test_list_items_endpoint(self):
        """Test list items endpoint"""
        # Seed test data via the data layer
        repo.upsert_item(HNItem(id=2, title="Item 2"))
        repo.upsert_item(HNItem(id=1, title="Item 1"))

        # Call the function directly
        result = asyncio.run(list_downloaded_items(offset=0, limit=2))

        # Assertions
        assert len(result["items"]) == 2
        assert result["items"][0]["id"] == 2  # Largest ID first
        assert result["items"][1]["id"] == 1
        assert result["pagination"]["offset"] == 0
        assert result["pagination"]["limit"] == 2
        assert result["pagination"]["count"] == 2
        assert result["pagination"]["total"] == 2

    def test_get_single_item_endpoint(self):
        """Test get single item endpoint"""
        # Seed test data via the data layer
        repo.upsert_item(HNItem(id=9, title="Test Item"))

        # Test existing item
        result = asyncio.run(get_single_item(item_id=9))
        assert result["id"] == 9
        assert result["title"] == "Test Item"

        # Test non-existing item
        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(get_single_item(item_id=999999))
        assert exc_info.value.status_code == 404
        assert "Item not found" in str(exc_info.value.detail)


class TestAPIEndpointsIntegration:
    """Integration tests using TestClient"""

    def test_queue_top_endpoint_integration(self):
        """Test the actual endpoint with mocked dependencies"""
        with patch("hnfm.web.api.get_top_story_ids") as mock_get_top_ids:
            mock_get_top_ids.return_value = [1, 2, 3, 4, 5]

            with patch("hnfm.web.tasks.hn_fetch_item.apply_async") as mock_apply_async:
                mock_apply_async.return_value = Mock()

                client = TestClient(app)
                response = client.post("/api/hn/queue-top?limit=3")

                assert response.status_code == 200
                data = response.json()
                assert data["queued_count"] == 3
                assert data["queued_ids"] == [1, 2, 3]
                assert mock_apply_async.call_count == 3

    def test_list_items_endpoint_integration(self):
        """Test the list endpoint against seeded database rows"""
        repo.upsert_item(HNItem(id=10, title="Ten"))
        repo.upsert_item(HNItem(id=20, title="Twenty"))

        client = TestClient(app)
        response = client.get("/api/hn/items?offset=0&limit=50")

        assert response.status_code == 200
        data = response.json()
        assert [i["id"] for i in data["items"]] == [20, 10]
        assert data["pagination"]["total"] == 2
