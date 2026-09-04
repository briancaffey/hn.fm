"""Tests for the pipeline audit trail.

Covers the recorder (db/steps.py), the rerun_step Celery task routing
(web/tasks.py), and the steps API endpoints (web/api.py). The autouse
fixtures in conftest.py give every test a fresh sqlite DB with the schema
pre-created plus isolated outputs dirs.
"""

from datetime import datetime
from unittest import mock

import pytest
from fastapi.testclient import TestClient

from ..db import repo, steps
from ..db.engine import db_session
from ..db.orm import PipelineStepRow
from ..web import tasks
from ..web.models import HNItem, ProcessedRun, Segment

ITEM, RUN, SEG = 101, 1, 1


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _insert_step(
    item_id=ITEM,
    run=RUN,
    seg=SEG,
    stage="stage",
    step_key="step",
    status="ok",
    **kwargs,
):
    """Insert a pipeline_steps row directly, bypassing the recorder."""
    with db_session() as s:
        row = PipelineStepRow(
            item_id=item_id,
            run=run,
            seg=seg,
            stage=stage,
            step_key=step_key,
            status=status,
            started_at=datetime.utcnow(),
            **kwargs,
        )
        s.add(row)
        s.flush()
        return row.id


def _record_ok_step(step_key, seg=SEG, inputs=None, outputs=None, item_id=ITEM, run=RUN):
    """Record a finished ok step through the real recorder, return its id."""
    stage = step_key.split("/")[0]
    with steps.step(item_id, run, seg, stage, step_key, inputs or {}) as st:
        if outputs:
            st.set(**outputs)
    rows = steps.list_steps(item_id, run, seg)
    return [r for r in rows if r["step_key"] == step_key and r["status"] == "ok"][-1]["id"]


def _seed_entities(item_id=ITEM, run=RUN, seg=SEG, script="old script"):
    """Seed item -> run -> segment in FK order so tasks can load real objects."""
    now = datetime.utcnow()
    repo.upsert_item(HNItem(id=item_id, type="story", title="A story"))
    repo.save_run(
        ProcessedRun(
            key=f"hnfm:item:{item_id}:run:{run}",
            item_id=item_id,
            run=run,
            created_at=now,
            source_url="http://example.com",
            content_raw="raw content",
            content_clean="clean content",
            summary="a summary",
            short_description="short",
            tags=["tag"],
            emoji=["✨"],
            haiku="haiku",
        )
    )
    repo.save_segment(
        Segment(
            key=f"hnfm:seg:{item_id}:{run}:{seg}",
            item_id=item_id,
            run=run,
            seg=seg,
            created_at=now,
            processed_run_key=f"hnfm:item:{item_id}:run:{run}",
            script=script,
        )
    )


def _only_step():
    rows = steps.list_steps(ITEM, RUN)
    assert len(rows) == 1
    return rows[0]


# ---------------------------------------------------------------------------
# Recorder: step() contextmanager
# ---------------------------------------------------------------------------

