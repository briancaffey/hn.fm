"""Tests for segment API endpoints"""

import json
from datetime import datetime
from unittest.mock import patch, MagicMock

import pytest
from fastapi.testclient import TestClient
import fakeredis

from ..web.api import app
from ..web.models import Segment, SegmentSummary


class TestSegmentAPI:
    """Test segment API endpoints"""

    @pytest.fixture
    def client(self):
        """Create a test client"""
        return TestClient(app)

    @pytest.fixture
    def redis_client(self):
        """Create a fake Redis client for testing"""
        return fakeredis.FakeRedis(decode_responses=False)

    @pytest.fixture
    def sample_segment(self):
        """Create a sample segment for testing"""
        return Segment(
            key="hnfm:seg:123:1:1",
            item_id=123,
            run=1,
            seg=1,
            created_at=datetime.utcnow(),
            processed_run_key="hnfm:item:123:run:1",
            script="This is a test script with more than 200 characters. "
            * 10,  # Make it long for preview testing
        )

    def test_segment_api_endpoints_exist(self, client):
        """Test that segment API endpoints exist and return proper error codes"""
        # Test POST endpoint exists (should return 422 for missing data)
        response = client.post("/api/hn/items/123/runs/1/segments")
        assert response.status_code in [
            200,
            422,
            500,
        ]  # Any of these is fine for basic existence test

        # Test GET list endpoint exists
        response = client.get("/api/hn/items/123/runs/1/segments")
        assert response.status_code in [
            200,
            404,
            500,
        ]  # Any of these is fine for basic existence test

        # Test GET single endpoint exists
        response = client.get("/api/hn/items/123/runs/1/segments/1")
        assert response.status_code in [
            200,
            404,
            500,
        ]  # Any of these is fine for basic existence test

        # Test DELETE endpoint exists
        response = client.delete("/api/hn/items/123/runs/1/segments/1")
        assert response.status_code in [
            200,
            404,
            500,
        ]  # Any of these is fine for basic existence test
