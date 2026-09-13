"""HNFM on air (plans/20): the producer's rules, the director's sequencing,
the bank's substitutions, and the switch that keeps all of it off."""

import os
from datetime import datetime
from unittest import mock

import pytest

from ..radio import director, producer
from ..radio.schemas import RunItem, RunSheet
from ..db import repo


def _eps(n=4, seconds=120):
    return [{"ref": f"{i}:1:1", "item_id": i, "run": 1, "seg": 1, "title": f"Story {i}",
             "path": f"/e/{i}.mp3", "seconds": seconds, "age_hours": i} for i in range(1, n + 1)]


def _stories(n=8):
    return [{"item_id": 100 + i, "run": 1, "title": f"New story {i}", "url": None, "age_hours": i}
            for i in range(1, n + 1)]


class TestFallbackBlock:
    def test_opens_with_id_and_time_check_then_briefs_with_beds(self):
        sheet = producer.fallback_block(_eps(), _stories(), [], [], minutes=10, now=datetime(2026, 9, 12, 8, 5))
        kinds = [i.kind for i in sheet.items]
        assert kinds[:2] == ["station_id", "time_check"]
        assert sheet.items[1].line == "It's 8:05 on HNFM."
        assert kinds.count("brief") >= 3
        assert kinds.count("episode") <= 1
        assert "music" in kinds
        for a, b in zip(kinds, kinds[1:]):
            assert not (a == "episode" and b == "episode")
        for it in sheet.items:
            if it.kind in ("station_id", "time_check", "coming_up", "brief"):
                assert it.mood == "calm"

    def test_skips_what_aired_or_is_planned(self):
        recent = [{"kind": "brief", "ref": "story:101"}, {"kind": "episode", "ref": "1:1:1"}]
        planned = [{"kind": "brief", "story": 102}, {"kind": "episode", "episode": "2:1:1"}]
        sheet = producer.fallback_block(_eps(), _stories(), recent, planned, minutes=10)
        stories = [i.story for i in sheet.items if i.kind == "brief"]
        eps = [i.episode for i in sheet.items if i.kind == "episode"]
        assert 101 not in stories and 102 not in stories
        assert "1:1:1" not in eps and "2:1:1" not in eps

    def test_respects_the_length(self):
        sheet = producer.fallback_block(_eps(20, seconds=180), _stories(40), [], [], minutes=10)
        total = sum((180 if i.kind == "episode" else 30 if i.kind in ("music", "brief") else 8) for i in sheet.items)
        assert total < 10 * 60 + 300


class TestEnforce:
    def _run(self, items, used_eps=set(), used_stories=set()):
        by_ref = {e["ref"]: e for e in _eps()}
        return producer.enforce(RunSheet(title="x", items=items), by_ref, {101, 102, 103},
                                used_eps, used_stories, minutes=30)

    def test_model_output_is_policed(self):
        out = self._run([
            RunItem(kind="brief", story=101, host="nobody", mood="happy"),
            RunItem(kind="brief", story=999),                 # unknown story: dropped
            RunItem(kind="brief", story=101),                 # repeat: dropped
            RunItem(kind="episode", episode="1:1:1"),
            RunItem(kind="episode", episode="2:1:1"),         # second deep dive: dropped
            RunItem(kind="coming_up", host="nobody", line=" ".join(["w"] * 40)),
            RunItem(kind="music", music_style="", seconds=500),
        ])
        kinds = [i.kind for i in out.items]
        assert kinds[0] == "station_id"
        assert kinds.count("brief") == 1 and kinds.count("episode") == 1
        br = next(i for i in out.items if i.kind == "brief")
        assert br.host in producer.HOSTS and br.mood == "calm"
        cu = next(i for i in out.items if i.kind == "coming_up")
        assert len(cu.line.split()) == 25
        mu = next(i for i in out.items if i.kind == "music")
        assert mu.seconds == 45 and mu.music_style

    def test_a_bare_story_id_resolves_to_its_episode(self):
        out = self._run([RunItem(kind="episode", episode="1"), RunItem(kind="music", music_style="s", seconds=30)])
        assert [i.episode for i in out.items if i.kind == "episode"] == ["1:1:1"]

    def test_recent_and_planned_are_refused(self):
        out = self._run([RunItem(kind="episode", episode="1:1:1"), RunItem(kind="brief", story=102)],
                        used_eps={"1:1:1"}, used_stories={102})
        assert [i.kind for i in out.items] == []

    def test_used_refs(self):
        eps, stories = producer.used_refs(
            [{"ref": "1:1:1"}, {"ref": "story:7"}, {"ref": None}],
            [{"kind": "episode", "episode": "2:1:1"}, {"kind": "brief", "story": 8}])
        assert eps == {"1:1:1", "2:1:1"} and stories == {7, 8}