class TestStepRecorder:
    def test_happy_path_records_ok_row(self):
        with steps.step(ITEM, RUN, SEG, "audio", "audio/sec_1", {"text": "hello"}) as st:
            st.set(path="/out/sec_1.wav", duration_ms=1200)

        row = _only_step()
        assert row["item_id"] == ITEM
        assert row["run"] == RUN
        assert row["seg"] == SEG
        assert row["stage"] == "audio"
        assert row["step_key"] == "audio/sec_1"
        assert row["status"] == "ok"
        assert row["inputs"] == {"text": "hello"}
        assert row["outputs"] == {"path": "/out/sec_1.wav", "duration_ms": 1200}
        assert isinstance(row["seconds"], float)
        assert row["seconds"] >= 0
        assert row["started_at"] is not None
        assert row["finished_at"] is not None
        assert row["error"] is None

    def test_exception_records_error_and_propagates(self):
        with pytest.raises(ValueError, match="boom"):
            with steps.step(ITEM, RUN, SEG, "images", "images/0/root", {"prompt": "p"}):
                raise ValueError("boom")

        row = _only_step()
        assert row["status"] == "error"
        assert row["error"] == "boom"
        assert isinstance(row["seconds"], float)
        assert row["finished_at"] is not None

    def test_soft_fail_records_error_without_raising(self):
        with steps.step(ITEM, RUN, SEG, "images", "images/1/clip", {}) as st:
            st.set(partial="thing")
            st.soft_fail("ltx clip did not render")
        # No exception escaped; the row is an error with the message.
        row = _only_step()
        assert row["status"] == "error"
        assert row["error"] == "ltx clip did not render"
        assert row["outputs"] == {"partial": "thing"}

    def test_record_llm_attributes_to_current_step(self):
        with steps.step(ITEM, RUN, SEG, "script", "script", {}) as st:
            steps.record_llm(model="qwen-3", tokens_in=100, tokens_out=20)
            steps.record_llm(tokens_in=50, tokens_out=5)
            st.set(script="s")

        row = _only_step()
        assert row["model"] == "qwen-3"
        assert row["tokens_in"] == 150
        assert row["tokens_out"] == 25
        assert row["llm_calls"] == 2

    def test_record_llm_outside_step_is_noop(self):
        with steps.step(ITEM, RUN, SEG, "script", "script", {}) as st:
            st.set(script="s")
        before = _only_step()

        # No step is executing; this must not raise and must not touch rows.
        steps.record_llm(model="stray", tokens_in=999, tokens_out=999)

        after = _only_step()
        assert after["model"] == before["model"] is None
        assert after["tokens_in"] == 0
        assert after["tokens_out"] == 0
        assert after["llm_calls"] == 0

    def test_inputs_and_outputs_are_bounded(self):
        big = "a" * 5000
        with steps.step(
            ITEM, RUN, SEG, "script", "script",
            {"text": big, "nested": {"inner": big}, "small": "ok"},
        ) as st:
            st.set(big_out=big)

        row = _only_step()
        for value in (row["inputs"]["text"], row["inputs"]["nested"]["inner"], row["outputs"]["big_out"]):
            assert "[truncated" in value
            assert "5000 chars total" in value
            assert value.startswith("a" * 100)
            assert len(value) < 4100
        assert row["inputs"]["small"] == "ok"

    def test_latest_wins_supersedes_older_seg_scoped_attempts(self):
        # An older error attempt and an older ok attempt at the same unit
        with pytest.raises(RuntimeError):
            with steps.step(ITEM, RUN, SEG, "audio", "audio/sec_1", {}):
                raise RuntimeError("first try failed")
        with steps.step(ITEM, RUN, SEG, "audio", "audio/sec_1", {}) as st:
            st.set(take=2)
        # A same-key step in another seg must not be touched
        with steps.step(ITEM, RUN, 2, "audio", "audio/sec_1", {}) as st:
            st.set(take=1)
        # The winning attempt
        with steps.step(ITEM, RUN, SEG, "audio", "audio/sec_1", {}) as st:
            st.set(take=3)

        rows = steps.list_steps(ITEM, RUN, SEG)
        assert [r["status"] for r in rows] == ["superseded", "superseded", "ok"]
        assert rows[-1]["outputs"] == {"take": 3}
        other_seg = [r for r in steps.list_steps(ITEM, RUN) if r["seg"] == 2]
        assert [r["status"] for r in other_seg] == ["ok"]

    def test_latest_wins_for_run_scoped_steps(self):
        with steps.step(ITEM, RUN, None, "scrape", "scrape", {}) as st:
            st.set(chars=10)
        # A seg-scoped step with the same key must not be superseded
        with steps.step(ITEM, RUN, SEG, "scrape", "scrape", {}) as st:
            st.set(chars=5)
        with steps.step(ITEM, RUN, None, "scrape", "scrape", {}) as st:
            st.set(chars=20)

        rows = steps.list_steps(ITEM, RUN)
        run_scoped = [r for r in rows if r["seg"] is None]
        assert [r["status"] for r in run_scoped] == ["superseded", "ok"]
        assert run_scoped[-1]["outputs"] == {"chars": 20}
        seg_scoped = [r for r in rows if r["seg"] == SEG]
        assert [r["status"] for r in seg_scoped] == ["ok"]


# ---------------------------------------------------------------------------
# Queries: list_steps scoping and ordering
# ---------------------------------------------------------------------------

