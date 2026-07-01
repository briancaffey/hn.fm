# Plan 6 — Automation

Once triage (Plan 4) can tell good stories from bad, close the loop: the system watches HN on a schedule, triages everything, and either queues winners for your approval or generates them outright.

## Design

- **Celery Beat schedules** (beat container already exists in docker-compose but has no app schedules):
  - every N hours: fetch top + new stories → run the cheap half + triage score (idempotent — skip items already triaged)
  - optional daily: auto-generate top-K ranked ungenerated stories (`AUTO_GENERATE_TOP_K`, default 0 = off)
- **Modes** (config): `manual` (triage only, you click Generate — the default), `semi` (auto-generate but require approval before any publish step), `auto` (full send).
- **Budget guardrails:** daily caps on generations and on GPU-stage failures before the scheduler pauses itself; caps visible on the dashboard.
- **Digest surface:** the Triage page (Plan 4) doubles as the morning review: "12 new stories scored overnight, 3 great." Optionally a daily summary notification later.
- Retry policy: transient stage failures (service down, timeout) retry with backoff via Celery; content failures (paywall) don't.

## Tasks

- [ ] Beat schedule entries + idempotent scheduled tasks (fetch/triage sweep)
- [ ] Auto-generate top-K task with mode + caps config
- [ ] Scheduler status card (last sweep, next sweep, caps used) on dashboard
- [ ] Failure backoff + self-pause on repeated GPU-stage failures
