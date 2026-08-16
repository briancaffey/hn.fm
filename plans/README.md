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

## Phase 2 — content quality & output volume (2026-08-16)

Plans 1–7 built the *machine*. Plans 8–15 are about what comes out of it: better
scripts, better visuals, comment-aware storytelling, measurable quality, and volume.

| # | Milestone | Doc | Status | Depends on |
|---|------|-----|--------|------------|
| 8 | LLM foundation: structured output, versioned prompts, loud failures | [08-llm-foundation.md](08-llm-foundation.md) | **done** (2026-08-16) — + model allowlist, structured script, 200 tests green | — |
| 9 | Two-axis scoring (interest × producibility) + the Story Brief | [09-story-brief-and-scoring.md](09-story-brief-and-scoring.md) | not started | 8, extends 4 |
| 10 | Comment mining with provenance | [10-comment-mining.md](10-comment-mining.md) | not started | 9 |
| 11 | The agentic script room | [11-agentic-script-room.md](11-agentic-script-room.md) | not started | 9, 10 |
| 12 | Style Bible + per-story Style Contract | [12-style-system.md](12-style-system.md) | not started | 9 |
| 13 | Art-direction agent: shot list + frame critic | [13-art-direction-agent.md](13-art-direction-agent.md) | not started | 11, 12 |
| 14 | Output quality gate + evals | [14-quality-gate.md](14-quality-gate.md) | not started | 11, 13 |
| 15 | Throughput (supersedes plan 6) | [15-throughput.md](15-throughput.md) | not started | 14 |

**Phase 2 sequencing.** 8 is the enabler — everything after it is a prompt, and
prompts you can't version or replay can't be improved deliberately. 9 and 10 build the
*inputs* (a brief, and the thread's contribution to it); 11 and 12/13 consume them for
words and pictures respectively and can proceed in parallel once 9 lands. 14 before
15 is the important one: a quality gate must exist before volume, or scaling just
multiplies the current quality.

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
