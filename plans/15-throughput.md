# Plan 15 — Throughput: from hand-run to a studio that runs itself

**Milestone 8, deliberately last.** Scaling output before the quality gate (plan 14)
exists just multiplies whatever quality you currently have. Once the gate is real,
volume becomes safe.

This subsumes plan 6 (automation), which was written before the scoring work landed.

## The bottlenecks, honestly

- **One Celery worker.** `docker-compose.yml` runs a single `celery-worker`; long image
  and LTX steps serialise behind each other and behind cheap text tasks.
- **Shared GPU services.** Flux, LTX, Magpie, ACE-Step and the LLM gateway are all on
  the same `inference-club` cluster. More workers means contention, not throughput,
  unless queues are separated and concurrency is capped per service.
- **The cheap half is nearly free.** Scrape → brief → triage is text-only. It can run
  at high volume continuously; only the GPU half needs rationing.
- **Disk.** Noted in memory as a recurring problem: outputs fill fast. At 10×/day this
  becomes the first thing to break.

## Design

### Split the queues
Separate Celery queues by resource — `text` (scrape, brief, triage, script room),
`gpu_image`, `gpu_video`, `gpu_audio`, `cpu` (ffmpeg assembly) — with independent
worker counts and per-queue concurrency matched to what each backing service can take.
Text workers scale freely; GPU queues stay at the service's real capacity.

### Scheduled ingest → triage → auto-generate
Celery Beat: poll top/new on an interval → fetch → cheap half → two-axis score. Then a
producer task picks the top N by rank subject to a **daily budget** (max segments, max
GPU minutes) and a diversity rule — no more than K stories from the same domain or
topic cluster per day, so the feed doesn't become all-LLM-news.

### Backpressure and resumability
Health-check each service via the existing `utils/service_registry.py` before
dispatching to its queue; pause that queue rather than failing runs when a service is
down. The audit trail already supports `rerun_step`, so a paused pipeline resumes at
the failing step instead of regenerating from scratch — make that the automatic
recovery path.

### Retention
Tiered cleanup: keep finished MP4s and episode MP3s in MinIO, drop intermediate frames
and raw WAVs for runs older than N days, and keep everything for anything starred or
`gate=pass`. Report disk headroom on the observability page.

## Targets

Set them explicitly so "increase output" has a number:

| | now | target |
|---|---|---|
| segments/day | hand-run, a few | 10–20 auto-generated |
| gate=pass rate | unmeasured | >70% |
| GPU minutes/segment | unmeasured | tracked and trending down |
| human touches/published video | every one | ~0 for pass, review only for `gate=review` |

## Tasks

- [ ] Split Celery queues by resource; per-queue worker counts and concurrency caps
- [ ] Celery Beat schedule: ingest → cheap half → score, continuously
- [ ] Auto-generate producer: top-N by rank, daily budget, domain/topic diversity cap
- [ ] Backpressure via `service_registry` health checks; pause-not-fail per queue
- [ ] Automatic resume-from-failing-step using `rerun_step`
- [ ] Tiered retention + disk headroom on the observability dashboard
- [ ] Throughput panel: segments/day, gate-pass rate, GPU minutes/segment, cost/segment
- [ ] Publishing hooks (YouTube / RSS already partly there via the podcast feed)
