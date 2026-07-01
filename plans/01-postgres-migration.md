# Plan 1 — Postgres foundation

Replace Redis as the application data store with Postgres + SQLAlchemy 2.0 + Alembic. Redis stays only as the Celery broker/result backend, which is what it's actually good at here.

## Why

- The data is fully relational: HNItem 1→N ProcessedRun 1→N Segment 1→N (Section, Image). Redis forces manual list-maintenance (`hnfm:item:{id}:runs`, `img_list`, `sec_list`) and SCAN-based enumeration for anything list-shaped.
- Upcoming features are queries: per-story generation counts, ranked triage (`ORDER BY suitability_score`), audit-trail step timelines, dashboard aggregates. All trivial in SQL, all painful as key scans.
- No exotic Redis features are in use: no TTLs (except Celery), no Lua, no pub/sub, no transactions. Just JSON-blob CRUD, two INCR counters, and ordered lists — all map cleanly to tables.

## Stack choice

- **SQLAlchemy 2.0** (typed ORM, mature) + **Alembic** for migrations + **psycopg 3** driver.
- Keep the existing **Pydantic models** (`src/hnfm/web/models.py`) as API/serialization schemas; ORM models live in a new `src/hnfm/db/` package. Don't use SQLModel — the Pydantic models are already load-bearing in prompts/tasks and coupling them to table shape would make schema evolution harder.
- Sync engine (Celery tasks are sync; FastAPI endpoints can use sync sessions via dependency, worker is single-concurrency anyway).

## Schema (v1)

```sql
hn_items         (id BIGINT PK,           -- HN item id, natural key
                  type, by, time TIMESTAMPTZ, url, title, text,
                  score INT, descendants INT, kids JSONB,
                  fetched_at TIMESTAMPTZ)

runs             (id BIGSERIAL PK,
                  item_id BIGINT FK → hn_items,
                  run_number INT,          -- preserves existing run numbering
                  UNIQUE (item_id, run_number),
                  created_at, source_url,
                  content_raw TEXT, content_clean TEXT, summary TEXT,
                  short_description TEXT, tags JSONB, emoji TEXT, haiku TEXT,
                  source_images JSONB)     -- folds hnfm:item:{id}:run:{n}:source_images in

segments         (id BIGSERIAL PK,
                  run_id BIGINT FK → runs,
                  seg_number INT, UNIQUE (run_id, seg_number),
                  created_at, script TEXT,
                  style_theme TEXT, aspect_format TEXT, meta_plan JSONB,
                  audio_ready BOOL, images_ready BOOL, video_ready BOOL,
                  audio_path, combined_audio_path, asr_json_path, asr_qa JSONB,
                  video_path, subtitles_path)

segment_sections (id BIGSERIAL PK, segment_id FK → segments,
                  section_number INT, UNIQUE (segment_id, section_number),
                  text TEXT, cleaned BOOL, audio_path TEXT,
                  duration_ms INT, start_ms INT, created_at, updated_at)

segment_images   (id BIGSERIAL PK, segment_id FK → segments,
                  image_index INT, UNIQUE (segment_id, image_index),
                  line_text TEXT, prompt TEXT, image_path TEXT,
                  sequence_paths JSONB, video_clip_path TEXT,
                  video_clip_seconds REAL, start_ms INT, duration_ms INT,
                  alignment JSONB, created_at, updated_at)

pipeline_metrics (id BIGSERIAL PK, segment_id FK → segments,
                  stages JSONB, counts JSONB, status TEXT,
                  theme TEXT, format TEXT,
                  total_seconds REAL, total_tokens_in INT, total_tokens_out INT,
                  started_at, finished_at)
                  -- superseded by pipeline_steps in Plan 2; keep for continuity
```

Notes:
- `run_number`/`seg_number` replace the Redis INCR counters (`run_seq`, `seg_seq`); compute as `MAX(run_number)+1` inside a transaction — single worker, no contention.
- List ordering (`LPUSH` newest-first) becomes `ORDER BY created_at DESC` / `run_number DESC`.
- Artifact files stay on disk; DB stores paths, exactly as Redis does today.
- Add `videos`-style derived data later as needed (QA verdicts live in `asr_qa` for now).