class TestListSteps:
    def test_seg_view_includes_run_scoped_rows_and_excludes_other_segs(self):
        id_null = _insert_step(seg=None, step_key="scrape")
        id_seg1_a = _insert_step(seg=1, step_key="script")
        id_seg2 = _insert_step(seg=2, step_key="script")
        id_seg1_b = _insert_step(seg=1, step_key="audio/sec_1")
        _insert_step(item_id=999, seg=1, step_key="script")  # other item

        rows = steps.list_steps(ITEM, RUN, seg=1)
        assert [r["id"] for r in rows] == [id_null, id_seg1_a, id_seg1_b]

        all_rows = steps.list_steps(ITEM, RUN)
        assert [r["id"] for r in all_rows] == [id_null, id_seg1_a, id_seg2, id_seg1_b]

    def test_get_step_and_supersede(self):
        sid = _insert_step(step_key="script")
        assert steps.get_step(sid)["step_key"] == "script"
        assert steps.get_step(10_000_000) is None
        steps.supersede(sid)
        assert steps.get_step(sid)["status"] == "superseded"


# ---------------------------------------------------------------------------
# rerun_supported / staleness
# ---------------------------------------------------------------------------

class TestRerunSupported:
    @pytest.mark.parametrize(
        "key",
        [
            "script",
            "audio/asr",
            "video/assemble",
            "media_plan/plan",
            "audio/sec_0",
            "audio/sec_12",
            "images/0/root",
            "images/7/root",
        ],
    )
    def test_supported(self, key):
        assert steps.rerun_supported(key) is True

    @pytest.mark.parametrize(
        "key",
        [
            "scrape",
            "summary",
            "audio/stitch",
            "images/2/frame_1",
            "media_plan/clip_3",
            "video/frames",
            "",
        ],
    )
    def test_unsupported(self, key):
        assert steps.rerun_supported(key) is False


class TestStaleness:
    def test_stale_patterns_for(self):
        assert steps.stale_patterns_for("script") == [
            "audio/%", "images/%", "media_plan/%", "video/%",
        ]
        assert steps.stale_patterns_for("audio/sec_3") == [
            "audio/stitch", "audio/asr", "video/%",
        ]
        assert steps.stale_patterns_for("images/2/root") == [
            "images/2/frame_%", "media_plan/clip_2", "video/%",
        ]
        assert steps.stale_patterns_for("media_plan/plan") == ["video/%"]
        assert steps.stale_patterns_for("media_plan/clip_5") == ["video/%"]
        assert steps.stale_patterns_for("audio/asr") == ["video/%"]
        assert steps.stale_patterns_for("images/2/frame_1") == ["video/%"]
        assert steps.stale_patterns_for("scrape") == []

    def test_mark_stale_flips_only_matching_ok_rows(self):
        flips_a = _insert_step(step_key="audio/stitch", status="ok")
        _insert_step(step_key="audio/asr", status="error")       # matches, not ok
        flips_b = _insert_step(step_key="video/assemble", status="ok")
        _insert_step(step_key="video/frames", status="superseded")  # matches, not ok
        _insert_step(step_key="images/1/root", status="ok")      # ok, no pattern match
        _insert_step(seg=2, step_key="video/assemble", status="ok")  # other seg

        patterns = steps.stale_patterns_for("audio/sec_3")
        count = steps.mark_stale(ITEM, RUN, SEG, patterns)
        assert count == 2

        stale = steps.list_stale(ITEM, RUN, SEG)
        assert sorted(r["id"] for r in stale) == sorted([flips_a, flips_b])
        assert all(r["status"] == "stale" for r in stale)
        # untouched rows keep their statuses
        by_key = {(r["seg"], r["step_key"]): r["status"] for r in steps.list_steps(ITEM, RUN)}
        assert by_key[(SEG, "audio/asr")] == "error"
        assert by_key[(SEG, "video/frames")] == "superseded"
        assert by_key[(SEG, "images/1/root")] == "ok"
        assert by_key[(2, "video/assemble")] == "ok"

    def test_mark_stale_with_no_patterns_is_noop(self):
        _insert_step(step_key="video/assemble", status="ok")
        assert steps.mark_stale(ITEM, RUN, SEG, []) == 0
        assert steps.list_stale(ITEM, RUN, SEG) == []

    def test_mark_stale_includes_run_scoped_rows_for_seg(self):
        run_scoped = _insert_step(seg=None, step_key="video/assemble", status="ok")
        assert steps.mark_stale(ITEM, RUN, SEG, ["video/%"]) == 1
        assert steps.get_step(run_scoped)["status"] == "stale"


# ---------------------------------------------------------------------------
# rerun_step task routing (mocked rebuild machinery)
# ---------------------------------------------------------------------------