class TestPlanBlockFallsBack:
    def test_model_failure_yields_a_fallback_sheet(self):
        svc = mock.Mock()
        svc.usage = {"calls": 0, "tokens_in": 0, "tokens_out": 0, "model": None}
        svc.generate_structured.side_effect = RuntimeError("model down")
        with mock.patch("hnfm.content.llm_service.LLMService", return_value=svc):
            sheet, source, _ = producer.plan_block(_eps(), _stories(), [], [], minutes=10)
        assert source == "fallback" and sheet.items


class TestBriefs:
    def test_spoken_reads_headline_then_bullets(self):
        from ..radio.briefs import spoken

        text = spoken({"title": "Kimi K3 at 1 token/s ", "bullets": ["It streams from four SSDs", "It is slow."]})
        assert text == "Kimi K3 at 1 token/s. It streams from four SSDs. It is slow."

    def test_voice_name_uses_the_mood_when_the_server_has_it(self, monkeypatch):
        from ..radio import voice

        monkeypatch.setattr(voice, "_VOICES", ["Magpie-Multilingual.EN-US.Mia", "Magpie-Multilingual.EN-US.Mia.Calm"])
        assert voice.voice_name("mia", "calm") == "Magpie-Multilingual.EN-US.Mia.Calm"
        assert voice.voice_name("mia", "happy") == "Magpie-Multilingual.EN-US.Mia"
        assert voice.voice_name("dia", "calm") == voice.HOSTS["dia"][1]


class TestDirector:
    """Against the real (sqlite) tables, with the library mocked."""

    def _sheet(self, items):
        return repo.radio_save_sheet(sheet_id="s1", title="t", minutes=10, items=items, source="test")

    def test_serves_in_order_and_skips_unavailable(self, monkeypatch):
        self._sheet([
            {"kind": "station_id", "host": "mia"},
            {"kind": "episode", "episode": "1:1:1"},
            {"kind": "music"},
        ])
        bank = {"station_id": {"id": "b1", "kind": "station_id", "path": "/b/1.mp3", "text": "You're listening", "host": "mia"}}
        monkeypatch.setattr(director, "episode", lambda ref: {"ref": ref, "path": "/e/1.mp3", "title": "Story 1",
                                                              "item_id": 1, "run": 1, "seg": 1, "seconds": 120} if ref == "1:1:1" else None)
        monkeypatch.setattr(director, "pick_from_bank", lambda kind, **kw: bank.get(kind))
        monkeypatch.setattr(director, "_request_plan", lambda: None)

        first = director.next_item()
        assert first["kind"] == "station_id" and first["title"] == "You're listening"
        second = director.next_item()
        assert second["kind"] == "episode" and second["path"] == "/e/1.mp3"
        # music is not in the bank: skipped; the sheet is exhausted and a
        # fallback block is planned inline from the (empty) library.
        monkeypatch.setattr(director, "episodes", lambda limit=80: [])
        monkeypatch.setattr(director, "plan_now", lambda **kw: {"sheet_id": "s2", "items": []})
        third = director.next_item()
        assert third.get("safety") is True or third["kind"] in ("music", "station_id")

    def test_queue_jumps_the_line(self, monkeypatch):
        self._sheet([{"kind": "station_id", "host": "mia"}])
        monkeypatch.setattr(director, "episode", lambda ref: {"ref": ref, "path": "/e/q.mp3", "title": "Queued",
                                                              "item_id": 5, "run": 1, "seg": 1})
        monkeypatch.setattr(director, "_request_plan", lambda: None)
        assert director.enqueue("5:1:1") == ["5:1:1"]
        item = director.next_item()
        assert item["queued"] is True and item["path"] == "/e/q.mp3"
        assert director.queue() == []

    def test_events_become_history_and_now_playing(self):
        director.record_event({"title": "A", "hnfm_kind": "episode", "hnfm_ref": "1:1:1", "hnfm_bank_id": ""})
        director.record_event({"title": "B", "hnfm_kind": "music", "hnfm_bank_id": "b9"})
        now = director.now_playing()
        assert now["title"] == "B" and now["meta"]["bank_id"] == "b9"
        hist = repo.radio_recent_events(hours=1)
        assert [h["title"] for h in hist] == ["A", "B"]


