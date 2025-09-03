"""Tests for run processing tasks."""

import json
import pytest
from unittest.mock import patch, MagicMock
import fakeredis

from ..web.tasks import process_hn_item_run


class TestRunTasks:
    """Test run processing tasks."""

    def test_process_hn_item_run_network_skip(self):
        """Test that process_hn_item_run handles network errors gracefully."""
        # Mock Redis client
        fake_redis = fakeredis.FakeRedis(decode_responses=False)

        # Seed item data
        item_data = {
            "id": 123,
            "title": "Test Article",
            "url": "https://example.com"
        }
        item_key = "hn:item:123"
        fake_redis.set(item_key, json.dumps(item_data).encode())

        # Mock Redis client creation
        with patch('src.hnfm.web.tasks.redis.Redis', return_value=fake_redis):
            with patch('src.hnfm.web.tasks.os.getenv') as mock_getenv:
                mock_getenv.side_effect = lambda key, default=None: {
                    "REDIS_HOST": "localhost",
                    "REDIS_PORT": "6379",
                    "REDIS_DB": "0",
                    "OUTPUTS_DIR": "/tmp"
                }.get(key, default)

                # Call the task - should raise due to network error
                with pytest.raises(RuntimeError, match="Failed to scrape"):
                    process_hn_item_run(123, 1)

    def test_process_hn_item_run_missing_item_raises(self):
        """Test that missing item raises exception."""
        # Mock Redis client with no item
        fake_redis = fakeredis.FakeRedis(decode_responses=False)

        with patch('src.hnfm.web.tasks.redis.Redis', return_value=fake_redis):
            with patch('src.hnfm.web.tasks.os.getenv') as mock_getenv:
                mock_getenv.side_effect = lambda key, default=None: {
                    "REDIS_HOST": "localhost",
                    "REDIS_PORT": "6379",
                    "REDIS_DB": "0",
                    "OUTPUTS_DIR": "/tmp"
                }.get(key, default)

                # Call the task - should raise
                with pytest.raises(RuntimeError, match="Item 123 not found"):
                    process_hn_item_run(123, 1)

    def test_process_hn_item_run_missing_url_raises(self):
        """Test that item without URL raises exception."""
        # Mock Redis client
        fake_redis = fakeredis.FakeRedis(decode_responses=False)

        # Seed item data without URL
        item_data = {
            "id": 123,
            "title": "Test Article"
            # No URL field
        }
        item_key = "hn:item:123"
        fake_redis.set(item_key, json.dumps(item_data).encode())

        with patch('src.hnfm.web.tasks.redis.Redis', return_value=fake_redis):
            with patch('src.hnfm.web.tasks.os.getenv') as mock_getenv:
                mock_getenv.side_effect = lambda key, default=None: {
                    "REDIS_HOST": "localhost",
                    "REDIS_PORT": "6379",
                    "REDIS_DB": "0",
                    "OUTPUTS_DIR": "/tmp"
                }.get(key, default)

                # Call the task - should raise
                with pytest.raises(RuntimeError, match="Item 123 has no URL"):
                    process_hn_item_run(123, 1)

    def test_process_hn_item_run_scrape_failure_raises(self):
        """Test that scrape failure raises exception."""
        # Mock Redis client
        fake_redis = fakeredis.FakeRedis(decode_responses=False)

        # Seed item data
        item_data = {
            "id": 123,
            "title": "Test Article",
            "url": "https://example.com"
        }
        item_key = "hn:item:123"
        fake_redis.set(item_key, json.dumps(item_data).encode())

        with patch('src.hnfm.web.tasks.redis.Redis', return_value=fake_redis):
            with patch('src.hnfm.web.tasks.os.getenv') as mock_getenv:
                mock_getenv.side_effect = lambda key, default=None: {
                    "REDIS_HOST": "localhost",
                    "REDIS_PORT": "6379",
                    "REDIS_DB": "0",
                    "OUTPUTS_DIR": "/tmp"
                }.get(key, default)

                # Call the task - should raise due to network error
                with pytest.raises(RuntimeError, match="Failed to scrape"):
                    process_hn_item_run(123, 1)
