"""Metrics identity fields and honest status (issues #21 and #23)."""

import os
from unittest.mock import patch

import pytest

from ..utils import metrics
from ..web import tasks

ITEM, RUN, SEG = 771, 1, 1


class TestAnnotate:
    def test_annotate_fills_fields_init_could_not_know(self):
        """The theme is chosen during image generation, so `init` can only
        record the caller's override — None on an ordinary run."""
        metrics.init(ITEM, RUN, SEG, title="T", theme=None, fmt=None)
        assert metrics.get_record(ITEM, RUN, SEG)["theme"] is None

        metrics.annotate(ITEM, RUN, SEG, theme="Blueprint", format="9:16")

        rec = metrics.get_record(ITEM, RUN, SEG)
        assert rec["theme"] == "Blueprint"
        assert rec["format"] == "9:16"
        assert rec["title"] == "T"

    def test_annotate_never_erases_a_known_value_with_none(self):
        metrics.init(ITEM, RUN, SEG, title="T")
        metrics.annotate(ITEM, RUN, SEG, theme="Blueprint")
        metrics.annotate(ITEM, RUN, SEG, theme=None)
        assert metrics.get_record(ITEM, RUN, SEG)["theme"] == "Blueprint"

    def test_annotate_is_non_fatal(self):
        with patch.object(metrics.repo, "save_metrics", side_effect=RuntimeError):
            metrics.annotate(ITEM, RUN, SEG, theme="x")  # must not raise


class TestArtifactStatus:
    def test_missing_artifact_is_partial_not_ok(self, tmp_path):
        """A run once finished in 84s with status 'ok', format '16:9' and no
        video at all."""
        with patch.dict(os.environ, {"OUTPUTS_DIR": str(tmp_path)}):
            status, why = tasks._artifact_status(999, 1, 1, "video")
        assert status == "partial"
        assert "never produced" in why

    def test_a_real_artifact_is_ok(self, tmp_path):
        seg_dir = tmp_path / "hn" / "item" / "999" / "runs" / "1" / "segments" / "1" / "video"
        seg_dir.mkdir(parents=True)
        (seg_dir / "segment.mp4").write_bytes(b"x" * 5000)

        with patch.dict(os.environ, {"OUTPUTS_DIR": str(tmp_path)}):
            status, why = tasks._artifact_status(999, 1, 1, "video")
        assert (status, why) == ("ok", None)

    def test_a_truncated_encode_is_partial(self, tmp_path):
        """A near-empty file is a failed encode, not an artifact."""
        seg_dir = tmp_path / "hn" / "item" / "999" / "runs" / "1" / "segments" / "1" / "video"
        seg_dir.mkdir(parents=True)
        (seg_dir / "segment.mp4").write_bytes(b"x" * 10)

        with patch.dict(os.environ, {"OUTPUTS_DIR": str(tmp_path)}):
            status, why = tasks._artifact_status(999, 1, 1, "video")
        assert status == "partial"
        assert "10 bytes" in why

    def test_audio_mode_checks_the_episode_not_the_video(self, tmp_path):
        seg_dir = tmp_path / "hn" / "item" / "999" / "runs" / "1" / "segments" / "1" / "audio"
        seg_dir.mkdir(parents=True)
        (seg_dir / "episode.mp3").write_bytes(b"x" * 5000)

        with patch.dict(os.environ, {"OUTPUTS_DIR": str(tmp_path)}):
            assert tasks._artifact_status(999, 1, 1, "audio")[0] == "ok"
            assert tasks._artifact_status(999, 1, 1, "video")[0] == "partial"
