# hn.fm — Grand Plan

North star: an automated studio that watches Hacker News, triages stories worth making videos about, generates them through an observable pipeline, and makes every step inspectable, editable, and re-runnable — with voices you can clone in minutes.

This file tracks the sub-plans. Each sub-plan is its own doc with design details and a task checklist. Update the status column as work lands.

## Sub-plans

| # | Plan | Doc | Status | Depends on |
|---|------|-----|--------|------------|
| 1 | Postgres foundation (replace Redis data store) | [01-postgres-migration.md](01-postgres-migration.md) | **done** (2026-07-01) — data backfilled, 105 tests green; final cleanup of old `hnfm:*` Redis keys pending | — |
| 2 | Pipeline audit trail + regenerate-from-step | [02-audit-trail.md](02-audit-trail.md) | **done** (2026-07-01) — metrics.py retirement deferred to plan 3 | 1 |
| 3 | UI overhaul (full-width, dense tables, X-ray view) | [03-ui-overhaul.md](03-ui-overhaul.md) | **core done** (2026-07-01) — a few cleanups listed in the doc | 1 (partially), 2 (X-ray) |
| 4 | Story scoring & ranked triage (+ human feedback, + audio-first/podcast) | [04-story-scoring.md](04-story-scoring.md) | **done** (2026-07-01) — Algolia search + content re-calibration pending | 1 |
| 5 | Voice onboarding (YouTube → DIA voice sample) | [05-voice-onboarding.md](05-voice-onboarding.md) | not started | — |
| 6 | Automation (scheduled ingest → triage → generate) | [06-automation.md](06-automation.md) | not started | 4 |
| 7 | MinIO object store for media artifacts | [07-minio-object-store.md](07-minio-object-store.md) | **done** (2026-07-01) — publish hooks + MinIO-first serving; local-disk reclaim pending | — |

## Sequencing rationale

**Postgres first (1).** Everything else wants relational queries: the story list needs per-story generation counts (a JOIN), triage needs ranking/filtering (ORDER BY score, WHERE flags), and the audit trail needs a proper step-records table. Doing these on Redis key-scans would mean building them twice. The migration is well-bounded: ~46 Redis call sites across 6 modules, all JSON-blob CRUD with no exotic Redis features (see sub-plan 1).

**Audit trail second (2).** The `pipeline_steps` table is the backbone for the X-ray UI, regenerate-from-step, and richer observability. It generalizes the existing `metrics.py` per-stage recording into per-step records with captured inputs (prompts, seeds, params) so any step can be edited and re-run.

**UI (3), scoring (4), voices (5) can proceed in parallel** once 1–2 are in. Voice onboarding (5) has no dependency on Postgres at all (DIA reads files from `voices/`) and can be built any time.

**Automation last (6).** Only worth automating once triage (4) can tell good stories from bad ones.

## Current architecture (as of 2026-07-01)

- **Backend:** Python (uv), FastAPI (`src/hnfm/web/api.py`) + Celery single-worker (`src/hnfm/web/celery_app.py`), Redis as both data store and broker.
- **Data model:** HNItem → ProcessedRun → Segment → (SegmentSection, SegmentImage), all Pydantic models serialized as JSON strings in Redis (`hnfm:*` keys), artifacts on disk under `outputs/hn/item/{id}/runs/{run}/segments/{seg}/`.
- **Pipeline stages:** scrape (Firecrawl + Wayback fallback) → summarize/enrich → script ([S1]/[S2] dialogue) → audio (Magpie or DIA TTS + Studio Voice enhancement + WhisperX ASR/QA) → images (Flux via NIM or InvokeAI, themed art direction, vision-planned sequences) → media plan (meta-sequencer picks image_sequence / LTX video / hyperframe per section, with critic pass) → video assembly (FFmpeg + subtitles + optional music bed).
- **Observability:** `src/hnfm/utils/metrics.py` records per-stage seconds/tokens/counts to `hnfm:metrics:*`; dashboard at `frontend/app/pages/observability.vue`.
- **Frontend:** Nuxt 4 + Tailwind 4 + shadcn-nuxt, pages for items / item / run / segment / compare / observability / services / admin. TanStack Table is installed but unused.
- **Inference services:** k8s `inference-club` cluster via `scripts/port-forwards.sh` (Magpie TTS, LTX-2, Flux, ACE-Step, Nemotron ASR, Firecrawl); DIA (`services/dia/`) and WhisperX (`services/whisperx/`) run separately.
