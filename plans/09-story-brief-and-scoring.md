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

## Search-to-generate

Plan 4 left this open. Add the Algolia HN search endpoint
(`https://hn.algolia.com/api/v1/search?query=…`) behind `GET /api/hn/search`, wired
to the triage page so "find the story about X and make a video" is one action. The
same Algolia client is what plan 10 uses for comments, so build it here.

## Storage

```sql
ALTER TABLE triage_scores
  ADD COLUMN interest INT, ADD COLUMN producibility INT,
  ADD COLUMN scrape_signals JSONB;

story_briefs (id PK, run_id FK → runs UNIQUE, brief JSONB,
              model TEXT, prompt_version TEXT, created_at TIMESTAMPTZ)
```

## Tasks

- [ ] Scrape step records `scrape_signals` (chars, paragraphs, boilerplate ratio,
      source used, image count, stub/paywall heuristic)
- [ ] Split scoring into `interest` + `producibility`; keep `rank_score` as the blend;
      re-tune weights in `config.yaml`
- [ ] `build_story_brief` task + `story_briefs` table (Alembic) + structured schema
      (uses plan 8's `generate_structured`)
- [ ] Triage page: two meters instead of one; "worth it, needs a better source" bucket
- [ ] `GET /api/hn/search` (Algolia) + search box → triage → generate flow
- [ ] Re-calibrate the rubric against full article content now that Firecrawl is up
      (plan 4 calibrated on titles only, because Firecrawl was down that day)
