# Plan 9 — Two-axis scoring + the Story Brief

**Milestone 2.** Plan 4 shipped a working triage score. This splits it into the two
axes you actually reason about, and turns the cheap text half of the pipeline into a
single structured artifact — the **Story Brief** — that every downstream stage reads.

## Two axes, not one

Today `suitability` blends "is this interesting?" with "can we make something of it?".
Those come apart constantly: a fascinating paywalled story scores low for the wrong
reason, and a thin but well-scraped blog post scores high for the wrong reason.

| Axis | Question | Driven by |
|---|---|---|
| `interest` 0–100 | Is this intrinsically worth an audience's attention? | novelty, stakes, surprise, breadth of appeal, HN signal (score/comment velocity), your interest profile |
| `producibility` 0–100 | Given what we actually retrieved, can we build a good video? | scrape completeness, factual density, structure (has an arc / has numbers / has entities), visual affordance, comment substance |

Rank stays a weighted blend, but both scores are stored and both are visible in the
UI. A high-interest / low-producibility story is a *fix the scrape* signal, not a
reject — surface it as its own bucket ("worth it, needs a better source").

### Producibility needs real scrape signal
`hard_flags()` currently knows only `scrape_fallback` and `len < 400`. Extend the
scrape step to record: char count, extracted-paragraph count, boilerplate ratio,
whether Firecrawl or the Wayback fallback answered, image count, code-block ratio,
and whether the page looks like a stub/paywall interstitial. These are deterministic
inputs to `producibility` — cheaper and more reliable than asking the LLM to guess.

## The Story Brief

One structured artifact per run, produced by the cheap half, consumed by plans 11
(script) and 12/13 (visuals). Replaces the current situation where the script prompt
gets `content_clean` + `summary` and the image prompt gets `run_summary` + one line —
neither has the whole picture.

```jsonc
{
  "thesis": "one sentence: what this story actually is",
  "why_now": "the reason it's on the front page today",
  "stakes": "who is affected and how much",
  "angle": "the framing that makes this a video rather than a summary",
  "key_facts": [ { "claim": "...", "source": "article|comment",
                   "quote": "...", "comment_id": 12345, "hn_user": "..." } ],
  "entities":  [ { "name": "...", "kind": "person|org|product|place", "role": "..." } ],
  "numbers":   [ { "value": "40%", "of": "...", "context": "..." } ],
  "tension":   "the disagreement, risk, or open question",
  "comment_insights": [ ... ],          // populated by plan 10
  "visual_affordances": ["what can literally be shown", ...],
  "unknowns": ["what the source does NOT establish"],
  "interest": 0-100, "producibility": 0-100, "verdict": "great|good|marginal|unsuitable"
}
```

`unknowns` is load-bearing: it is what the fact-checker in plan 11 uses to refuse to
let the writer invent (the UCSD fabrication in plan 8's evidence is exactly this
failure).

## Search-to-generate — CUT (2026-08-21)

Originally scoped as an Algolia-backed `GET /api/hn/search`. **Dropped: this project
takes no third-party data dependencies.**

The `hn.algolia.com/api/v1` endpoint is genuinely free and keyless (verified: a
credential-free request returns 200, and no API key exists in this repo), but it is
a third-party service outside the cluster, rate-limited, and free on terms its owner
controls. Brian's call is that HN data comes from HN.

The official Firebase API has **no search endpoint at all**, so there is no
equivalent to build — search-to-generate is removed from the plan rather than
reimplemented. Fetching a story by ID already works, which covers the same need with
one extra step.

## Storage

```sql
ALTER TABLE triage_scores
  ADD COLUMN interest INT, ADD COLUMN producibility INT,
  ADD COLUMN scrape_signals JSONB;

story_briefs (id PK, run_id FK → runs UNIQUE, brief JSONB,
              model TEXT, prompt_version TEXT, created_at TIMESTAMPTZ)
```

## Tasks

- [x] Scrape step records `scrape_signals` (`content/scrape_signals.py`: chars,
      words, paragraphs, boilerplate ratio, code ratio, source used, image/link/
      heading counts, stub-or-paywall heuristic). `ScrapedContent.source` now
      distinguishes a live Firecrawl fetch from a Wayback copy
- [x] Split scoring into `interest` + `producibility` (prompt v3, schema-enforced);
      `producibility_ceiling()` caps the model's optimism from the signals; weights
      and bucket thresholds in `config.yaml`
- [x] `build_story_brief` task + `story_briefs` table (Alembic 0005) + schema
- [x] Triage page: two meters, "needs source" chip, and a bucket filter
      (`GET /api/triage?bucket=needs_better_source`)
- [x] ~~`GET /api/hn/search` (Algolia) + search box~~ — **cut**, see above
- [ ] **Re-calibrate the rubric against full article content** — BLOCKED, see below

### Design decisions taken during implementation

**Producibility multiplies rather than adds** in `rank_score`. An additive weight
lets a high interest score paper over an unusable scrape; a multiplier makes an
unbuildable story sink regardless. It is scaled to `[floor, 1]` (floor 0.15) so such
stories sink but never vanish — ordering, not censorship.

**The ceiling is deterministic and overrides the model.** The signals are ground
truth about what we hold; the score is an opinion about it. A capped story is also
demoted out of `great`/`good`, because a verdict that survives the cap would still
pull it into auto-generation later (plan 15).

**Interest is never capped.** The story is still good — that is the entire point of
splitting the axes, and it is what makes the "needs better source" bucket meaningful.

**The brief is two LLM calls, not one.** Framing is editorial judgement and wants a
higher temperature; evidence extraction wants a low one and a verbatim-quote rule.
One call cannot run at two temperatures. It also degrades better — either half can
fail and the brief is still usable, recorded as `partial`.

**Every article-sourced `key_fact` has its quote verified against the article** and
is dropped if absent (whitespace- and smart-quote-insensitive). Everything downstream
treats `key_facts` as ground truth, so a fabricated quote is the most dangerous thing
this stage can emit. Cheap to check, so checked.

### Verified

Offline end-to-end (real code, real DB, mocked LLM), with the model claiming
`producibility=85, verdict=great` for both stories:

| | 214-char stub (the fabrication case) | real 7.7k article |
|---|---|---|
| stored producibility | **20** (capped) | 85 |
| verdict | **marginal** (demoted) | great |
| flags | `too_short`, `needs_better_source` | — |
| rank | **37.1** | **101.2** |

219 tests pass. Migration 0005 verified up and down.

## Blocked — needs the inference cluster

The `inference-club` box (192.168.5.173) was unreachable throughout this work, so
nothing below could run against a live model:

- **Rubric re-calibration** (the remaining task). Needs real scores over a spread of
  real stories to tune `interest`/`producibility` weights and the bucket thresholds.
- **Brief quality**: prompts `brief.framing` / `brief.evidence` are unexercised. In
  particular `unknowns` — the field plan 11's fact-checker depends on — has never
  been generated. Expect to iterate on that prompt once it can run.
- **One-call vs two-call**: the split was chosen on the temperature argument above,
  which stands on its own, but the schema-adherence half of the case is untested.
