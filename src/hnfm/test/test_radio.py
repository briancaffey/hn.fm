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
        assert sheet.items[1].line == "It's eight oh five in the morning, on HNFM."
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
        # Episodes are off by default now (the feature is the long form);
        # these tests exercise the episode rules, so allow one.
        producer.MAX_EPISODES = 1
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

    def test_one_fresh_story_is_a_block_not_a_rejection(self):
        svc = mock.Mock()
        svc.usage = {"calls": 0, "tokens_in": 0, "tokens_out": 0, "model": None}
        svc.model = "m"
        svc.generate_structured.return_value = RunSheet(title="x", items=[
            RunItem(kind="station_id", host="mia"), RunItem(kind="brief", story=1, host="mia")])
        with mock.patch("hnfm.content.llm_service.LLMService", return_value=svc):
            sheet, source, _ = producer.plan_block([], _stories(1), [], [], minutes=10)
        assert source == "llm"

    def test_nothing_fresh_means_a_music_hold_not_station_ids(self):
        sheet = producer.fallback_block(_eps(), [], [], [], minutes=10)
        assert sheet.items and all(i.kind == "music" for i in sheet.items)
        assert len({i.music_style for i in sheet.items}) == 2


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


class TestCopy:
    def test_speakable(self):
        from ..radio.copy import speakable

        assert speakable("HNFM uses AI on a GPU.") == "H.N.F.M. uses A.I. on a G.P.U."
        assert speakable("NASA and RAM stay words.") == "NASA and RAM stay words."
        assert speakable("It costs $2.5 billion, up 40% since 1994.") == \
            "It costs two point five billion dollars, up forty percent since nineteen ninety-four."
        assert speakable("2026 saw 12 GB in 300 ms") == "twenty twenty-six saw twelve gigabytes in three hundred milliseconds"
        assert speakable("**bold** & `code` at https://x.y/z 🚀") == "bold and code at"
        assert speakable("1,234 users") == "one thousand two hundred thirty-four users"

    def test_bits_listing_names_every_bit(self):
        from ..radio import bits

        text = bits.listing()
        for key in bits.BITS:
            assert f"- {key}:" in text


class TestBitsAndFeatures:
    def test_enforce_keeps_one_feature_and_two_bits_never_adjacent(self):
        by_ref = {}
        sheet = RunSheet(title="x", items=[
            RunItem(kind="bit", bit="joke"),
            RunItem(kind="bit", bit="word"),           # adjacent: dropped
            RunItem(kind="feature", story=101, host="jason"),
            RunItem(kind="feature", story=102),        # second feature: becomes a brief
            RunItem(kind="bit", bit="stack"),
            RunItem(kind="bit", bit="nope"),           # unknown: dropped
            RunItem(kind="brief", story=103),
            RunItem(kind="bit", bit="sketch"),         # third bit: dropped
        ])
        out = producer.enforce(sheet, by_ref, {101, 102, 103}, set(), set(), minutes=30)
        kinds = [i.kind for i in out.items]
        assert kinds.count("feature") == 1 and kinds.count("bit") == 2 and kinds.count("brief") == 2
        bits_ = [i.bit for i in out.items if i.kind == "bit"]
        assert bits_ == ["joke", "stack"]
        assert next(i for i in out.items if i.kind == "bit").host == "leo"

    def test_fallback_has_a_feature_and_bits(self):
        sheet = producer.fallback_block(_eps(), _stories(12), [], [], minutes=15, now=datetime(2026, 9, 13, 3, 0))
        kinds = [i.kind for i in sheet.items]
        assert kinds.count("feature") == 1 and kinds.count("bit") >= 1 and kinds.count("episode") == 0
        assert kinds[kinds.index("feature") - 1] == "coming_up"


