"""The schedule: config parsing, beat table, gating, churn probe, and the API.

Every test runs against the sqlite fixture from conftest; nothing here
touches the broker (dispatches are patched), because a test that enqueues a
real task runs it on the live workers against production Postgres.
"""

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from hnfm import schedule as sched
from hnfm.db import repo


SAMPLE = {
    "enabled": True,
    "jobs": {
        "fetch-new": {"task": "hnfm.web.tasks.fetch_hn_list", "every": "10m",
                      "gate": "scraping", "kwargs": {"list_name": "new", "limit": 60}},
        "digest": {"task": "hnfm.web.tasks.build_digest", "cron": "0 10 * * *",
                   "gate": "generation", "kwargs": {"shape": "punchline", "send": True}},
        "off": {"task": "x", "every": "1h", "enabled": False},
    },
}


class TestConfig:
    def test_parse_every(self):
        assert sched.parse_every("10m") == 600
        assert sched.parse_every("6h") == 21600
        assert sched.parse_every("1d") == 86400
        assert sched.parse_every(45) == 45
        with pytest.raises(ValueError):
            sched.parse_every("soon")

    def test_jobs_load_in_order_with_cadence_words(self):
        jobs = sched.load_jobs(SAMPLE)
        assert [j.name for j in jobs] == ["fetch-new", "digest", "off"]
        assert jobs[0].cadence == "every 10 min"
        assert jobs[1].cadence == "daily at 10:00 UTC"
        assert sched.describe_cron("0 11 * * 6") == "Sat at 11:00 UTC"

    def test_cron_fields_map_to_the_right_celery_slots(self):
        """crontab() takes day_of_week THIRD, unlike cron. The Saturday job
        was scheduling for June before this was pinned."""
        job = sched.load_jobs({"jobs": {"sat": {"task": "t", "cron": "0 11 * * 6"}}})[0]
        c = job.celery_schedule()
        assert c.day_of_week == {6}
        assert c.month_of_year == set(range(1, 13))
        assert c.day_of_month == set(range(1, 32))

    def test_a_job_needs_exactly_one_cadence(self):
        with pytest.raises(ValueError):
            sched.load_jobs({"jobs": {"x": {"task": "t", "every": "1m", "cron": "* * * * *"}}})
        with pytest.raises(ValueError):
            sched.load_jobs({"jobs": {"x": {"task": "t"}}})

    def test_an_unknown_gate_is_refused(self):
        with pytest.raises(ValueError):
            sched.load_jobs({"jobs": {"x": {"task": "t", "every": "1m", "gate": "sometimes"}}})

    def test_beat_table_fires_the_wrapper_and_skips_disabled(self):
        table = sched.beat_schedule(SAMPLE)
        assert set(table) == {"fetch-new", "digest"}
        assert all(e["task"] == "hnfm.web.tasks.scheduled_job" for e in table.values())
        assert table["fetch-new"]["args"] == ["fetch-new"]

    def test_schedule_enabled_env_wins(self, monkeypatch):
        monkeypatch.setenv("SCHEDULE_ENABLED", "false")
        assert sched.beat_schedule(SAMPLE) == {}
        monkeypatch.setenv("SCHEDULE_ENABLED", "true")
        assert sched.schedule_enabled({"enabled": False}) is True

    def test_next_run_estimates(self):
        jobs = {j.name: j for j in sched.load_jobs(SAMPLE)}
        now = datetime(2026, 9, 8, 9, 0, tzinfo=timezone.utc)
        assert jobs["digest"].next_run(None, now) == datetime(2026, 9, 8, 10, 0, tzinfo=timezone.utc)
        assert jobs["fetch-new"].next_run(None, now) is None
        assert jobs["fetch-new"].next_run(now - timedelta(minutes=4), now) == now + timedelta(minutes=6)
        assert jobs["fetch-new"].next_run(now - timedelta(hours=1), now) == now


