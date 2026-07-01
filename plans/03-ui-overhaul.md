# Plan 3 — UI overhaul

Make the UI a dense, full-screen mission control: see everything flowing in from HN at a glance with generation status per story, drill into a story → generation → step X-ray without hunting, and trigger/edit/regenerate from wherever you are.

## Current pain (from the code)

- Story list (`frontend/app/pages/hn/items.vue`) is a plain 7-column table with no sorting/filtering, no generation info (you can't see whether a story has runs/videos without clicking in), and wastes horizontal space. TanStack Vue Table is installed but unused.
- Navigation is deep and blind: items → item → run → segment are four separate pages; the segment page (1,350 lines) holds everything interesting but you only find out what exists after clicking through.
- Video player constrained to `max-w-4xl`; tables `container mx-auto`; no sidebar, no dense mode.
- Status is polled ad hoc (1–2s refresh loops per action) with no unified "what is the pipeline doing right now" surface.

## Design

### Layout shell
- Full-width app shell with a slim left sidebar (Stories, Segments, Triage [Plan 4], Voices [Plan 5], Observability, Services, Admin) replacing the top nav. Content area uses the entire viewport width.
- Dark-mode-first density: smaller row heights, tabular-nums, sticky table headers.

### Stories page (the home screen)
- TanStack-powered table, one row per HN item, full width. Columns: score, title (+domain), age, comments, **triage score & flags** (Plan 4), **runs count**, **segments count**, **videos count**, latest status (e.g. "video ready 2h ago" / "images failed"), quick actions (open, generate, open latest video).
- Server-side: one new endpoint `GET /api/stories?sort=&filter=&offset=` returning items joined with generation aggregates (needs Postgres — a single GROUP BY; this is the main reason the list can't be good today).
- Column sorting, text search, and filters (has video / failed / un-generated / by tag).

### Story detail
- Single page with everything: story header + summary/enrichment, then a **generations table** (one row per segment across all runs: run/seg, theme, format, audio/images/video status chips, QA verdict, duration, created, watch link). No separate run page needed for browsing — runs become a grouping within this table.
- Inline video player at full available width, artifact strip (images thumbnails) per generation row expandable in place.

### Generation X-ray (per segment)
- Rebuild the segment page around the **step timeline** from Plan 2: a vertical timeline grouped by stage, each step showing status, duration, tokens, and a preview of its output (script text, audio player, image thumb, clip).
- Expand step → inputs as an editable form (prompt/params/seed) → **"Re-run from here"**; stale downstream steps get amber badges + "rebuild stale" button.
- Keep the existing per-image/per-section editors — they become step-editors on the same surface instead of separate expandable sections.
- A right-hand summary rail: script, combined audio, final video, metrics rollup.

### Live activity
- A small "now running" indicator in the sidebar fed by a `GET /api/activity` endpoint (running steps from `pipeline_steps` where status='running' + Celery queue depth). Replaces scattered polling with one poll (or SSE later).

## Tasks

- [x] App shell: fixed sidebar (Stories/Segments/Observability/Services/Admin + dark-mode toggle + activity light), full-width content
- [x] `GET /api/stories` with generation aggregates (runs/segments/videos counts, latest activity; server-side sort/filter/search/pagination); mission-control table on `/hn/items` with sortable headers, filter chips, debounced search, queue buttons, per-row Generate
- [x] **Reusable pagination pattern**: `usePaginatedFetch` composable (pagination + sort + debounced search + URL query sync + stale-response guard, standard `{items, pagination:{total}}` contract) feeding the shared `Pagination.vue` bar — the one way tables fetch lists
- [x] Story detail: `GET /api/hn/items/{id}/generations` (segments flattened across runs + run summaries) → one dense generations table with status chips, QA badges, expandable inline video + thumbnail strip, X-ray links; Gallery tab (compare-page parity)
- [x] X-ray timeline shipped in plan 2 (StepTimeline on the segment page)
- [x] Activity indicator: `GET /api/activity` (running + recent steps) polled by one sidebar component (visibility-aware)
- [x] Observability: per-render breakdown links to the segment X-ray + story page
- [ ] Segment page rebuild around the timeline with right-hand summary rail (nice-to-have; X-Ray section exists)
- [ ] Kill remaining per-action polling loops on the segment page in favor of the activity feed
- [ ] `/api/metrics` on steps + retire metrics.py (still recording in parallel; carry-over)
- [ ] Old `/hn/item/[id]/run/[runId]` page is now redundant with the generations table — remove after a soak

Status: **core done 2026-07-01** — shell, stories mission control, story detail, activity, gallery. Leftovers above are cleanups, not blockers.