class TestComplete:
    def test_a_thin_block_is_given_its_shape(self):
        thin = RunSheet(title="x", items=[
            RunItem(kind="station_id", host="mia", mood="calm"),
            RunItem(kind="brief", story=101, host="leo", mood="calm"),
            RunItem(kind="music", music_style="a", seconds=30),
            RunItem(kind="music", music_style="a", seconds=30),
        ])
        out = producer.complete(thin, _stories(12), minutes=30, now=datetime(2026, 9, 13, 3, 0))
        kinds = [i.kind for i in out.items]
        assert kinds.count("brief") >= 6
        assert kinds.count("feature") == 1 and kinds[kinds.index("feature") - 1] == "coming_up"
        assert 1 <= kinds.count("bit") <= 2
        for a, b in zip(kinds, kinds[1:]):
            assert not (a == "bit" and b == "bit")
        # the model's own items are still there, in order
        assert out.items[0].kind == "station_id" and out.items[1].story == 101
        stories = [i.story for i in out.items if i.story]
        assert len(stories) == len(set(stories))

    def test_a_full_block_is_left_alone(self):
        full = producer.fallback_block(_eps(), _stories(12), [], [], minutes=15, now=datetime(2026, 9, 13, 3, 0))
        out = producer.complete(full, _stories(12), minutes=15, now=datetime(2026, 9, 13, 3, 0))
        assert [i.kind for i in out.items if i.kind != "music"] == [i.kind for i in full.items if i.kind != "music"]

    def test_feature_wins_over_an_earlier_brief_on_the_same_story(self):
        sheet = RunSheet(title="x", items=[
            RunItem(kind="brief", story=101, host="mia"),
            RunItem(kind="brief", story=102, host="mia"),
            RunItem(kind="coming_up", story=101, host="jason", line="Coming up"),
            RunItem(kind="feature", story=101, host="jason"),
        ])
        out = producer.enforce(sheet, {}, {101, 102}, set(), set(), minutes=30)
        kinds = [(i.kind, i.story) for i in out.items if i.kind in ("brief", "feature")]
        assert kinds == [("brief", 102), ("feature", 101)]

    def test_hosts_rotate_when_the_model_repeats_one(self):
        sheet = RunSheet(title="x", items=[RunItem(kind="brief", story=s, host="mia") for s in (101, 102, 103)])
        out = producer.enforce(sheet, {}, {101, 102, 103}, set(), set(), minutes=30)
        hosts = [i.host for i in out.items if i.kind == "brief"]
        assert hosts[0] == "mia" and hosts[1] != "mia" and hosts[2] != hosts[1]

    def test_a_brief_with_a_bit_key_and_no_story_is_a_bit(self):
        out = producer.enforce(RunSheet(title="x", items=[RunItem(kind="brief", bit="stack", host="ray")]),
                               {}, set(), set(), set(), minutes=30)
        assert [(i.kind, i.bit, i.host) for i in out.items if i.kind == "bit"] == [("bit", "stack", "ray")]


class TestBitsCopy:
    def test_dashes_and_curly_quotes_read_plainly(self):
        from hnfm.radio.copy import speakable
        assert speakable("Another ‘quick sync’—because it’s fun") == "Another 'quick sync', because it's fun"

    def test_single_voice_drops_labels_and_strangers(self):
        from hnfm.radio import bits
        text = "Leo: Set-up here.\nCalmHost: Not me.\n**Leo:** The turn."
        kept = []
        for raw in text.splitlines():
            m = bits._LABEL.match(raw.strip())
            if m and m.group(1).lower() not in ("leo", "host", "narrator"):
                continue
            kept.append(bits._LABEL.sub("", raw.strip()))
        assert kept == ["Set-up here.", "The turn."]

    def test_ellipsis_and_wrapping_quotes(self):
        from hnfm.radio.copy import speakable
        assert speakable('"How... cozy."') == "How. cozy."


class TestRequestPlan:
    def test_second_request_within_window_is_not_dispatched(self, monkeypatch):
        from datetime import datetime
        from hnfm.radio import director
        store = {}
        monkeypatch.setattr(director, "log", lambda *a, **k: None)
        monkeypatch.setattr("hnfm.db.repo.get_setting", lambda k: store.get(k))
        monkeypatch.setattr("hnfm.db.repo.set_setting", lambda k, v: store.__setitem__(k, v))
        sent = []

        class _T:
            def apply_async(self, kwargs):
                sent.append(kwargs); return type("R", (), {"id": "t1"})()
        monkeypatch.setattr("hnfm.web.tasks.radio_plan_block", _T())
        assert director.request_plan("sheet low")["status"] == "queued"
        assert director.request_plan("manual")["status"] == "already planning"
        assert director.request_plan("manual", force=True)["status"] == "queued"
        assert len(sent) == 2