class TestGating:
    @pytest.fixture(autouse=True)
    def _jobs(self, monkeypatch):
        orig = sched.load_jobs
        monkeypatch.setattr(sched, "load_jobs", lambda config=None: orig(SAMPLE))

    def test_paused_scraping_skips_and_records(self, monkeypatch):
        from hnfm.web import tasks

        sent = []
        monkeypatch.setattr(tasks.celery_app, "send_task", lambda *a, **k: sent.append((a, k)))
        repo.set_setting(sched.SETTING_SCRAPING_PAUSED, True)
        out = tasks.scheduled_job("fetch-new")
        assert out["status"] == "skipped" and "paused" in out["note"]
        assert sent == []
        assert repo.get_setting(sched.SETTING_LAST_RUN_PREFIX + "fetch-new")["status"] == "skipped"

    def test_force_ignores_the_pause(self, monkeypatch):
        from hnfm.web import tasks

        class _T:
            id = "t-1"

        sent = []
        monkeypatch.setattr(tasks.celery_app, "send_task", lambda name, kwargs=None: sent.append((name, kwargs)) or _T())
        repo.set_setting(sched.SETTING_SCRAPING_PAUSED, True)
        out = tasks.scheduled_job("fetch-new", force=True)
        assert out["status"] == "dispatched" and out["task_id"] == "t-1"
        assert sent == [("hnfm.web.tasks.fetch_hn_list", {"list_name": "new", "limit": 60})]

    def test_generation_pause_does_not_touch_scraping(self, monkeypatch):
        from hnfm.web import tasks

        class _T:
            id = "t-2"

        sent = []
        monkeypatch.setattr(tasks.celery_app, "send_task", lambda name, kwargs=None: sent.append(name) or _T())
        repo.set_setting(sched.SETTING_GENERATION_PAUSED, True)
        assert tasks.scheduled_job("fetch-new")["status"] == "dispatched"
        assert tasks.scheduled_job("digest")["status"] == "skipped"
        assert sent == ["hnfm.web.tasks.fetch_hn_list"]

    def test_send_is_dropped_when_mail_is_not_configured(self, monkeypatch):
        from hnfm.web import tasks

        class _T:
            id = "t-3"

        sent = []
        monkeypatch.setattr(tasks.celery_app, "send_task", lambda name, kwargs=None: sent.append(kwargs) or _T())
        for v in ("BREVO_API_KEY", "DIGEST_FROM_EMAIL", "KINDLE_EMAIL"):
            monkeypatch.delenv(v, raising=False)
        monkeypatch.setenv("EMAIL_PROVIDER", "brevo")
        out = tasks.scheduled_job("digest")
        assert out["status"] == "dispatched"
        assert sent[0]["send"] is False
        assert "without sending" in out["note"]


class TestProbe:
    def test_first_sample_has_no_deltas_then_counts_movement(self, monkeypatch):
        from hnfm.web import tasks

        lists = {"new": [5, 4, 3, 2, 1], "top": [10, 20, 30]}
        monkeypatch.setattr("hnfm.utils.hn_utils.get_new_story_ids", lambda: lists["new"])
        monkeypatch.setattr("hnfm.utils.hn_utils.get_top_story_ids", lambda: lists["top"])
        first = tasks.probe_hn_churn()
        assert first["new"]["new"] is None
        lists["new"] = [7, 6, 5, 4, 3]
        lists["top"] = [10, 99, 30]
        second = tasks.probe_hn_churn()
        assert second["new"]["new"] == 2
        assert second["top"]["front_changed"] == 1
        rows = repo.list_samples("new", datetime.utcnow() - timedelta(minutes=5))
        assert [r["new_count"] for r in rows] == [None, 2]


class TestApi:
    @pytest.fixture
    def client(self, monkeypatch):
        orig = sched.load_jobs
        monkeypatch.setattr(sched, "load_jobs", lambda config=None: orig(SAMPLE))
        from hnfm.web.api import app

        return TestClient(app)

    def test_schedule_lists_jobs_and_controls(self, client):
        body = client.get("/api/schedule").json()
        assert body["timezone"] == "UTC"
        assert [j["name"] for j in body["jobs"]] == ["fetch-new", "digest", "off"]
        assert body["jobs"][1]["next_run"] is not None
        assert body["jobs"][2]["enabled"] is False
        assert body["controls"] == {"scraping_paused": False, "generation_paused": False}
        assert "new" in body["churn"] and "top" in body["churn"]

    def test_controls_persist_only_the_keys_sent(self, client):
        out = client.post("/api/schedule/controls", json={"generation_paused": True}).json()
        assert out == {"scraping_paused": False, "generation_paused": True,
                       "changed": {"generation_paused": True}}
        assert client.get("/api/schedule").json()["controls"]["generation_paused"] is True

    def test_run_now_rejects_unknown_jobs(self, client, monkeypatch):
        from hnfm.web import tasks

        class _T:
            id = "t-9"

        monkeypatch.setattr(tasks.scheduled_job, "apply_async", lambda **k: _T())
        assert client.post("/api/schedule/jobs/nope/run").status_code == 404
        assert client.post("/api/schedule/jobs/fetch-new/run").json()["task_id"] == "t-9"
