# Plan 2 — Pipeline audit trail + regenerate-from-step

Give every generation a complete X-ray: an ordered record of every step the pipeline took — with the exact inputs it used (prompts, params, seeds) and the outputs it produced — and make any step editable and re-runnable from that point.

## What exists today

- `src/hnfm/utils/metrics.py` records per-*stage* seconds/tokens/counts (7 stages: scrape, source_images, script, audio, images, media_plan, video) into one metrics blob per segment. Great for the dashboard, but it doesn't capture *inputs* (prompts, seeds, params) or per-call granularity, so you can't inspect or replay from it.
- Partial regeneration already exists and proves the pattern: `rebuild_single_image` (`tasks.py:890-1021`) accepts `prompt_override`/`line_override`; per-section audio rebuild exists too. The UI already has edit + regenerate on images and sections.
- Every stage already writes its artifacts to deterministic disk paths, so "output refs" are mostly free.

## Design

### `pipeline_steps` table

```sql
pipeline_steps (
  id BIGSERIAL PK,
  segment_id FK → segments,          -- NULL for run-scoped steps (scrape, summary)
  run_id FK → runs,
  stage TEXT,                        -- scrape | script | audio | images | media_plan | video …
  step_key TEXT,                     -- e.g. 'images/3/root', 'images/3/frame_2', 'audio/sec_5', 'script', 'media_plan/critic'
  seq INT,                           -- global order within the run
  status TEXT,                       -- running | ok | error | stale | superseded
  started_at, finished_at, seconds REAL,
  model TEXT, tokens_in INT, tokens_out INT,
  inputs JSONB,                      -- the replay payload: prompt(s), params, seed, source refs
  outputs JSONB,                     -- artifact paths, text outputs, structured results
  error TEXT,
  supersedes BIGINT FK → pipeline_steps  -- set when a step is a regeneration of an earlier one
)
```

Key idea: **`inputs` must be sufficient to re-run the step.** For an LLM call that's the full messages + model + params; for an image that's prompt + theme + dims + seed; for TTS that's text + voice + backend + params. This is what turns the audit trail from a log into a control surface.

### Recording

- Replace the `metrics.py` module-global with a `StepRecorder` bound to the current run/segment (still fine as a module global under the single-worker model — same constraint as today).
- Instrument at the call boundaries that already exist: `llm_service.py` (all LLM calls already flow through one place and already report usage), `tts_api_service.py`, image service factory, `ltx_service.py`, hyperframes producer, ffmpeg assembly.
- Stage-level rollups for the existing observability dashboard become a `GROUP BY stage` over steps — the `/api/metrics` contract can be preserved as a view.

### Regenerate-from-step

1. UI shows the step timeline; user expands a step, sees `inputs` rendered as an editable form (prompt textarea, params, seed).
2. `POST /api/steps/{id}/rerun` with optional input overrides → creates a new step (`supersedes` pointing at the old one), executes just that unit of work, updates the owning entity (image/section/segment field) exactly like `rebuild_single_image` does today.
3. **Downstream invalidation:** rerunning a step marks dependent steps `stale` (e.g. new section audio → combined.wav, ASR, subtitles, video are stale; new image root → sequence frames, motion clip, video are stale). Staleness is display + a "rebuild stale" button — not automatic cascade — so you stay in control and don't burn GPU time accidentally.
4. Dependency edges are static per stage (a small hand-written map, not a general graph engine). You explicitly said no graph needed — this is just "which stages read which outputs."

## Tasks

- [x] Alembic migration 0002 for `pipeline_steps`; recorder in `src/hnfm/db/steps.py` (step() contextmanager, non-fatal, LLM token attribution, input bounding, latest-wins supersession)
- [x] Instrument LLM service (model + tokens attributed to the current step)
- [x] Instrument scrape/summary/enrich/script, per-section TTS, stitch, ASR, per-image prompt/root/sequence frames, media plan + LTX/hyperframe clips (soft_fail for non-fatal clip failures), video assembly
- [x] Static stage-dependency map (`stale_patterns_for`) + staleness marking; `rebuild-stale` endpoint (currently resolves to video reassembly; upstream reruns refresh stitch/ASR themselves)
- [x] `GET /api/hn/items/{i}/runs/{r}[/segments/{s}]/steps`, `POST /api/steps/{id}/rerun` (overrides: prompt/line_text/text/script/regenerate_prompt), `POST .../rebuild-stale`
- [x] Reruns route onto existing rebuild machinery (`rerun_step` task: script / audio section / image root / ASR / media plan / video)
- [x] "Pipeline X-Ray" timeline section on the segment page (grouped by stage, status dots, expandable inputs/outputs, editable rerun, history toggle, rebuild-stale button)
- [ ] Port `/api/metrics` to read from steps and retire `metrics.py` — deferred to plan 3 (dashboard moves to steps then; both record in parallel for now, cheap)
- [ ] Known gap for plan 3 UI: after a `script` rerun everything downstream goes stale, but rebuild-stale only reassembles video — audio/images need explicit per-step reruns first (the endpoint reports them as `skipped`)

Status: **done 2026-07-01** (46 dedicated tests; live-verified scrape/summary/enrich steps against real Postgres + LLM).

## Notes

- Keep step `inputs` for LLM calls complete but bounded (truncate giant article bodies with a ref to the run's `content_clean` instead of duplicating it).
- Seeds: image/TTS/LTX calls should always record the seed actually used (DIA already returns `x-seed`) so a rerun-without-edits is reproducible.
