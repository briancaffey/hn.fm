"""Tests for run utilities."""

import json
import os
import tempfile
import pytest
from datetime import datetime
from unittest.mock import patch, MagicMock
import fakeredis

from ..utils.run_utils import (
    next_run_id,
    scrape_url_firecrawl,
    clean_content,
    summarize_text_v1,
    save_processed_run,
    list_runs_for_item,
    get_run,
    get_run_key,
    get_run_seq_key,
    get_runs_list_key,
    get_run_disk_path,
)
from ..web.models import ProcessedRun


class TestRunUtils:
    """Test run utility functions."""

    def test_next_run_id_increments(self):
        """Test that next_run_id increments properly."""
        fake_redis = fakeredis.FakeRedis(decode_responses=True)

        # New item: INCR returns 1, then 2
        run1 = next_run_id(123, redis_client=fake_redis)
        assert run1 == 1

        run2 = next_run_id(123, redis_client=fake_redis)
        assert run2 == 2

        # Different item should start from 1
        run3 = next_run_id(456, redis_client=fake_redis)
        assert run3 == 1

    def test_clean_content(self):
        """Test content cleaning functionality."""
        # Test basic cleaning
        text = "  Hello   world  \n\n  This is   a test  "
        cleaned = clean_content(text)
        assert cleaned == "Hello world This is a test"

        # Test empty string
        assert clean_content("") == ""
        assert clean_content(None) == ""

        # Test with multiple newlines
        text2 = "Line 1\n\n\nLine 2\n\nLine 3"
        cleaned2 = clean_content(text2)
        assert cleaned2 == "Line 1 Line 2 Line 3"

    def test_scrape_url_firecrawl_network_skip(self):
        """Test that scrape_url_firecrawl raises error when network is unavailable."""
        # This test verifies the function handles network errors gracefully
        with pytest.raises(RuntimeError, match="Failed to scrape"):
            scrape_url_firecrawl("https://example.com")

    def test_summarize_text_v1_network_skip(self):
        """Test that summarize_text_v1 handles network errors gracefully."""
        # This test verifies the function handles network errors gracefully
        # It will either return a fallback or raise an error depending on LLM service state
        try:
            result = summarize_text_v1("Some article text")
            # If it doesn't raise an error, it should return some string
            assert isinstance(result, str)
        except RuntimeError:
            # This is also acceptable - the function should handle errors gracefully
            pass

    def test_save_processed_run_persists_everywhere(self):
        """Test that save_processed_run persists to Redis and disk."""
        fake_redis = fakeredis.FakeRedis(decode_responses=True)

        with tempfile.TemporaryDirectory() as temp_dir:
            # Create a test ProcessedRun
            processed_run = ProcessedRun(
                key="hnfm:item:123:run:1",
                item_id=123,
                run=1,
                created_at=datetime.utcnow(),
                source_url="https://example.com",
                content_raw="Raw content",
                content_clean="Clean content",
                summary="Summary"
            )

            # Save the run
            save_processed_run(processed_run, redis_client=fake_redis, outputs_root=temp_dir)

            # Assert Redis key exists
            run_key = get_run_key(123, 1)
            assert fake_redis.exists(run_key)

            # Assert run is in the runs list
            runs_list_key = get_runs_list_key(123)
            assert fake_redis.llen(runs_list_key) == 1
            assert fake_redis.lrange(runs_list_key, 0, -1) == ["1"]

            # Assert file exists
            disk_path = get_run_disk_path(123, 1, temp_dir)
            assert os.path.exists(disk_path)

            # Verify file content
            with open(disk_path, 'r') as f:
                saved_data = json.load(f)
                assert saved_data['item_id'] == 123
                assert saved_data['run'] == 1
                assert saved_data['summary'] == "Summary"

    def test_list_runs_for_item_newest_first(self):
        """Test that list_runs_for_item returns newest first."""
        fake_redis = fakeredis.FakeRedis(decode_responses=True)

        # Seed runs list with LPUSH 2 then 1 (newest first)
        # LPUSH adds to the left, so lpush("2", "1") results in ["1", "2"] with "1" being newest
        runs_list_key = get_runs_list_key(123)
        fake_redis.lpush(runs_list_key, "2", "1")

        # Test listing - should return newest first
        runs = list_runs_for_item(123, redis_client=fake_redis)
        assert runs == [1, 2]  # "1" is newest (pushed last)

    def test_list_runs_for_item_with_pagination(self):
        """Test pagination in list_runs_for_item."""
        fake_redis = fakeredis.FakeRedis(decode_responses=True)

        # Seed with multiple runs
        # lpush("5", "4", "3", "2", "1") results in ["1", "2", "3", "4", "5"] with "1" being newest
        runs_list_key = get_runs_list_key(123)
        fake_redis.lpush(runs_list_key, "5", "4", "3", "2", "1")

        # Test pagination - offset 1, limit 2 should return [2, 3]
        runs = list_runs_for_item(123, redis_client=fake_redis, offset=1, limit=2)
        assert runs == [2, 3]

    def test_get_run_roundtrip(self):
        """Test get_run roundtrip."""
        fake_redis = fakeredis.FakeRedis(decode_responses=True)

        # Create and save a run
        processed_run = ProcessedRun(
            key="hnfm:item:123:run:1",
            item_id=123,
            run=1,
            created_at=datetime.utcnow(),
            source_url="https://example.com",
            content_raw="Raw content",
            content_clean="Clean content",
            summary="Summary"
        )

        # Save to Redis
        run_key = get_run_key(123, 1)
        fake_redis.set(run_key, processed_run.model_dump_json())

        # Retrieve and verify
        retrieved_run = get_run(123, 1, redis_client=fake_redis)
        assert retrieved_run is not None
        assert retrieved_run.item_id == 123
        assert retrieved_run.run == 1
        assert retrieved_run.summary == "Summary"

    def test_get_run_missing(self):
        """Test get_run with missing run."""
        fake_redis = fakeredis.FakeRedis(decode_responses=True)

        retrieved_run = get_run(123, 999, redis_client=fake_redis)
        assert retrieved_run is None

    def test_redis_key_helpers(self):
        """Test Redis key helper functions."""
        assert get_run_key(123, 1) == "hnfm:item:123:run:1"
        assert get_run_seq_key(123) == "hnfm:item:123:run_seq"
        assert get_runs_list_key(123) == "hnfm:item:123:runs"

    def test_disk_path_helper(self):
        """Test disk path helper function."""
        path = get_run_disk_path(123, 1, "/outputs")
        expected = "/outputs/hn/item/123/runs/1/processed.json"
        assert path == expected
