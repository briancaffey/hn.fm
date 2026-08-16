# Plan 14 — Output quality gate + evals

**Milestone 7.** Triage scores the *input story*. Nothing scores the *finished video*.
Without that, every prompt change is a guess and every regression is invisible — and
scaling output (plan 15) multiplies whatever the current quality is.

## The golden set

Pick ~15 stories spanning the range you actually publish: a great one, a dull one, a
paywalled stub, a Show HN, a heavy-comments thread, a numbers-heavy paper, a drama
story. Freeze their scraped content and comment trees in the DB so re-runs are
deterministic on the text side and don't depend on Firecrawl being up.

`make eval` re-runs the golden set and prints a scorecard diff against the last run.
This is the loop that makes plans 11–13 measurable rather than vibes.

## What gets scored

Deterministic checks first — they're free and catch the ugly failures:

| Check | Signal |
|---|---|
| Script contract | no markdown, no leaked meta-commentary, well-formed speaker tags |
| Grounding | every section's `provenance` resolves to a brief fact or comment |
| Attribution | comment-derived sections name the user in the spoken text |
| Palette drift | per-frame dominant-colour distance from `palette_lock` |
| Pacing | section duration distribution; no section over N seconds on one image |
| Caption sync | ASR word timings vs. rendered ASS (the ASR QA loop already exists) |
| Speaker balance | not 100% strict alternation; monologue runs present |

Then an LLM/vision jury on the things only judgement catches — script quality, hook
strength, visual variety, style consistency, and the taste rubric already written in
`prompts/media_plan.plan.yaml` ("interesting, educational, funny, unexpected,
original"). Judge each dimension in a separate call; a single "rate this video" call
collapses to a 7 every time.

## Storage and gating

```sql
segment_quality (id PK, segment_id FK UNIQUE, checks JSONB, jury JSONB,
                 overall REAL, gate TEXT,          -- pass|review|fail
                 prompt_versions JSONB, model TEXT, scored_at TIMESTAMPTZ)
```

`prompt_versions` comes from plan 8's registry — it's what lets you attribute a score
change to a specific prompt edit.

Gate policy: **pass** → eligible for auto-publish; **review** → lands in a review queue
in the UI; **fail** → auto-retry once from the failing step (`rerun_step` already
supports this), then park. Thresholds in `config.yaml`.

## Human feedback closes the loop

`story_feedback` (⭐/👍/👎) already exists from plan 4 for *stories*. Add the same for
*finished segments*, and periodically check the jury against your ratings. When they
disagree, the rubric is wrong — fix the rubric, not the score.

## Tasks

- [ ] Golden set: 15 stories with frozen content + comment trees; `make eval`
- [ ] Deterministic check suite (the table above)
- [ ] Per-dimension LLM/vision jury, reusing the taste rubric in the prompt registry
- [ ] `segment_quality` table (Alembic) + gate policy + thresholds in config
- [ ] Scorecard diff output: this run vs. last, per dimension, with prompt versions
- [ ] Segment feedback (⭐/👍/👎) + a "jury vs. Brian" agreement report
- [ ] Review queue page for `gate=review`
