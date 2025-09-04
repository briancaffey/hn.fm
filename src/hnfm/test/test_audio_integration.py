"""Integration tests for audio functionality"""

import pytest
from unittest.mock import Mock, patch
from fastapi.testclient import TestClient

from ..web.api import app


class TestAudioIntegration:
    """Test audio functionality integration"""

    @pytest.fixture
    def client(self):
        """Create test client"""
        return TestClient(app)

    @patch("src.hnfm.web.api.build_segment_audio")
    def test_audio_api_endpoints(self, mock_build_task, client):
        """Test that audio API endpoints are accessible and queue tasks"""
        # Mock the task
        mock_task = Mock()
        mock_task.apply_async.return_value = mock_task
        mock_build_task.return_value = mock_task

        # Test build all audio endpoint
        response = client.post("/api/hn/items/123/runs/1/segments/2/audio")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "queued"
        assert data["mode"] == "all"

        # Test build one section endpoint
        response = client.post("/api/hn/items/123/runs/1/segments/2/sections/3/audio")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "queued"
        assert data["mode"] == "one"
        assert data["section"] == 3

        # Test list sections endpoint (should return empty list for non-existent segment)
        response = client.get("/api/hn/items/123/runs/1/segments/2/sections")
        assert response.status_code == 200
        data = response.json()
        assert data["sections"] == []

    def test_audio_utils_functions(self):
        """Test that audio utility functions work correctly"""
        from ..audio.audio_utils import split_script_into_sections, k_sec, k_sec_list

        # Test script splitting
        script = "[S1] Line 1\n[S2] Line 2\n[S1] Line 3"
        sections = split_script_into_sections(script)
        assert len(sections) == 2
        assert sections[0] == "[S1] Line 1\n[S2] Line 2"
        assert sections[1] == "[S1] Line 3"

        # Test key generation
        assert k_sec(123, 1, 2, 3) == "hnfm:seg:123:1:2:sec:3"
        assert k_sec_list(123, 1, 2) == "hnfm:seg:123:1:2:sec:list"

    def test_segment_model_audio_fields(self):
        """Test that Segment model has audio fields"""
        from ..web.models import Segment, SegmentSection
        from datetime import datetime

        # Test Segment model with audio fields
        segment = Segment(
            key="hnfm:seg:123:1:2",
            item_id=123,
            run=1,
            seg=2,
            created_at=datetime.utcnow(),
            processed_run_key="hnfm:item:123:run:1",
            script="[S1] Test script",
            sections_total=2,
            audio_combined_path="/path/to/audio.wav",
            audio_ready=True,
        )

        assert segment.sections_total == 2
        assert segment.audio_combined_path == "/path/to/audio.wav"
        assert segment.audio_ready is True

        # Test SegmentSection model
        section = SegmentSection(
            key="hnfm:seg:123:1:2:sec:1",
            item_id=123,
            run=1,
            seg=2,
            section=1,
            text="[S1] Test text",
            audio_path="/path/to/section.wav",
            cleaned=True,
            duration_ms=1000,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

        assert section.section == 1
        assert section.text == "[S1] Test text"
        assert section.cleaned is True
        assert section.duration_ms == 1000
