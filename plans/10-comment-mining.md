# Plan 10 — Comment mining with provenance

**Milestone 3.** The HN thread is often better than the article: the correction, the
person who actually built the thing, the benchmark nobody published. Right now none of
it reaches the video.

## Current state

Comments are **not fetched at all**. `HNItem.kids` stores bare comment IDs
(`orm.py:60`), nothing walks them, and `config.yaml`'s `content.include_comments: true`
is dead config that no code reads.

## Fetching

Use Algolia, not Firebase. `https://hn.algolia.com/api/v1/items/{id}` returns the
**entire comment tree nested in one request** — Firebase would need one call per
comment (hundreds per story). The same client is built in plan 9 for search.

Store the tree flattened, preserving structure:

```sql
story_comments (id PK, item_id FK, comment_id BIGINT UNIQUE, parent_id BIGINT,
                hn_user TEXT, text TEXT, created_at TIMESTAMPTZ,
                depth INT, descendant_count INT, sort_rank INT)

comment_insights (id PK, run_id FK, comment_id FK → story_comments,
                  kind TEXT,           -- correction|first_hand|expert_context|
                                       -- counterpoint|data_point|humor|context
                  claim TEXT,          -- the extractable insight, in our words
                  quote TEXT,          -- verbatim span, for on-screen attribution
                  value_score INT,     -- 0-100, does this ADD to understanding
                  confidence INT,      -- how well-supported is it
                  used BOOLEAN)        -- did it make the final script
```

## Selection: cheap filter, then LLM

HN gives no per-comment karma via the API, so rank with what exists before spending
tokens: depth (top-level and one-deep carry most signal), `descendant_count` (replies
are the crowd's own upvote), text length band (very short = reaction, very long =
often the good one), position in the default ordering, and a cheap keyword pass for
first-hand markers ("I work on", "we ran", "author here", "actually,").

Take the top ~25 by that heuristic into one structured LLM call that returns
`comment_insights` rows. Only insights with `value_score` above a configurable
threshold reach the brief.

**The bar is "adds to understanding", not "is highly upvoted."** A funny top comment
that restates the headline is worth less than a quiet reply correcting the article's
central number.

## Getting it into the script — with attribution

Insights land in `story_brief.comment_insights`. Plan 11's writer treats them as
first-class beats, and the **attribution is mandatory and machine-checked**: every
script section carries `provenance` naming article-or-comment, and comment-derived
sections carry `hn_user` + `comment_id`.

Narration should make the shift audible, not bury it:

> "The article stops there — but down in the thread, **jsmith**, who says they ran
> this in production for two years, gives the number the post left out: forty percent."

Style rules for the writer (these go in the prompt, and the script-doctor pass
enforces them):
- Name the source before the claim, never after — the listener must know it's a
  comment *while* hearing it.
- Distinguish *correction* ("a commenter pushes back on that") from *addition*
  ("someone in the thread fills in what's missing") — the two `kind` values already
  encode which.
- Never present a commenter's claim with the same confidence as the article's. The
  brief's `confidence` score maps to hedging language.
- Cap comment-derived beats at ~30% of sections (configurable) so it stays a story,
  not a thread reading.

Because provenance is structured data, plan 13 can also render it: a lower-third card
with the username and the verbatim `quote` while that section plays. That is a
production-quality touch competitors don't have — and it is only possible because the
attribution is a field, not a turn of phrase.

## Tasks

- [ ] Algolia client (shared with plan 9) + `fetch_item_comments` task
- [ ] `story_comments` + `comment_insights` tables (Alembic)
- [ ] Heuristic pre-ranker (depth / descendants / length band / first-hand markers)
- [ ] Structured insight-extraction call → `comment_insights`
- [ ] Merge selected insights into the Story Brief (plan 9)
- [ ] Wire `content.include_comments` + threshold + cap into `config.yaml` (make the
      dead config real)
- [ ] Segment/run UI: show which sections came from comments and from whom
