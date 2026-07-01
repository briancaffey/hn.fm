# Plan 4 — Story scoring & ranked triage

Stop generating videos for duds. Ingest stories cheaply (text only), score their suitability for an engaging video, surface a ranked queue, and only spend GPU time on winners.

## Concept: split the pipeline at the text/GPU boundary

The pipeline already has a natural cheap/expensive split: scrape + clean + summarize + enrich costs a few LLM calls; everything after (TTS, images, LTX, video) is the expensive part. Triage = run the cheap half for every candidate story, score it, stop.

```
queue-top/new → fetch item → scrape+clean+summarize (existing) → TRIAGE SCORE → ranked queue
                                                                       ↓ (you pick, or auto-gen top N)
                                                             full generation pipeline
```

The triage run *is* a normal `ProcessedRun` — when you decide to generate, the script stage starts from the already-scraped content. Nothing is wasted.

## Scoring

### Hard flags (deterministic, before any LLM)
- `paywalled` / `scrape_failed`: content_clean is empty or near-empty vs. HN title-only fallback (the scraper already falls back — today that failure is silent; surface it)
- `too_short`: cleaned content under a threshold
- `dupe`: same URL/domain+title already generated

### LLM suitability score
One structured-output call over title + summary + content excerpt, returning:

```json
{
  "suitability": 0-100,
  "verdict": "great | good | marginal | unsuitable",
  "reasons": ["…2-3 short bullets…"],
  "flags": ["niche_library", "paywalled_partial", "listicle", "no_narrative", …],
  "topics": ["generative-ai", "local-llm", "hardware", …],
  "visual_potential": 0-10,     // can this be *shown*, not just said
  "narrative_potential": 0-10   // is there a story arc / tension / stakes
}
```

Rubric in the prompt: favor concrete stories with stakes, visuals, and broad comprehensibility; penalize obscure-dependency-changelog posts, pure code minutiae, paywalled stubs. Keep the rubric text in a config/DB record so it's editable without a deploy.

### Interest profile (configurable, yours)
- `interest_profile` table (or config section): weighted topic list (e.g. generative-ai +3, local-ai +3, robotics +1, crypto −2) and optional keyword boosts.
- `rank = w1·suitability + w2·topic_match + w3·log(hn_score) + recency_decay`, weights configurable.
- Profile is data, not code — editable in the UI later; supports multiple profiles if you ever want channel-specific feeds.

### Search / targeted generation
- Keep the existing single-item fetch, plus a search box that runs Algolia HN search (`hn.algolia.com/api`) so "find me the story about X and make a video" is one action: search → pick → triage → generate.

## Storage

```sql
triage_scores (id PK, run_id FK → runs UNIQUE,
               suitability INT, verdict TEXT, reasons JSONB, flags JSONB,
               topics JSONB, visual_potential INT, narrative_potential INT,
               interest_match REAL, rank_score REAL,
               model TEXT, scored_at TIMESTAMPTZ)
```

## UI (ties into Plan 3)

- **Triage page:** ranked queue of scored-but-ungenerated stories — rank, title, verdict chip, reasons on hover/expand, flags, topics, one-click **Generate**. Bulk actions: "generate top 5", dismiss.
- Stories table gets the score/verdict column; unsuitable stories visibly deprioritized, never hidden (you said you *can* make a video of anything — this is ordering, not censorship).

## Tasks

- [ ] Hard-flag detection in `process_hn_item_run` (surface scrape-fallback as a flag instead of silent)
- [ ] Triage scoring task + structured-output prompt (rubric as editable config); `triage_scores` table
- [ ] `triage` becomes the default terminus for queue-top/queue-new (cheap half only); explicit action continues to full pipeline
- [ ] Ranking function + interest profile config (seed with generative-AI/local-AI weights)
- [ ] `GET /api/triage?sort=rank` + Triage page + score column on stories table
- [ ] Algolia HN search endpoint + search-to-generate flow
- [ ] Calibrate: score 30–50 recent stories, eyeball the ordering, tune rubric/weights
