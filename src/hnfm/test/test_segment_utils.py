"""Tests for segment utilities (Postgres data layer)."""

import os
from datetime import datetime

from ..db import repo
from ..utils.segment_utils import (
    k_seg,
    seg_dir,
    next_seg_id,
    generate_script_v1,
    save_segment,
    get_segment,
    list_segments_for_run,
    list_all_segments,
    count_all_segments,
    delete_segment,
)
from ..web.models import HNItem, ProcessedRun, Segment


def _seed_run(item_id: int = 123, run: int = 1) -> None:
    """Create the FK parents a segment needs (hn item + run)."""
    repo.upsert_item(HNItem(id=item_id))
    repo.save_run(
        ProcessedRun(
            key=f"hnfm:item:{item_id}:run:{run}",
            item_id=item_id,
            run=run,
            created_at=datetime.utcnow(),
            source_url="https://example.com",
            content_raw="Raw content",
            content_clean="Clean content",
            summary="Summary",
            short_description="Short description",
            tags=["tech"],
            emoji=["🤖"],
            haiku="Test haiku",
        )
    )


def _make_segment(item_id: int = 123, run: int = 1, seg: int = 1, script: str = None) -> Segment:
    return Segment(
        key=k_seg(item_id, run, seg),
        item_id=item_id,
        run=run,
        seg=seg,
        created_at=datetime.utcnow(),
        processed_run_key=f"hnfm:item:{item_id}:run:{run}",
        script=script if script is not None else f"Script {seg}",
    )


class TestSegmentKeyHelpers:
    """Test legacy key-string and disk-path helpers"""

    def test_k_seg(self):
        """Test segment key generation"""
        assert k_seg(123, 1, 2) == "hnfm:seg:123:1:2"

    def test_seg_dir(self):
        """Test segment directory path generation"""
        assert (
            seg_dir("/outputs", 123, 1, 2) == "/outputs/hn/item/123/runs/1/segments/2"
        )


class TestSegmentUtils:
    """Test segment utility functions"""

    def test_next_seg_id_increments(self):
        """Test that next_seg_id increments correctly"""
        item_id, run = 123, 1

        # First call should return 1
        assert next_seg_id(item_id, run) == 1

        # Second call should return 2
        assert next_seg_id(item_id, run) == 2

        # A different run has its own counter
        assert next_seg_id(item_id, 2) == 1

    def test_generate_script_v1_function_exists(self):
        """Test that generate_script_v1 function exists and can be imported"""
        assert callable(generate_script_v1)

    def test_save_and_get_segment_roundtrip(self, outputs_root):
        """Test saving and getting a segment"""
        _seed_run()
        sample_segment = _make_segment(script="This is a test script.")

        # Save segment
        save_segment(sample_segment, outputs_root=outputs_root)

        # Verify it shows up in the run's segment list
        assert list_segments_for_run(123, 1) == [1]

        # Verify disk storage
        expected_file = os.path.join(
            outputs_root, "hn/item/123/runs/1/segments/1/segment.json"
        )
        assert os.path.exists(expected_file)

        # Get segment back
        retrieved_segment = get_segment(
            sample_segment.item_id, sample_segment.run, sample_segment.seg
        )
        assert retrieved_segment is not None
        assert retrieved_segment.item_id == sample_segment.item_id
        assert retrieved_segment.run == sample_segment.run
        assert retrieved_segment.seg == sample_segment.seg
        assert retrieved_segment.script == sample_segment.script

    def test_list_segments_for_run_newest_first(self, outputs_root):
        """Test listing segments in newest-first order"""
        item_id, run = 123, 1
        _seed_run(item_id, run)

        # Create multiple segments
        for i in range(1, 4):
            save_segment(_make_segment(item_id, run, i), outputs_root=outputs_root)

        # List segments (should be newest-first)
        segment_ids = list_segments_for_run(item_id, run)
        assert segment_ids == [3, 2, 1]  # Newest first

        # Global helpers see them too
        assert count_all_segments() == 3
        assert len(list_all_segments()) == 3

    def test_list_segments_for_run_pagination(self, outputs_root):
        """Test segment listing with pagination"""
        item_id, run = 123, 1
        _seed_run(item_id, run)

        # Create 5 segments
        for i in range(1, 6):
            save_segment(_make_segment(item_id, run, i), outputs_root=outputs_root)

        # Test pagination
        first_page = list_segments_for_run(item_id, run, offset=0, limit=2)
        assert first_page == [5, 4]

        second_page = list_segments_for_run(item_id, run, offset=2, limit=2)
        assert second_page == [3, 2]

    def test_delete_segment_removes_everything(self, outputs_root):
        """Test that delete_segment removes everything"""
        _seed_run()
        sample_segment = _make_segment()

        # Save segment first
        save_segment(sample_segment, outputs_root=outputs_root)

        # Verify it exists (DB + disk)
        assert get_segment(123, 1, 1) is not None

        expected_file = os.path.join(
            outputs_root, "hn/item/123/runs/1/segments/1/segment.json"
        )
        assert os.path.exists(expected_file)

        # Delete segment
        success = delete_segment(
            sample_segment.item_id,
            sample_segment.run,
            sample_segment.seg,
            outputs_root=outputs_root,
        )
        assert success is True

        # Verify DB row is gone
        assert get_segment(123, 1, 1) is None

        # Verify segment is removed from the run's list
        assert list_segments_for_run(123, 1) == []

        # Verify disk file is gone
        assert not os.path.exists(expected_file)
        assert not os.path.exists(os.path.dirname(expected_file))

    def test_delete_segment_not_found(self, outputs_root):
        """Test deleting a non-existent segment"""
        success = delete_segment(123, 1, 999, outputs_root=outputs_root)
        assert success is False

    def test_get_segment_not_found(self):
        """Test getting a non-existent segment"""
        assert get_segment(123, 1, 999) is None
