"""Tests for segment Celery tasks"""

import json
from datetime import datetime
from unittest.mock import patch, MagicMock

import pytest
import fakeredis

from ..web.tasks import generate_segment
from ..web.models import ProcessedRun


class TestGenerateSegmentTask:
    """Test the generate_segment Celery task"""

    @pytest.fixture
    def redis_client(self):
        """Create a fake Redis client for testing"""
        return fakeredis.FakeRedis(decode_responses=False)

    @pytest.fixture
    def sample_processed_run(self):
        """Create a sample ProcessedRun for testing"""
        return ProcessedRun(
            key="hnfm:item:123:run:1",
            item_id=123,
            run=1,
            created_at=datetime.utcnow(),
            source_url="https://example.com",
            content_raw="Raw content",
            content_clean="Clean content for script generation",
            summary="Article summary",
            short_description="Short description",
            tags=["tech", "ai"],
            emoji=["🤖", "💻", "🚀", "⚡"],
            haiku="Technology grows\nArtificial intelligence\nFuture is bright",
        )

    def test_generate_segment_function_exists(self):
        """Test that generate_segment function exists and is callable"""
        # Just test that the function exists and is callable
        assert callable(generate_segment)

    @patch("src.hnfm.web.tasks.redis.Redis")
    def test_generate_segment_missing_run_raises(self, mock_redis_class, redis_client):
        """Test segment generation when processed run is missing"""
        # Setup mocks
        mock_redis_class.return_value = redis_client

        # Don't store any processed run in Redis

        # Mock environment variables
        with patch.dict(
            "os.environ",
            {
                "REDIS_HOST": "localhost",
                "REDIS_PORT": "6379",
                "REDIS_DB": "0",
                "OUTPUTS_DIR": "/app/outputs",
            },
        ):
            # Call the task and expect exception
            with pytest.raises(
                RuntimeError,
                match="ProcessedRun hnfm:item:123:run:1 not found in Redis",
            ):
                generate_segment(123, 1, 1)

    @patch("src.hnfm.web.tasks.redis.Redis")
    def test_generate_segment_empty_fields_raises(self, mock_redis_class, redis_client):
        """Test segment generation when processed run has empty content_clean or summary"""
        # Setup mocks
        mock_redis_class.return_value = redis_client

        # Store processed run with empty content_clean
        processed_run_data = {
            "key": "hnfm:item:123:run:1",
            "item_id": 123,
            "run": 1,
            "created_at": datetime.utcnow().isoformat(),
            "source_url": "https://example.com",
            "content_raw": "Raw content",
            "content_clean": "",  # Empty content_clean
            "summary": "Article summary",
            "short_description": "Short description",
            "tags": ["tech"],
            "emoji": ["🤖"],
            "haiku": "Test haiku",
        }
        redis_client.set("hnfm:item:123:run:1", json.dumps(processed_run_data))

        # Mock environment variables
        with patch.dict(
            "os.environ",
            {
                "REDIS_HOST": "localhost",
                "REDIS_PORT": "6379",
                "REDIS_DB": "0",
                "OUTPUTS_DIR": "/app/outputs",
            },
        ):
            # Call the task and expect exception
            with pytest.raises(
                RuntimeError,
                match="ProcessedRun hnfm:item:123:run:1 missing content_clean or summary",
            ):
                generate_segment(123, 1, 1)

    def test_generate_segment_imports_work(self):
        """Test that all required imports work for the task"""
        # Test that we can import the task function
        from ..web.tasks import generate_segment

        assert callable(generate_segment)
