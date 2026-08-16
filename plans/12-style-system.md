# Plan 12 — Style Bible + per-story Style Contract

**Milestone 5.** Two goals that pull in opposite directions and need different
mechanisms: **wide variety across stories**, **strict consistency within one story**.

## Current state

`content/art_direction.py` holds 12 `Theme` dataclasses. Each is a name plus one
string of style words, appended verbatim to every scene prompt in a take. Selection is
`pick_theme(seed=item_id + run*131 + seg*977)` — a hash. Consistency within a take is
"the same sentence is appended each time", which controls medium and palette *words*
but not palette *values*, recurring subjects, or composition language.

That got the project off one-look-fits-all, and it's the right skeleton. It needs
depth on both axes.

## Variety: the Style Bible

Move styles out of Python into `styles/*.yaml` — data, loadable and editable without a
deploy (same principle as the triage rubric). Target 40+ entries. Each is richer than
a style string:

```yaml
key: risograph
name: Risograph Print
medium: "risograph print illustration, visible halftone grain, slight misregistration"
palette:
  values: ["#FF48B0", "#0078BF", "#FFE800", "#F4F1E8"]   # actual hex, locked
  description: "two-three fluorescent spot colours on off-white stock"
lighting: "flat, no modelling; colour separation does the work"
camera: "front-on, poster-like; minimal perspective"
texture: "paper tooth, ink bleed at edges"
motion_character: "hard cuts, no easing — print doesn't drift"    # for LTX/hyperframes
typography: { display: "Grotesk, tight tracking", body: "mono" }  # for hyperframes
music_mood: "playful, analog, mid-tempo"                          # for ACE-Step
negative: "photorealism, gradients, lens flare, 3d render"
fit_tags: [zine, indie, community, playful, design, protest]
avoid_tags: [enterprise, security-incident, obituary]
```

The extra fields matter because they reach stages the current `Theme` can't: LTX
motion character, HyperFrames typography, and the ACE-Step music mood all currently
ignore the visual theme entirely, which is why a video's music and kinetic text feel
unrelated to its images.

**Building 40+ styles is itself an agentic task** — generate candidates against a
diversity brief (era, medium, palette temperature, energy), render a 3-image probe of
each on a fixed test prompt, and keep the ones that are visually distinct from
everything already in the bible. Do this once, review by eye, commit the survivors.

## Consistency: the Style Contract

Replace the hash pick with a **casting agent**: given the Story Brief (plan 9), choose
the style whose `fit_tags` suit this story's tone and subject, and reject on
`avoid_tags` (no claymation for a security breach). Then it emits a per-story
**Style Contract** — the thing that actually creates within-story consistency:

```jsonc
{
  "style_key": "risograph",
  "palette_lock": ["#FF48B0", "#0078BF", "#FFE800"],
  "recurring_motif": "a hand-drawn circuit trace that runs through every frame",
  "subject_sheet": [
    { "id": "protagonist", "description": "a lone engineer in a red jacket, ..." },
    { "id": "the_system",  "description": "the datacenter rendered as a paper cathedral" }
  ],
  "composition_rules": ["negative space on the left third", "horizon always low"],
  "forbidden": ["photorealistic faces", "literal screenshots of code"]
}
```

Every image prompt in the story inherits the contract. A `subject_sheet` entry is
what lets shot 7 say "the same engineer from shot 2" and actually get her — the
missing piece today, where each `generate_image_prompt_v1` call is independent and has
no memory of any previous shot.

Keep multi-take comparison working: takes of the same story get *different* style
keys (that's the point of the compare page), but each take gets its own internally
consistent contract.

## Storage

```sql
ALTER TABLE segments
  ADD COLUMN style_contract JSONB;      -- style_theme/style_theme_name stay for compat
```

## Tasks

- [ ] `styles/*.yaml` schema + loader; port the existing 12 themes as the first entries
- [ ] Agentic style-generation run to reach 40+; probe-render and cull near-duplicates
- [ ] Casting agent: brief → style choice (`fit_tags`/`avoid_tags`), replacing the hash
- [ ] Style Contract generation (palette lock, motif, subject sheet, composition rules)
- [ ] Thread the contract into image prompts, LTX motion, HyperFrames typography, and
      ACE-Step music mood — all four currently ignore it
- [ ] `style_contract` column (Alembic) + surface it on the segment page
- [ ] Style gallery page: every style rendered on the same probe prompt, side by side
