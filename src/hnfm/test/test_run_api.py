"""Tests for run API endpoints."""

import json
import pytest
from unittest.mock import patch, MagicMock
import fakeredis
from fastapi.testclient import TestClient

from ..web.api import app
from ..web.models import ProcessedRun, RunSummary
from datetime import datetime


class TestRunAPI:
    """Test run API endpoints."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)

    @pytest.fixture
    def fake_redis(self):
        """Create fake Redis client."""
        return fakeredis.FakeRedis(decode_responses=False)

    def test_api_endpoints_exist(self, client):
        """Test that the API endpoints exist and return proper status codes."""
        # Test POST endpoint exists (should return 200 with queued status)
        response = client.post("/api/hn/items/123/runs")
        assert response.status_code == 200
        data = response.json()
        assert "item_id" in data
        assert "run" in data
        assert "status" in data

        # Test GET list endpoint exists (should return 200 with empty runs)
        response = client.get("/api/hn/items/123/runs")
        assert response.status_code == 200
        data = response.json()
        assert "item_id" in data
        assert "runs" in data
        assert "pagination" in data

        # Test GET single endpoint exists (should return 404 for non-existent run)
        response = client.get("/api/hn/items/123/runs/1")
        assert response.status_code == 404

    def test_api_endpoints_validation(self, client):
        """Test that API endpoints validate input properly."""
        # Test with invalid item ID
        response = client.post("/api/hn/items/invalid/runs")
        assert response.status_code == 422  # Validation error

        response = client.get("/api/hn/items/invalid/runs")
        assert response.status_code == 422  # Validation error

        response = client.get("/api/hn/items/invalid/runs/1")
        assert response.status_code == 422  # Validation error

        # Test with invalid run ID
        response = client.get("/api/hn/items/123/runs/invalid")
        assert response.status_code == 422  # Validation error
