"""Tests for segment API endpoints (Postgres-backed data layer)"""

from datetime import datetime
from unittest.mock import Mock, patch

import pytest
from fastapi.testclient import TestClient

from ..db import repo
from ..web.api import app
from ..web.models import HNItem, ProcessedRun, Segment

LONG_SCRIPT = "This is a test script with more than 200 characters. " * 10


def seed_segment(item_id: int = 123, run: int = 1, seg: int = 1, script: str = LONG_SCRIPT) -> Segment:
    """Seed item -> run -> segment (in FK order) and return the Segment."""
    repo.upsert_item(HNItem(id=item_id, title=f"Item {item_id}"))
    repo.save_run(
        ProcessedRun(
            key=f"hnfm:item:{item_id}:run:{run}",
            item_id=item_id,
            run=run,
            created_at=datetime.utcnow(),
            source_url="https://example.com/article",
            content_raw="raw",
            content_clean="clean",
            summary="summary",
            short_description="short",
            tags=["tag"],
            emoji=["🔥", "🚀", "🎧", "📰"],
            haiku="haiku",
        )
    )
    segment = Segment(
        key=f"hnfm:seg:{item_id}:{run}:{seg}",
        item_id=item_id,
        run=run,
        seg=seg,
        created_at=datetime.utcnow(),
        processed_run_key=f"hnfm:item:{item_id}:run:{run}",
        script=script,
    )
    repo.save_segment(segment)
    return segment


class TestSegmentAPI:
    """Test segment API endpoints"""

    @pytest.fixture
    def client(self):
        """Create a test client (inside the test so it uses the test DB)"""
        return TestClient(app)

    def test_segment_api_endpoints_exist(self, client):
        """Test that segment API endpoints exist and return proper status codes"""
        # Test POST endpoint exists (queues a segment task)
        with patch("hnfm.web.tasks.generate_segment.apply_async") as mock_apply:
            mock_apply.return_value = Mock()
            response = client.post("/api/hn/items/123/runs/1/segments")
        assert response.status_code == 200
        data = response.json()
        assert "item_id" in data
        assert "run" in data
        assert "seg" in data
        assert "status" in data

        # Test GET list endpoint exists (empty list is fine)
        response = client.get("/api/hn/items/123/runs/1/segments")
        assert response.status_code == 200

        # Test GET single endpoint exists (404 for non-existent segment)
        response = client.get("/api/hn/items/123/runs/1/segments/1")
        assert response.status_code == 404

        # Test DELETE endpoint exists (404 for non-existent segment)
        response = client.delete("/api/hn/items/123/runs/1/segments/1")
        assert response.status_code == 404

    def test_create_segment_queues_task(self, client):
        """POST creates sequential segment IDs and queues the Celery task"""
        with patch("hnfm.web.tasks.generate_segment.apply_async") as mock_apply:
            mock_apply.return_value = Mock()

            response = client.post("/api/hn/items/123/runs/1/segments")
            assert response.status_code == 200
            data = response.json()
            assert data == {"item_id": 123, "run": 1, "seg": 1, "status": "queued"}

            # Next segment for the same run increments
            response = client.post("/api/hn/items/123/runs/1/segments")
            assert response.json()["seg"] == 2

            assert mock_apply.call_count == 2
            assert mock_apply.call_args_list[0].kwargs["args"] == [123, 1, 1, False]
            assert mock_apply.call_args_list[0].kwargs["queue"] == "hnfm_tasks"

    def test_get_single_segment(self, client):
        """GET single segment returns the seeded segment"""
        seed_segment(item_id=123, run=1, seg=1)

        response = client.get("/api/hn/items/123/runs/1/segments/1")
        assert response.status_code == 200
        data = response.json()
        assert data["item_id"] == 123
        assert data["run"] == 1
        assert data["seg"] == 1
        assert data["script"] == LONG_SCRIPT
        assert data["key"] == "hnfm:seg:123:1:1"
        assert data["processed_run_key"] == "hnfm:item:123:run:1"

    def test_list_segments_with_preview(self, client):
        """GET list returns segment summaries with a truncated script preview"""
        seed_segment(item_id=123, run=1, seg=1)

        response = client.get("/api/hn/items/123/runs/1/segments")
        assert response.status_code == 200
        data = response.json()
        assert data["item_id"] == 123
        assert data["run"] == 1
        assert len(data["segments"]) == 1

        summary = data["segments"][0]
        assert summary["seg"] == 1
        # Scripts longer than 200 chars are truncated with an ellipsis
        assert summary["script_preview"] == LONG_SCRIPT[:200] + "..."
        assert data["pagination"]["count"] == 1

    def test_list_all_segments(self, client):
        """GET /api/segments lists segments across items/runs with a total"""
        seed_segment(item_id=123, run=1, seg=1, script="short script")

        response = client.get("/api/segments")
        assert response.status_code == 200
        data = response.json()
        assert len(data["segments"]) == 1
        assert data["segments"][0]["item_id"] == 123
        assert data["segments"][0]["script"] == "short script"
        assert data["pagination"]["total"] == 1

    def test_delete_segment(self, client):
        """DELETE removes the segment; a second delete returns 404"""
        seed_segment(item_id=123, run=1, seg=1)

        response = client.delete("/api/hn/items/123/runs/1/segments/1")
        assert response.status_code == 200
        data = response.json()
        assert data == {"item_id": 123, "run": 1, "seg": 1, "status": "deleted"}

        # Segment is gone
        assert client.get("/api/hn/items/123/runs/1/segments/1").status_code == 404

        # Deleting again returns 404
        response = client.delete("/api/hn/items/123/runs/1/segments/1")
        assert response.status_code == 404
