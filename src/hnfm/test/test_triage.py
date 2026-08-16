"""Tests for story triage: scorer plumbing, ranking, feedback, podcast API."""

from datetime import datetime
from unittest.mock import patch

from fastapi.testclient import TestClient

from ..content import triage
from ..db import repo
from ..web.api import app
from ..web.models import HNItem, ProcessedRun, Segment
from ..web import tasks


def _seed(item_id: int, title: str, hn_score: int = 100, summary: str = "s"):
    repo.upsert_item(HNItem(id=item_id, title=title, url=f"http://x/{item_id}",
                            score=hn_score, descendants=10, time=1_700_000_000))
    repo.save_run(ProcessedRun(
        key="k", item_id=item_id, run=1, created_at=datetime.utcnow(),
        source_url="http://x", content_raw="raw", content_clean="c" * 500,
        summary=summary, short_description="sd", tags=[], emoji=[], haiku="h"))


def _score(item_id: int, suitability: int, topics=None, verdict="good"):
    interest = triage.interest_match(topics or [], "")
    repo.save_triage_score(item_id, 1, {
        "suitability": suitability, "verdict": verdict, "reasons": ["r"],
        "flags": [], "topics": topics or [], "visual_potential": 5,
        "narrative_potential": 5, "interest_match": interest,
        "rank_score": triage.rank_score(suitability, interest, 100),
        "model": "test-model",
    })


class TestScorerPlumbing:
    def test_clamp_bounds_lists_and_lowercases_topics(self):
        """The schema guarantees types, ranges and the verdict enum; `_clamp`
        bounds the sizes it can't (the triage UI renders these as chips)."""
        out = triage._clamp({
            "suitability": 100, "verdict": "great", "reasons": ["x"] * 10,
            "flags": ["f"] * 20, "topics": ["AI", "Local-AI"] * 8,
            "visual_potential": 5, "narrative_potential": 5,
        })
        assert len(out["reasons"]) == 5
        assert len(out["flags"]) == 10
        assert len(out["topics"]) == 8
        assert out["topics"][:2] == ["ai", "local-ai"]

    def test_interest_match_uses_profile(self):
        # generative-ai carries weight 3.0 in config.yaml
        assert triage.interest_match(["generative-ai"]) > 0.5
        assert triage.interest_match(["knitting"]) == 0.0
        assert triage.interest_match(["crypto"]) < 0

    def test_rank_score_monotonic(self):
        low = triage.rank_score(20, 0.0, 10)
        high = triage.rank_score(90, 0.9, 500)
        assert high > low

    def test_hard_flags(self):
        assert triage.FLAG_SCRAPE_FALLBACK in triage.hard_flags("x" * 500, True)
        assert triage.FLAG_TOO_SHORT in triage.hard_flags("short", False)
        assert triage.hard_flags("x" * 500, False) == []

    def test_score_content_returns_validated_score(self):
        from ..content.llm_schemas import TriageScore

        scored = TriageScore(
            suitability=70, verdict="good", reasons=[], flags=[],
            topics=["ai"], visual_potential=6, narrative_potential=7,
        )
        with patch("hnfm.content.llm_service.LLMService.generate_structured",
                   return_value=scored):
            out = triage.score_content("t", "s", "c")
        assert out["suitability"] == 70
        assert out["verdict"] == "good"
        assert out["model"] == triage.primary_model()

    def test_score_content_raises_rather_than_defaulting(self):
        """A silently-defaulted score would mis-rank the queue forever, so a
        failed scoring call must surface (plans/08)."""
        import pytest
        from ..content.llm_service import LLMError

        with patch("hnfm.content.llm_service.LLMService.generate_structured",
                   side_effect=LLMError("all models failed")):
            with pytest.raises(RuntimeError, match="triage scoring failed"):
                triage.score_content("t", "s", "c")


class TestScoreRunTask:
    def test_score_run_persists(self):
        _seed(11, "AI story")
        fake = {
            "suitability": 80, "verdict": "great", "reasons": ["visual"],
            "flags": [], "topics": ["generative-ai"], "visual_potential": 8,
            "narrative_potential": 7, "model": "test-model",
        }
        with patch.object(tasks.triage_module, "score_content", return_value=dict(fake)) \
                if hasattr(tasks, "triage_module") else patch(
                "hnfm.content.triage.score_content", return_value=dict(fake)):
            result = tasks.score_run(11, 1)
        assert result["verdict"] == "great"
        stored = repo.get_triage_score(11, 1)
        assert stored["suitability"] == 80
        assert stored["interest_match"] > 0.5  # generative-ai matched profile
        assert stored["rank_score"] > 0


