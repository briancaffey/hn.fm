"""What runs on a timer, and the two switches that stop it.

The schedule is data in config.yaml (`schedule.jobs`): each job names a task,
a cadence (`every: 10m` or `cron: "0 10 * * *"`), the gate it sits behind, and
the kwargs it dispatches with. Celery beat is built from this list, and the
/schedule page reads the same list, so the UI can never drift from what beat
is actually doing.

Two runtime overrides live in the database (see `db.repo.get_setting`), not
in config, because they are meant to be flipped from the UI while everything
keeps running:

    scraping_paused    - jobs gated `scraping` (fetching HN lists, scoring the
                         backlog) are skipped at fire time
    generation_paused  - jobs gated `generation` (digests, renders, Kindle
                         sends) are skipped at fire time

Skipping happens when the job fires, not by rewriting beat: the wrapper task
`hnfm.web.tasks.scheduled_job` consults the flags and records a skipped run,
so a paused schedule is still visible as a schedule.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

from celery.schedules import crontab, schedule as interval_schedule

GATE_SCRAPING = "scraping"
GATE_GENERATION = "generation"
GATE_NONE = "none"
GATES = (GATE_SCRAPING, GATE_GENERATION, GATE_NONE)

SETTING_SCRAPING_PAUSED = "schedule.scraping_paused"
SETTING_GENERATION_PAUSED = "schedule.generation_paused"
SETTING_LAST_RUN_PREFIX = "schedule.last_run."

_EVERY = re.compile(r"^\s*(\d+)\s*([smhd])\s*$")
_UNIT_SECONDS = {"s": 1, "m": 60, "h": 3600, "d": 86400}


@dataclass
class Job:
    name: str
    task: str
    gate: str = GATE_NONE
    every: Optional[int] = None  # seconds
    cron: Optional[str] = None  # five-field crontab, UTC
    kwargs: Dict = field(default_factory=dict)
    enabled: bool = True
    why: str = ""

    @property
    def cadence(self) -> str:
        """Human wording for the UI."""
        if self.cron:
            return describe_cron(self.cron)
        if self.every:
            return "every " + describe_seconds(self.every)
        return "never"

    def celery_schedule(self):
        if self.cron:
            # Named, because crontab()'s positional order is NOT cron's:
            # it takes day_of_week third. Passing five cron fields
            # positionally turned "Saturday" into "June".
            minute, hour, dom, month, dow = _cron_fields(self.cron)
            return crontab(minute=minute, hour=hour, day_of_month=dom,
                           month_of_year=month, day_of_week=dow)
        return interval_schedule(timedelta(seconds=self.every))

    def next_run(self, last_dispatch: Optional[datetime], now: Optional[datetime] = None) -> Optional[datetime]:
        """Best estimate without beat's private state. Cron is exact (it is a
        function of the clock); an interval is last dispatch + period, and
        unknown until the first dispatch."""
        now = now or datetime.now(timezone.utc)
        if self.cron:
            # remaining_estimate() measures from the real clock, so build the
            # next occurrence from remaining_delta(), which is relative to
            # the instant passed in — testable, and honest about "now".
            start, delta, _to_local = self.celery_schedule().remaining_delta(now)
            return start + delta
        if self.every and last_dispatch:
            if last_dispatch.tzinfo is None:
                last_dispatch = last_dispatch.replace(tzinfo=timezone.utc)
            due = last_dispatch + timedelta(seconds=self.every)
            return due if due > now else now
        return None


def parse_every(text) -> int:
    """'10m' -> 600. Accepts s/m/h/d, or a bare number of seconds."""
    if isinstance(text, (int, float)):
        return int(text)
    m = _EVERY.match(str(text))
    if not m:
        raise ValueError(f"unparseable interval {text!r} (want e.g. 10m, 6h, 1d)")
    return int(m.group(1)) * _UNIT_SECONDS[m.group(2)]


def _cron_fields(text: str) -> List[str]:
    parts = str(text).split()
    if len(parts) != 5:
        raise ValueError(f"cron {text!r} needs five fields: min hour dom month dow")
    return parts


def describe_seconds(seconds: int) -> str:
    for unit, size in (("d", 86400), ("h", 3600), ("m", 60)):
        if seconds % size == 0 and seconds >= size:
            n = seconds // size
            word = {"d": "day", "h": "hour", "m": "min"}[unit]
            if n > 1 and unit != "m":
                word += "s"
            return f"{n} {word}"
    return f"{seconds} s"


def describe_cron(text: str) -> str:
    minute, hour, dom, month, dow = _cron_fields(text)
    if minute.isdigit() and hour.isdigit() and dom == "*" and month == "*":
        at = f"{int(hour):02d}:{int(minute):02d} UTC"
        if dow == "*":
            return f"daily at {at}"
        days = {"0": "Sun", "1": "Mon", "2": "Tue", "3": "Wed", "4": "Thu", "5": "Fri", "6": "Sat"}
        if dow in days:
            return f"{days[dow]} at {at}"
        return f"{at} on dow {dow}"
    return f"cron {text}"


def _job_from_config(name: str, raw: dict) -> Job:
    raw = raw or {}
    gate = str(raw.get("gate") or GATE_NONE)
    if gate not in GATES:
        raise ValueError(f"job {name}: gate must be one of {GATES}, got {gate!r}")
    every = raw.get("every")
    cron = raw.get("cron")
    if bool(every) == bool(cron):
        raise ValueError(f"job {name}: set exactly one of `every` or `cron`")
    if cron:
        _cron_fields(cron)
    return Job(
        name=name,
        task=str(raw["task"]),
        gate=gate,
        every=parse_every(every) if every else None,
        cron=str(cron) if cron else None,
        kwargs=dict(raw.get("kwargs") or {}),
        enabled=bool(raw.get("enabled", True)),
        why=str(raw.get("why") or ""),
    )


def load_jobs(config: Optional[dict] = None) -> List[Job]:
    """Jobs from config.yaml `schedule.jobs`, in file order. A malformed job
    raises: a schedule that silently drops entries is worse than one that
    refuses to start."""
    if config is None:
        from .utils.config import config_manager

        config = config_manager.get("schedule", {}) or {}
    jobs = config.get("jobs") or {}
    return [_job_from_config(name, raw) for name, raw in jobs.items()]


def get_job(name: str) -> Optional[Job]:
    return next((j for j in load_jobs() if j.name == name), None)


def schedule_enabled(config: Optional[dict] = None) -> bool:
    """SCHEDULE_ENABLED wins over config; default on. Beat with nothing
    scheduled is harmless, so a checkout without credentials still runs the
    cheap jobs and skips sends (see tasks.scheduled_job)."""
    env = os.getenv("SCHEDULE_ENABLED")
    if env is not None:
        return env.strip().lower() == "true"
    if config is None:
        from .utils.config import config_manager

        config = config_manager.get("schedule", {}) or {}
    return bool(config.get("enabled", True))


def beat_schedule(config: Optional[dict] = None) -> dict:
    """The Celery beat table. Every entry fires the same wrapper task with the
    job name; the wrapper does the gating and the real dispatch, so beat
    itself never touches the database."""
    if not schedule_enabled(config):
        return {}
    table = {}
    for job in load_jobs(config):
        if not job.enabled:
            continue
        table[job.name] = {
            "task": "hnfm.web.tasks.scheduled_job",
            "schedule": job.celery_schedule(),
            "args": [job.name],
        }
    return table