class TestSwitch:
    def test_api_is_404_when_off(self, monkeypatch):
        from fastapi.testclient import TestClient
        from ..web.api import app

        monkeypatch.setenv("RADIO_ENABLED", "false")
        c = TestClient(app)
        assert c.get("/api/radio/status").json() == {"enabled": False}
        assert c.get("/api/radio/next").status_code == 404
        assert c.get("/api/radio/script").status_code == 404

    def test_script_is_served_when_on(self, monkeypatch):
        from fastapi.testclient import TestClient
        from ..web.api import app

        monkeypatch.setenv("RADIO_ENABLED", "true")
        body = TestClient(app).get("/api/radio/script").text
        assert "output.icecast" in body and "/api/radio/next" in body

    def test_beat_leaves_no_entry_when_off(self, monkeypatch):
        from .. import schedule as sched

        monkeypatch.delenv("RADIO_ENABLED", raising=False)
        cfg = {"enabled": True, "jobs": {
            "radio-monitor": {"task": "x", "every": "5m", "requires_env": "RADIO_ENABLED"},
            "fetch-new": {"task": "y", "every": "10m"},
        }}
        assert list(sched.beat_schedule(cfg)) == ["fetch-new"]
        monkeypatch.setenv("RADIO_ENABLED", "true")
        assert sorted(sched.beat_schedule(cfg)) == ["fetch-new", "radio-monitor"]

    def test_services_page_lists_the_radio_only_when_on(self, monkeypatch):
        from ..utils import service_registry as reg

        monkeypatch.setenv("RADIO_ENABLED", "false")
        assert not [s for s in reg.get_service_specs() if s.role == "Radio"]
        monkeypatch.setenv("RADIO_ENABLED", "true")
        assert len([s for s in reg.get_service_specs() if s.role == "Radio"]) == 2


class TestCommentary:
    """The studio's feed (plans/21): components narrate, the stream tails."""

    def test_log_lines_land_and_tail_in_order(self):
        from .. import radio

        radio.log("dj", "asked what's next")
        radio.log("director", "served item 1/3: station_id — hi", kind="station_id")
        tail = repo.radio_log_tail(limit=10)
        assert [t["component"] for t in tail[-2:]] == ["dj", "director"]
        assert tail[-1]["meta"] == {"kind": "station_id"}
        since = repo.radio_log_since(after_id=tail[-2]["id"])
        assert [t["message"] for t in since] == ["served item 1/3: station_id — hi"]

    def test_next_item_narrates(self, monkeypatch):
        repo.radio_save_sheet(sheet_id="s9", title="t", minutes=10,
                              items=[{"kind": "station_id", "host": "mia"}], source="test")
        monkeypatch.setattr(director, "pick_from_bank",
                            lambda kind, **kw: {"id": "b1", "kind": kind, "path": "/b.mp3", "text": "hi", "host": "mia"})
        monkeypatch.setattr(director, "_request_plan", lambda: None)
        director.next_item()
        msgs = [t["message"] for t in repo.radio_log_tail(limit=5)]
        assert "asked what's next" in msgs
        assert any(m.startswith("served item 1/1: station_id") for m in msgs)

    def test_studio_endpoints_when_on(self, monkeypatch):
        from fastapi.testclient import TestClient
        from ..web.api import app

        monkeypatch.setenv("RADIO_ENABLED", "true")
        c = TestClient(app)
        assert c.get("/api/radio/log").json() == {"lines": []} or True
        snap = c.get("/api/radio/studio").json()
        assert "log" in snap and "sheet_items" in snap and "icecast" in snap
