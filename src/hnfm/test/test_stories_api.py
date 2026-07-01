"""Tests for the mission-control endpoints: /api/stories, generations, activity."""

from datetime import datetime, timedelta

from fastapi.testclient import TestClient

from ..db import repo, steps
from ..web.api import app
from ..web.models import HNItem, ProcessedRun, Segment


def _seed_story(item_id: int, title: str, score: int = 10, n_runs: int = 0,
                video_ready_segs: int = 0, time: int = 1_700_000_000):
    repo.upsert_item(HNItem(id=item_id, title=title, url=f"http://ex.com/{item_id}",
                            score=score, descendants=score * 2, time=time))
    for run in range(1, n_runs + 1):
        repo.save_run(ProcessedRun(
            key=f"k", item_id=item_id, run=run, created_at=datetime.utcnow(),
            source_url="http://ex.com", content_raw="r", content_clean="c",
            summary=f"summary {run}", short_description="sd", tags=["t"],
            emoji=["x"], haiku="h"))
        seg = Segment(
            key="k", item_id=item_id, run=run, seg=1,
            created_at=datetime.utcnow() + timedelta(minutes=run),
            processed_run_key="k", script="[S1] hi",
            video_ready=(run <= video_ready_segs))
        repo.save_segment(seg)


class TestStoriesEndpoint:
    def test_aggregates_and_pagination_shape(self):
        _seed_story(1, "Alpha story", score=5, n_runs=2, video_ready_segs=1)
        _seed_story(2, "Beta story", score=50)

        client = TestClient(app)
        data = client.get("/api/stories").json()
        assert data["pagination"]["total"] == 2
        by_id = {r["id"]: r for r in data["items"]}
        assert by_id[1]["runs_count"] == 2
        assert by_id[1]["segments_count"] == 2
        assert by_id[1]["videos_count"] == 1
        assert by_id[1]["latest_activity"] is not None
        assert by_id[2]["runs_count"] == 0
        assert by_id[2]["videos_count"] == 0

    def test_sort_and_filters_and_search(self):
        _seed_story(1, "Alpha story", score=5, n_runs=1, video_ready_segs=1)
        _seed_story(2, "Beta story", score=50)
        _seed_story(3, "Gamma alpha thing", score=25, n_runs=1)

        client = TestClient(app)
        # sort by score ascending
        rows = client.get("/api/stories?sort=score&dir=asc").json()["items"]
        assert [r["id"] for r in rows] == [1, 3, 2]
        # sort by videos desc puts the story with a video first
        rows = client.get("/api/stories?sort=videos&dir=desc").json()["items"]
        assert rows[0]["id"] == 1
        # has_video filter
        rows = client.get("/api/stories?has_video=true").json()["items"]
        assert [r["id"] for r in rows] == [1]
        # un-generated filter
        rows = client.get("/api/stories?has_runs=false").json()["items"]
        assert [r["id"] for r in rows] == [2]
        # title search (case-insensitive)
        data = client.get("/api/stories?q=alpha").json()
        assert data["pagination"]["total"] == 2
        # pagination slice
        data = client.get("/api/stories?limit=1&offset=1&sort=id&dir=asc").json()
        assert [r["id"] for r in data["items"]] == [2]
        assert data["pagination"]["total"] == 3


class TestGenerationsEndpoint:
    def test_generations_flattened_across_runs(self):
        _seed_story(7, "Story", n_runs=3, video_ready_segs=2)
        client = TestClient(app)
        data = client.get("/api/hn/items/7/generations").json()
        gens = data["generations"]
        assert len(gens) == 3
        # newest first
        assert [g["run"] for g in gens] == [3, 2, 1]
        assert gens[0]["run_summary"] == "summary 3"
        assert gens[-1]["video_ready"] is True

    def test_generations_empty(self):
        _seed_story(8, "No gens")
        client = TestClient(app)
        assert client.get("/api/hn/items/8/generations").json()["generations"] == []


class TestActivityEndpoint:
    def test_running_and_recent(self):
        # a finished step (recent) and a hanging one (running)
        with steps.step(1, 1, None, "scrape", "scrape", {}):
            pass
        try:
            with steps.step(1, 1, 1, "script", "script", {}):
                raise RuntimeError("boom")  # finishes as status=error → recent
        except RuntimeError:
            pass

        # simulate a genuinely running step by inserting directly
        from ..db.engine import db_session
        from ..db.orm import PipelineStepRow

        with db_session() as s:
            s.add(PipelineStepRow(
                item_id=2, run=1, seg=1, stage="audio", step_key="audio/sec_1",
                status="running", started_at=datetime.utcnow(),
                tokens_in=0, tokens_out=0, llm_calls=0))

        client = TestClient(app)
        data = client.get("/api/activity").json()
        assert [r["step_key"] for r in data["running"]] == ["audio/sec_1"]
        keys = {r["step_key"] for r in data["recent"]}
        assert "scrape" in keys