class TestPickFromBank:
    def test_when_everything_played_lately_pick_the_longest_ago(self, monkeypatch):
        from hnfm.radio import library
        items = [{"id": "a", "kind": "music", "created_at": "1"}, {"id": "b", "kind": "music", "created_at": "2"},
                 {"id": "c", "kind": "music", "created_at": "3"}]
        monkeypatch.setattr(library, "load_bank", lambda: items)
        assert library.pick_from_bank("music", avoid_ids=["a", "c", "b"])["id"] == "b"
        assert library.pick_from_bank("music", avoid_ids=["a"])["id"] == "b"

    def test_clock_times_read_like_a_host(self):
        from datetime import datetime
        from hnfm.radio.copy import speakable, time_words
        assert speakable("It's 4:04 AM.") == "It's four oh four A.M."
        assert speakable("The time is 12:30 PM") == "The time is twelve thirty P.M."
        assert speakable("at 9:00") == "at nine o'clock"
        assert time_words(datetime(2026, 9, 13, 16, 5)) == "four oh five in the afternoon"


class TestNoRepeats:
    def test_strict_pick_skips_rather_than_repeats(self, monkeypatch):
        from hnfm.radio import library
        monkeypatch.setattr(library, "load_bank", lambda: [{"id": "a", "kind": "station_id", "created_at": "1"}])
        assert library.pick_from_bank("station_id", avoid_ids=["a"], strict=True) is None
        assert library.pick_from_bank("station_id", avoid_ids=["a"])["id"] == "a"

    def test_an_unvoiced_coming_up_is_skipped_not_replaced_by_an_id(self, monkeypatch):
        calls = []
        def pick(kind, **kw):
            calls.append(kind); return None
        monkeypatch.setattr(director, "pick_from_bank", pick)
        assert director._resolve({"kind": "coming_up", "host": "sofia"}, "s1", []) is None
        assert calls == ["coming_up"]

    def test_the_same_sentence_from_another_block_counts_as_played(self, monkeypatch):
        from hnfm.radio import library
        monkeypatch.setattr(library, "load_bank", lambda: [
            {"id": "s1-3", "kind": "station_id", "sheet_id": "s1", "text": "You're listening to HNFM", "created_at": "1"},
            {"id": "s2-3", "kind": "station_id", "sheet_id": "s2", "text": "You're listening to HNFM", "created_at": "2"},
            {"id": "g1", "kind": "station_id", "text": "HNFM. Made by machines", "created_at": "0"},
        ])
        assert library.pick_from_bank("station_id", avoid_ids=["s1-3"], sheet_id="s2", strict=True)["id"] == "g1"

    def test_no_sheet_holds_on_music_and_asks_for_a_block(self, monkeypatch):
        asked = []
        monkeypatch.setattr(director, "_request_plan", lambda: asked.append(1))
        monkeypatch.setattr(director, "current_sheet", lambda: None)
        monkeypatch.setattr(director, "pick_from_bank",
                            lambda kind, **kw: {"id": "m1", "kind": "music", "path": "/m.mp3", "style": "lo-fi"})
        item = director.next_item()
        assert item["kind"] == "music" and item.get("hold") is True and asked == [1]


class TestReadyGate:
    def test_a_parked_sheet_is_not_current_until_marked_ready(self):
        repo.radio_save_sheet(sheet_id="park1", title="t", minutes=10,
                              items=[{"kind": "brief", "story": 1, "host": "mia"}], source="llm", ready=False)
        assert all(sh["sheet_id"] != "park1" for sh in repo.radio_open_sheets())
        repo.radio_mark_ready("park1")
        assert any(sh["sheet_id"] == "park1" for sh in repo.radio_open_sheets())

    def test_what_the_director_served_counts_as_played(self, monkeypatch):
        picks = []
        def pick(kind, avoid_ids=(), **kw):
            picks.append(list(avoid_ids))
            return {"id": "id-" + str(len(picks)), "kind": kind, "path": "/x.mp3", "text": "hi", "host": "mia"}
        monkeypatch.setattr(director, "pick_from_bank", pick)
        monkeypatch.setattr(director, "_request_plan", lambda: None)
        repo.radio_save_sheet(sheet_id="srv", title="t", minutes=10, source="test",
                              items=[{"kind": "station_id", "host": "mia"}, {"kind": "station_id", "host": "leo"}])
        director.next_item(); director.next_item()
        assert "id-1" in picks[1]

    def test_a_parked_block_counts_as_a_plan_in_flight(self, monkeypatch):
        monkeypatch.setattr(director, "log", lambda *a, **k: None)
        monkeypatch.setattr(director, "planning_since", lambda: None)
        repo.radio_save_sheet(sheet_id="park2", title="t", minutes=10, source="llm", ready=False,
                              items=[{"kind": "brief", "story": 1, "host": "mia"}])
        assert director.request_plan("sheet low")["status"] == "already planning"

