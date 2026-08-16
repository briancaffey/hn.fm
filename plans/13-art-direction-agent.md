# Plan 13 — Art-direction agent: whole-story shot list + a rendered-frame critic

**Milestone 6.** Give the visuals a director that sees the whole script at once, and a
critic that looks at what actually came out of the image model.

## Current state

Two things already work well and stay: the **meta-sequencer** (`content/
meta_sequencer.py`) choosing per-section between image sequence / LTX motion / kinetic
text with guardrails and a critic, and the **vision-driven sequence planner**
(`content/sequence_planner.py`) that looks at a rendered root frame and plans edits
that advance the content rather than swapping the lighting.

The gap is one level up. `generate_image_prompt_v1` is called **once per section, in a
loop, with no memory** — it sees `line_text`, `run_summary`, a cycling `shot_hint` from
an 8-item list, and nothing else. So:

- Shot 7 cannot reference shot 2. Continuity exists *within* a sequence (the planner
  gives us that) but never *across* the story.
- Shot variety is a round-robin over 8 hints, not a composed visual rhythm.
- Nothing ever looks at the generated image to ask whether it's any good.

## The storyboard agent

One call over the **whole structured script + the Style Contract**, emitting a shot
list with cross-references:

```jsonc
{ "shots": [
  { "index": 4,
    "subject_ref": "protagonist",            // from the contract's subject_sheet
    "callback_to": 1,                        // reuse shot 1's framing for the rhyme
    "shot": "extreme macro detail",
    "scene": "her hand on the cold-aisle door handle, frost on the metal",
    "why": "the turn lands here — go tight before the reveal",
    "continuity": ["red jacket", "low horizon", "circuit-trace motif in the frost"] }
] }
```

Two rules the agent is held to, because they're what separates a storyboard from a
list of pictures:
- **Visual rhythm**: no two adjacent shots at the same distance; establish before
  detail; the payoff beat gets the widest or tightest frame in the piece.
- **Motif discipline**: the contract's `recurring_motif` appears in most shots, always
  differently.

`visual_intent` from the structured script (plan 11) is the input that makes this
possible — the director is told what each beat needs to *show*, not asked to infer it.

## The frame critic

After each root frame renders, a vision call grades it (the vision path already exists
in `sequence_planner`, reuse the client):

```jsonc
{ "prompt_fidelity": 0-10, "style_match": 0-10, "composition": 0-10,
  "artifacts": ["extra fingers", "unreadable text"], "verdict": "keep|repair|reroll",
  "repair_hint": "..." }
```

Below threshold → one repair pass (image-to-image with the hint) → one reroll →
accept the best. Budget-capped per segment so a bad story can't consume the GPU.
Every attempt lands in `pipeline_steps`, so the compare UI can show what was rejected.

Add a cheap deterministic check alongside the LLM: extract the dominant colours of each
frame and measure distance from `palette_lock`. A frame that drifts off-palette is
detectable without a model call, and it's the most common way within-story consistency
visibly breaks.

## Tasks

- [ ] `content/storyboard.py` — whole-script shot list with `subject_ref`,
      `callback_to`, `continuity`, honouring the Style Contract
- [ ] Replace the per-section `generate_image_prompt_v1` loop with shot-list execution
      (keep the function as the single-shot fallback)
- [ ] Retire the 8-item `SHOTS` round-robin in `build_segment_images`
- [ ] Frame critic (vision) + repair/reroll loop with a per-segment attempt budget
- [ ] Palette-distance check against `palette_lock`; flag drift on the step record
- [ ] Feed the shot list to the meta-sequencer so its template choice knows what the
      visuals will actually be (today it plans blind of the imagery)
- [ ] Compare UI: show rejected attempts and the critic's reasons