class TestRerunStepRouting:
    def test_images_root_reuses_recorded_prompt(self):
        sid = _record_ok_step(
            "images/2/root",
            inputs={"prompt": "a red fox at dawn", "line_text": "the fox"},
            outputs={"image_path": "/out/2.png"},
        )
        with mock.patch.object(
            tasks, "rebuild_single_image", return_value={"rebuilt": True}
        ) as rebuild:
            result = tasks.rerun_step(sid)

        rebuild.assert_called_once_with(
            ITEM, RUN, SEG, 2, prompt_override="a red fox at dawn", line_override=None
        )
        assert result["status"] == "ok"
        assert result["step_key"] == "images/2/root"

    def test_images_root_regenerate_prompt_passes_none(self):
        sid = _record_ok_step("images/2/root", inputs={"prompt": "a red fox at dawn"})
        with mock.patch.object(
            tasks, "rebuild_single_image", return_value={"rebuilt": True}
        ) as rebuild:
            tasks.rerun_step(sid, {"regenerate_prompt": True})

        rebuild.assert_called_once_with(
            ITEM, RUN, SEG, 2, prompt_override=None, line_override=None
        )

    def test_images_root_explicit_prompt_override_wins(self):
        sid = _record_ok_step("images/2/root", inputs={"prompt": "old prompt"})
        with mock.patch.object(
            tasks, "rebuild_single_image", return_value={"rebuilt": True}
        ) as rebuild:
            tasks.rerun_step(sid, {"prompt": "brand new prompt", "line_text": "new line"})

        rebuild.assert_called_once_with(
            ITEM, RUN, SEG, 2, prompt_override="brand new prompt", line_override="new line"
        )

    def test_audio_section_routes_to_build_segment_audio(self):
        sid = _record_ok_step("audio/sec_2", inputs={"text": "original text"})
        # Downstream ok steps should be marked stale by the rerun
        _record_ok_step("audio/stitch")
        _record_ok_step("audio/asr")
        _record_ok_step("video/assemble")

        with mock.patch.object(
            tasks, "build_segment_audio", return_value={"status": "ok"}
        ) as build:
            result = tasks.rerun_step(sid, {"text": "edited narration"})

        build.assert_called_once_with(
            ITEM, RUN, SEG, mode="one", section=2, text_override="edited narration"
        )
        assert result["status"] == "ok"
        assert result["stale"] == 3
        stale_keys = {r["step_key"] for r in steps.list_stale(ITEM, RUN, SEG)}
        assert stale_keys == {"audio/stitch", "audio/asr", "video/assemble"}

    def test_audio_section_without_override_passes_none_text(self):
        sid = _record_ok_step("audio/sec_5", inputs={"text": "original"})
        with mock.patch.object(
            tasks, "build_segment_audio", return_value={"status": "ok"}
        ) as build:
            tasks.rerun_step(sid)
        build.assert_called_once_with(
            ITEM, RUN, SEG, mode="one", section=5, text_override=None
        )

    def test_script_manual_override_sets_segment_script(self):
        _seed_entities(script="old script")
        sid = _record_ok_step("script", inputs={"summary": "a summary"})

        with mock.patch.object(tasks, "generate_script") as gen:
            result = tasks.rerun_step(sid, {"script": "[S1] manual"})

        gen.assert_not_called()
        assert result["status"] == "ok"
        assert repo.get_segment(ITEM, RUN, SEG).script == "[S1] manual"

        # A fresh script step was recorded and supersedes the original
        script_rows = [
            r for r in steps.list_steps(ITEM, RUN, SEG) if r["step_key"] == "script"
        ]
        assert [r["status"] for r in script_rows] == ["superseded", "ok"]
        assert script_rows[-1]["inputs"]["manual_override"] is True
        assert script_rows[-1]["outputs"]["script"] == "[S1] manual"

    def test_media_plan_routes(self):
        sid = _record_ok_step("media_plan/plan")
        with mock.patch.object(
            tasks, "build_segment_media_plan", return_value={"status": "ok"}
        ) as plan:
            result = tasks.rerun_step(sid)
        plan.assert_called_once_with(ITEM, RUN, SEG)
        assert result["status"] == "ok"

    def test_video_assemble_routes(self):
        sid = _record_ok_step("video/assemble")
        with mock.patch.object(
            tasks, "generate_segment_video", return_value={"status": "ok"}
        ) as vid:
            result = tasks.rerun_step(sid)
        vid.assert_called_once_with(ITEM, RUN, SEG)
        assert result["status"] == "ok"

    def test_unsupported_step_key_raises(self):
        sid = _record_ok_step("audio/stitch")
        with pytest.raises(RuntimeError, match="not supported"):
            tasks.rerun_step(sid)

    def test_missing_step_raises(self):
        with pytest.raises(RuntimeError, match="not found"):
            tasks.rerun_step(10_000_000)


