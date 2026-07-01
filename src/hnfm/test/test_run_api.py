"""Tests for run API endpoints (Postgres-backed data layer)."""

from datetime import datetime
from unittest.mock import Mock, patch

import pytest
from fastapi.testclient import TestClient

from ..db import repo
from ..web.api import app
from ..web.models import HNItem, ProcessedRun


def seed_run(item_id: int = 123, run: int = 1, summary: str = "Test summary") -> None:
    """Seed an item and a processed run (item first — FK constraint)."""
    repo.upsert_item(HNItem(id=item_id, title=f"Item {item_id}"))
    repo.save_run(
        ProcessedRun(
            key=f"hnfm:item:{item_id}:run:{run}",
            item_id=item_id,
            run=run,
            created_at=datetime.utcnow(),
            source_url="https://example.com/article",
            content_raw="raw content",
            content_clean="clean content",
            summary=summary,
            short_description="A short description",
            tags=["testing", "api"],
            emoji=["🔥", "🚀", "🎧", "📰"],
            haiku="tests run swiftly by / postgres holds the pipeline state / green marks fill the screen",
        )
    )


class TestRunAPI:
    """Test run API endpoints."""

    @pytest.fixture
    def client(self):
        """Create test client (inside the test so it uses the test DB)."""
        return TestClient(app)

    def test_api_endpoints_exist(self, client):
        """Test that the API endpoints exist and return proper status codes."""
        # Test POST endpoint exists (should return 200 with queued status)
        with patch("hnfm.web.tasks.process_hn_item_run.apply_async") as mock_apply:
            mock_apply.return_value = Mock()
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

    def test_create_run_queues_task(self, client):
        """POST creates sequential run IDs and queues the Celery task."""
        with patch("hnfm.web.tasks.process_hn_item_run.apply_async") as mock_apply:
            mock_apply.return_value = Mock()

            response = client.post("/api/hn/items/123/runs")
            assert response.status_code == 200
            data = response.json()
            assert data == {"item_id": 123, "run": 1, "status": "queued"}

            # Second run for the same item increments the counter
            response = client.post("/api/hn/items/123/runs")
            assert response.status_code == 200
            assert response.json()["run"] == 2

            assert mock_apply.call_count == 2
            # continue_chain defaults to False
            assert mock_apply.call_args_list[0].kwargs["queue"] == "hnfm_tasks"
            assert mock_apply.call_args_list[0].kwargs["args"] == [123, 1, False]

    def test_get_single_run(self, client):
        """GET single run returns the seeded run data."""
        seed_run(item_id=123, run=1, summary="Seeded summary")

        response = client.get("/api/hn/items/123/runs/1")
        assert response.status_code == 200
        data = response.json()
        assert data["item_id"] == 123
        assert data["run"] == 1
        assert data["summary"] == "Seeded summary"
        assert data["source_url"] == "https://example.com/article"
        assert data["tags"] == ["testing", "api"]

    def test_list_runs_returns_summaries(self, client):
        """GET list returns run summaries newest-first with pagination."""
        seed_run(item_id=123, run=1, summary="first run")
        seed_run(item_id=123, run=2, summary="second run")

        response = client.get("/api/hn/items/123/runs")
        assert response.status_code == 200
        data = response.json()
        assert data["item_id"] == 123
        assert [r["run"] for r in data["runs"]] == [2, 1]
        assert data["runs"][0]["summary"] == "second run"
        assert data["pagination"]["count"] == 2

    def test_delete_run(self, client):
        """DELETE removes the run; a second delete returns 404."""
        seed_run(item_id=123, run=1)

        response = client.delete("/api/hn/items/123/runs/1")
        assert response.status_code == 200
        assert response.json()["success"] is True

        # Run is gone
        assert client.get("/api/hn/items/123/runs/1").status_code == 404

        # Deleting again returns 404
        response = client.delete("/api/hn/items/123/runs/1")
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