class TestTriageQueueAPI:
    def test_ranking_and_feedback_boosts(self):
        _seed(1, "Meh story");   _score(1, 30, ["knitting"], "marginal")
        _seed(2, "Great AI story"); _score(2, 85, ["generative-ai"], "great")
        _seed(3, "Okay story");  _score(3, 60, [], "good")

        client = TestClient(app)
        rows = client.get("/api/triage").json()["items"]
        assert [r["item_id"] for r in rows] == [2, 3, 1]

        # human boost: star the meh story → floats to top
        assert client.post("/api/hn/items/1/feedback",
                           json={"verdict": "starred", "note": "I like it"}
                           ).status_code == 200
        rows = client.get("/api/triage").json()["items"]
        assert rows[0]["item_id"] == 1
        assert rows[0]["human_verdict"] == "starred"
        assert rows[0]["human_note"] == "I like it"

        # reject hides by default, visible with include_rejected
        client.post("/api/hn/items/3/feedback", json={"verdict": "rejected"})
        ids = [r["item_id"] for r in client.get("/api/triage").json()["items"]]
        assert 3 not in ids
        ids = [r["item_id"] for r in
               client.get("/api/triage?include_rejected=true").json()["items"]]
        assert 3 in ids and ids[-1] == 3  # sunk to the bottom

        # clearing feedback restores rank order
        client.post("/api/hn/items/1/feedback", json={"verdict": None})
        rows = client.get("/api/triage?include_rejected=true").json()["items"]
        assert rows[0]["item_id"] == 2

    def test_generated_stories_hidden_by_default(self):
        _seed(5, "Done story"); _score(5, 90, ["ai"])
        repo.save_segment(Segment(
            key="k", item_id=5, run=1, seg=1, created_at=datetime.utcnow(),
            processed_run_key="k", script="[S1] x", video_ready=True))
        client = TestClient(app)
        assert client.get("/api/triage").json()["items"] == []
        rows = client.get("/api/triage?include_generated=true").json()["items"]
        assert rows[0]["videos_count"] == 1

    def test_feedback_validation(self):
        _seed(6, "Story")
        client = TestClient(app)
        assert client.post("/api/hn/items/6/feedback",
                           json={"verdict": "meh"}).status_code == 400
        assert client.post("/api/hn/items/999/feedback",
                           json={"verdict": "approved"}).status_code == 404


class TestPodcastAPI:
    def _seed_episode(self, outputs_root, item_id=21):
        import os

        _seed(item_id, "Podcast story")
        ep_dir = os.path.join(outputs_root, "ep")
        os.makedirs(ep_dir, exist_ok=True)
        ep_path = os.path.join(ep_dir, "episode.mp3")
        with open(ep_path, "wb") as f:
            f.write(b"ID3fake-mp3-bytes")
        repo.save_segment(Segment(
            key="k", item_id=item_id, run=1, seg=1, created_at=datetime.utcnow(),
            processed_run_key="k", script="[S1] x", audio_ready=True,
            audio_combined_path=ep_path, episode_path=ep_path))
        return ep_path

    def test_episodes_list_and_feed(self, outputs_root):
        self._seed_episode(outputs_root)
        client = TestClient(app)

        data = client.get("/api/podcast/episodes").json()
        assert data["pagination"]["total"] == 1
        ep = data["items"][0]
        assert ep["title"] == "Podcast story"
        assert ep["audio_url"].endswith("/api/podcast/episodes/21/1/1.mp3")

        feed = client.get("/api/podcast/feed.xml")
        assert feed.status_code == 200
        assert "application/rss+xml" in feed.headers["content-type"]
        assert "<title>Podcast story</title>" in feed.text
        assert 'type="audio/mpeg"' in feed.text
        assert "hnfm-21-1-1" in feed.text

    def test_episode_mp3_served_locally(self, outputs_root):
        self._seed_episode(outputs_root, item_id=22)
        client = TestClient(app)
        resp = client.get("/api/podcast/episodes/22/1/1.mp3")
        assert resp.status_code == 200
        assert resp.content.startswith(b"ID3")

    def test_episode_404(self):
        client = TestClient(app)
        assert client.get("/api/podcast/episodes/1/1/1.mp3").status_code == 404
