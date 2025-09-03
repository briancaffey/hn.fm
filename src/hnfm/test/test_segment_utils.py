"""Tests for segment utilities"""

import json
import os
import tempfile
import shutil
from datetime import datetime
from unittest.mock import patch, MagicMock

import pytest
import fakeredis

from ..utils.segment_utils import (
    k_seg,
    k_seg_seq,
    k_seg_list,
    seg_dir,
    next_seg_id,
    generate_script_v1,
    save_segment,
    get_segment,
    list_segments_for_run,
    delete_segment,
)
from ..web.models import Segment


class TestSegmentKeyHelpers:
    """Test Redis key helper functions"""

    def test_k_seg(self):
        """Test segment key generation"""
        assert k_seg(123, 1, 2) == "hnfm:seg:123:1:2"

    def test_k_seg_seq(self):
        """Test segment sequence key generation"""
        assert k_seg_seq(123, 1) == "hnfm:seg:seq:123:1"

    def test_k_seg_list(self):
        """Test segment list key generation"""
        assert k_seg_list(123, 1) == "hnfm:seg:list:123:1"

    def test_seg_dir(self):
        """Test segment directory path generation"""
        assert seg_dir("/outputs", 123, 1, 2) == "/outputs/hn/item/123/runs/1/segments/2"


class TestSegmentUtils:
    """Test segment utility functions"""

    @pytest.fixture
    def redis_client(self):
        """Create a fake Redis client for testing"""
        return fakeredis.FakeRedis(decode_responses=False)

    @pytest.fixture
    def temp_outputs_dir(self):
        """Create a temporary outputs directory"""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir)

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
            script="This is a test script."
        )

    def test_next_seg_id_increments(self, redis_client):
        """Test that next_seg_id increments correctly"""
        item_id, run = 123, 1

        # First call should return 1
        seg_id_1 = next_seg_id(item_id, run, redis_client=redis_client)
        assert seg_id_1 == 1

        # Second call should return 2
        seg_id_2 = next_seg_id(item_id, run, redis_client=redis_client)
        assert seg_id_2 == 2

    def test_generate_script_v1_function_exists(self):
        """Test that generate_script_v1 function exists and can be imported"""
        # Just test that the function exists and is callable
        assert callable(generate_script_v1)

    def test_save_and_get_segment_roundtrip(self, redis_client, temp_outputs_dir, sample_segment):
        """Test saving and getting a segment"""
        # Save segment
        save_segment(sample_segment, redis_client=redis_client, outputs_root=temp_outputs_dir)

        # Verify Redis storage
        key = k_seg(sample_segment.item_id, sample_segment.run, sample_segment.seg)
        stored_data = redis_client.get(key)
        assert stored_data is not None

        # Verify segment list
        list_key = k_seg_list(sample_segment.item_id, sample_segment.run)
        segment_ids = redis_client.lrange(list_key, 0, -1)
        assert [b"1"] == segment_ids

        # Verify disk storage
        expected_file = os.path.join(temp_outputs_dir, "hn/item/123/runs/1/segments/1/segment.json")
        assert os.path.exists(expected_file)

        # Get segment back
        retrieved_segment = get_segment(sample_segment.item_id, sample_segment.run, sample_segment.seg, redis_client=redis_client)
        assert retrieved_segment is not None
        assert retrieved_segment.item_id == sample_segment.item_id
        assert retrieved_segment.run == sample_segment.run
        assert retrieved_segment.seg == sample_segment.seg
        assert retrieved_segment.script == sample_segment.script

    def test_list_segments_for_run_newest_first(self, redis_client, temp_outputs_dir):
        """Test listing segments in newest-first order"""
        item_id, run = 123, 1

        # Create multiple segments
        segments = []
        for i in range(1, 4):
            segment = Segment(
                key=f"hnfm:seg:{item_id}:{run}:{i}",
                item_id=item_id,
                run=run,
                seg=i,
                created_at=datetime.utcnow(),
                processed_run_key=f"hnfm:item:{item_id}:run:{run}",
                script=f"Script {i}"
            )
            segments.append(segment)
            save_segment(segment, redis_client=redis_client, outputs_root=temp_outputs_dir)

        # List segments (should be newest-first)
        segment_ids = list_segments_for_run(item_id, run, redis_client=redis_client)
        assert segment_ids == [3, 2, 1]  # Newest first

    def test_list_segments_for_run_pagination(self, redis_client, temp_outputs_dir):
        """Test segment listing with pagination"""
        item_id, run = 123, 1

        # Create 5 segments
        for i in range(1, 6):
            segment = Segment(
                key=f"hnfm:seg:{item_id}:{run}:{i}",
                item_id=item_id,
                run=run,
                seg=i,
                created_at=datetime.utcnow(),
                processed_run_key=f"hnfm:item:{item_id}:run:{run}",
                script=f"Script {i}"
            )
            save_segment(segment, redis_client=redis_client, outputs_root=temp_outputs_dir)

        # Test pagination
        first_page = list_segments_for_run(item_id, run, redis_client=redis_client, offset=0, limit=2)
        assert first_page == [5, 4]

        second_page = list_segments_for_run(item_id, run, redis_client=redis_client, offset=2, limit=2)
        assert second_page == [3, 2]

    def test_delete_segment_removes_everything(self, redis_client, temp_outputs_dir, sample_segment):
        """Test that delete_segment removes everything"""
        # Save segment first
        save_segment(sample_segment, redis_client=redis_client, outputs_root=temp_outputs_dir)

        # Verify it exists
        key = k_seg(sample_segment.item_id, sample_segment.run, sample_segment.seg)
        assert redis_client.exists(key)

        expected_file = os.path.join(temp_outputs_dir, "hn/item/123/runs/1/segments/1/segment.json")
        assert os.path.exists(expected_file)

        # Delete segment
        success = delete_segment(sample_segment.item_id, sample_segment.run, sample_segment.seg,
                               redis_client=redis_client, outputs_root=temp_outputs_dir)
        assert success is True

        # Verify Redis key is gone
        assert not redis_client.exists(key)

        # Verify segment is removed from list
        list_key = k_seg_list(sample_segment.item_id, sample_segment.run)
        segment_ids = redis_client.lrange(list_key, 0, -1)
        assert len(segment_ids) == 0

        # Verify disk file is gone
        assert not os.path.exists(expected_file)
        assert not os.path.exists(os.path.dirname(expected_file))

    def test_delete_segment_not_found(self, redis_client, temp_outputs_dir):
        """Test deleting a non-existent segment"""
        success = delete_segment(123, 1, 999, redis_client=redis_client, outputs_root=temp_outputs_dir)
        assert success is False

    def test_get_segment_not_found(self, redis_client):
        """Test getting a non-existent segment"""
        segment = get_segment(123, 1, 999, redis_client=redis_client)
        assert segment is None