# ---------------------------------------------------------------------------
# API endpoints
# ---------------------------------------------------------------------------

class TestStepsApi:
    def test_get_segment_steps(self):
        from ..web.api import app

        id_scrape = _insert_step(seg=None, stage="scrape", step_key="scrape")
        id_script = _insert_step(seg=SEG, stage="script", step_key="script")
        id_video = _insert_step(
            seg=SEG, stage="video", step_key="video/assemble", status="stale"
        )
        _insert_step(seg=2, step_key="script")  # other seg, excluded

        client = TestClient(app)
        resp = client.get(f"/api/hn/items/{ITEM}/runs/{RUN}/segments/{SEG}/steps")
        assert resp.status_code == 200
        data = resp.json()
        assert data["item_id"] == ITEM
        assert data["run"] == RUN
        assert data["seg"] == SEG
        assert [s["id"] for s in data["steps"]] == [id_scrape, id_script, id_video]
        assert data["stale_count"] == 1
        # JSON object keys are strings
        assert data["rerunnable"] == {
            str(id_scrape): False,
            str(id_script): True,
            str(id_video): True,
        }

    def test_get_run_steps(self):
        from ..web.api import app

        ids = [
            _insert_step(seg=None, step_key="scrape"),
            _insert_step(seg=1, step_key="script"),
            _insert_step(seg=2, step_key="script"),
        ]
        client = TestClient(app)
        resp = client.get(f"/api/hn/items/{ITEM}/runs/{RUN}/steps")
        assert resp.status_code == 200
        assert [s["id"] for s in resp.json()["steps"]] == ids

    def test_post_rerun_queues_task(self):
        from ..web.api import app

        sid = _insert_step(step_key="images/2/root", inputs={"prompt": "p"})
        client = TestClient(app)
        with mock.patch(
            "hnfm.web.tasks.rerun_step.apply_async",
            return_value=mock.Mock(id="task-123"),
        ) as apply_async:
            resp = client.post(f"/api/steps/{sid}/rerun", json={"prompt": "new"})

        assert resp.status_code == 200
        data = resp.json()
        assert data == {
            "status": "queued",
            "step_id": sid,
            "step_key": "images/2/root",
            "task_id": "task-123",
        }
        apply_async.assert_called_once_with(
            args=[sid], kwargs={"overrides": {"prompt": "new"}}
        )

    def test_post_rerun_unsupported_step_returns_400(self):
        from ..web.api import app

        sid = _insert_step(step_key="audio/stitch")
        client = TestClient(app)
        with mock.patch("hnfm.web.tasks.rerun_step.apply_async") as apply_async:
            resp = client.post(f"/api/steps/{sid}/rerun", json={})
        assert resp.status_code == 400
        assert "not supported" in resp.json()["detail"]
        apply_async.assert_not_called()

    def test_post_rerun_missing_step_returns_404(self):
        from ..web.api import app

        client = TestClient(app)
        resp = client.post("/api/steps/10000000/rerun", json={})
        assert resp.status_code == 404

    def test_rebuild_stale_queues_video_and_reports_skipped(self):
        from ..web.api import app

        _insert_step(step_key="video/assemble", status="stale")
        _insert_step(step_key="images/2/frame_1", status="stale")
        _insert_step(step_key="audio/stitch", status="ok")  # not stale, ignored

        client = TestClient(app)
        with mock.patch(
            "hnfm.web.tasks.generate_segment_video.apply_async",
            return_value=mock.Mock(id="vid-task-1"),
        ) as apply_async:
            resp = client.post(
                f"/api/hn/items/{ITEM}/runs/{RUN}/segments/{SEG}/rebuild-stale"
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["queued"] == [
            {"step_key": "video/assemble", "task_id": "vid-task-1"}
        ]
        assert data["skipped"] == ["images/2/frame_1"]
        assert data["stale_keys"] == ["images/2/frame_1", "video/assemble"]
        apply_async.assert_called_once_with(args=[ITEM, RUN, SEG])

    def test_rebuild_stale_with_no_video_stale_queues_nothing(self):
        from ..web.api import app

        _insert_step(step_key="images/2/frame_1", status="stale")
        client = TestClient(app)
        with mock.patch(
            "hnfm.web.tasks.generate_segment_video.apply_async"
        ) as apply_async:
            resp = client.post(
                f"/api/hn/items/{ITEM}/runs/{RUN}/segments/{SEG}/rebuild-stale"
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["queued"] == []
        assert data["skipped"] == ["images/2/frame_1"]
        apply_async.assert_not_called()


class TestReapAbandoned:
    """A worker killed mid-step leaves its row `running` forever (issue #9)."""

    def _running_row(self, started_at, step_key="brief/build"):
        with db_session() as s:
            row = PipelineStepRow(
                item_id=ITEM,
                run=RUN,
                seg=None,
                stage="brief",
                step_key=step_key,
                status="running",
                started_at=started_at,
            )
            s.add(row)
            s.flush()
            return row.id

    def test_reaps_a_step_older_than_the_longest_task_limit(self):
        from datetime import timedelta

        stale_id = self._running_row(
            datetime.utcnow() - timedelta(seconds=steps.MAX_STEP_SECONDS + 60)
        )

        assert steps.reap_abandoned() == 1

        row = steps.get_step(stale_id)
        assert row["status"] == "abandoned"
        assert row["finished_at"] is not None
        assert "worker died" in row["error"]

    def test_leaves_a_genuinely_running_step_alone(self):
        fresh_id = self._running_row(datetime.utcnow())

        assert steps.reap_abandoned() == 0
        assert steps.get_step(fresh_id)["status"] == "running"

    def test_reaped_step_leaves_the_running_feed(self):
        from datetime import timedelta

        self._running_row(
            datetime.utcnow() - timedelta(seconds=steps.MAX_STEP_SECONDS + 60)
        )
        assert len(steps.activity()["running"]) == 1

        steps.reap_abandoned()

        after = steps.activity()
        assert after["running"] == []
        # Visible as a terminal outcome, not silently vanished.
        assert [r["status"] for r in after["recent"]] == ["abandoned"]

    def test_abandoned_is_not_counted_as_a_failure(self):
        """`abandoned` is infrastructure, not a step that failed."""
        from datetime import timedelta

        self._running_row(
            datetime.utcnow() - timedelta(seconds=steps.MAX_STEP_SECONDS + 60)
        )
        steps.reap_abandoned()

        with db_session() as s:
            errors = (
                s.query(PipelineStepRow)
                .filter(PipelineStepRow.status == "error")
                .count()
            )
        assert errors == 0


class TestRecordTaskFailure:
    """A task dying outside a step() block left no trace at all (issue #8)."""

    def test_records_a_crash_with_no_step_block(self):
        step_id = steps.record_task_failure(
            "hnfm.web.tasks.process_hn_item_run",
            (49551096, 2),
            {},
            "Item 49551096 has no URL",
            traceback="Traceback (most recent call last): ...",
        )
        assert step_id is not None

        row = steps.get_step(step_id)
        assert row["item_id"] == 49551096
        assert row["run"] == 2
        assert row["stage"] == "task"
        assert row["step_key"] == "task/process_hn_item_run"
        assert row["status"] == "error"
        assert "has no URL" in row["error"]

    def test_the_crash_reaches_the_activity_feed(self):
        steps.record_task_failure(
            "hnfm.web.tasks.process_hn_item_run", (ITEM, RUN), {}, "boom"
        )
        recent = steps.activity()["recent"]
        assert [r["step_key"] for r in recent] == ["task/process_hn_item_run"]

    def test_item_agnostic_task_still_records(self):
        """build_digest takes no item_id; it must not be lost for want of one."""
        step_id = steps.record_task_failure(
            "hnfm.web.tasks.build_digest", (), {"limit": 6, "shape": "daily"}, "boom"
        )
        row = steps.get_step(step_id)
        assert row["item_id"] == 0
        assert row["run"] == 0
        assert row["step_key"] == "task/build_digest"

    def test_kwargs_are_read_when_args_are_positional_empty(self):
        step_id = steps.record_task_failure(
            "hnfm.web.tasks.generate_segment", (), {"item_id": 7, "run": 3, "seg": 2},
            "boom",
        )
        row = steps.get_step(step_id)
        assert (row["item_id"], row["run"], row["seg"]) == (7, 3, 2)