## Migration strategy

1. **Repository layer first.** Create `src/hnfm/db/repo.py` exposing the operations the app actually performs (`get_item`, `save_item`, `list_items(offset, limit)`, `create_run`, `get_segment`, `save_section`, …). Port the ~46 Redis call sites in `hn_utils.py`, `run_utils.py`, `segment_utils.py`, `audio_utils.py`, `tasks.py`, `metrics.py`, `api.py` to call the repo instead of `redis_client` directly. This is the bulk of the diff but it's mechanical.
2. **Postgres in docker-compose** (`postgres:17`, volume, healthcheck) + `DATABASE_URL` env; Alembic init with the v1 schema.
3. **Backfill script** (`scripts/backfill_redis_to_pg.py`): walk Redis keys *and* the `outputs/` disk mirror (disk is the more durable copy — every entity is mirrored as JSON there), upsert into Postgres. Idempotent so it can be re-run.
4. **Cut over** the repo layer to Postgres; keep Redis running as Celery broker only. Delete the RedisInsight compose service or keep it for broker debugging.
5. **Cleanup:** remove dead Redis helpers, drop `hnfm:*` keys once verified.

## Tasks

- [x] Add `sqlalchemy>=2.0`, `alembic`, `psycopg[binary]` to pyproject; add postgres to docker-compose
- [x] `src/hnfm/db/`: engine/session setup, ORM models, Alembic migration 0001
- [x] Repository layer with the full operation set (`src/hnfm/db/repo.py`); tests run on sqlite via `src/hnfm/test/conftest.py`
- [x] Port call sites module-by-module (hn_utils → run_utils → segment_utils → audio_utils → tasks → metrics → api)
- [x] Backfill script (`scripts/backfill_redis_to_pg.py`), ran 2026-07-01: 620 items / 138 runs / 142 segments / 1,461 sections / 1,253 images / 9 metrics — Redis and disk passes cross-validated exactly
- [x] Test suite ported off fakeredis (105 passing); API smoke-tested live against Postgres (items/runs/segments/sections/images/metrics endpoints)
- [ ] Smoke-test a full *generation* pipeline run end-to-end (needs GPU services up)
- [ ] After a comfortable soak period: delete old `hnfm:*` keys from Redis, drop the RedisInsight compose service

## Implementation notes (as built, where it differs from the sketch above)

- Composite **natural PKs** instead of surrogates: `runs(item_id, run)`, `segments(item_id, run, seg)`, `segment_sections(+section)`, `segment_images(+image_index)` — every call site addresses rows by those tuples, and cascading FKs give run/segment deletes for free.
- `id_counters` table with atomic PG upsert replaces Redis INCR (run/seg numbers are allocated before their rows exist, so MAX()+1 wasn't enough).
- `pipeline_metrics` keeps the record dict verbatim in a JSON `data` column (plus `finalized`/timestamps for ordering) so `/api/metrics` is byte-compatible; plan 2 replaces it anyway.
- Legacy `key` strings (`hnfm:seg:…`) are still emitted on API responses for frontend compatibility; they're recomputed in `repo.py`, not stored.
- `HNFM_DB_AUTO_CREATE=true` (dev default) creates tables at startup; Alembic owns schema evolution (`uv run alembic upgrade head`).
- A handful of pre-2026 runs missing newer fields (e.g. `haiku`) fail Pydantic validation and were skipped by the backfill — same behavior as the old code path, which also returned None for them.

## Risks / notes

- `metrics.py` uses a module-global current-record pattern; port it as-is for now — Plan 2 replaces it with `pipeline_steps`.
- Admin "Delete All Data" endpoint (`/api/admin/delete-all-data`) needs a PG implementation (TRUNCATE cascade).
- Frontend contract: keep API response shapes identical so the UI doesn't need to change in this plan.
