# Prompt evolution log

Each entry: what was measured, what changed, why, and what the numbers did.
Metrics come from `src/hnfm/evals` and are computed without a model, so a
change is judged by whether the number moved.

Stories under test (chosen to be deliberately unalike, so a fix that only
works on one kind of story shows up as not generalising):

| item | subject |
|---|---|
| 49582867 | Nvidia Personal AI Router — consumer hardware |
| 49582874 | What Linux does when you `malloc()` — systems internals |
| 49582793 | ZZZ backup page / wiki outage — web history, no hardware at all |

---

## Round 1 — baseline

| metric | value | reading |
|---|---|---|
| speaker switch rate | 0.456 | healthy — the run-length enforcement is holding |
| repeated openings | 0.000 | no formulaic section starts |
| script lexical diversity | 0.748 | good |
| length variation | 0.224 | sections vary in length |
| **visual_intent overlap** | **0.028** | the writer's declared subjects are highly varied |
| **rendered scene overlap** | **0.327** | …and the art director throws that away |

**The finding.** Image variety does not fail where it looked like it failed.
The script's `visual_intent` values are near-perfectly distinct (0.028
pairwise overlap). The collapse happens one step later, in
`generate_image_prompt_v1`: 0.035 in, **0.327 out** — a ten-fold loss. Sampled
output shows why: a laptop on a walnut desk, a smartphone, two mirrored walnut
desks, a laptop on a kitchen island. Every beat becomes the same domestic tech
tableau whatever the intent said.

**Cause.** Two lines I wrote myself:

1. `prompts/image.scene.yaml` says *"keep the same world, cast and place where
   the story has not moved on"*. That was added for cross-shot continuity and
   it works — it also instructs the model to repeat the subject.
2. `prior_scenes` passes the **full text** of previous scenes. Shown a wall of
   walnut-desk prose and told to keep the world, the model reasonably
   continues it.

The shot list is not the problem: `shot_coverage` is 0.64, so camera treatment
genuinely varies. Angle was never what made the images feel same-y — subject
was.

---

## Round 2 — the art-director prompt (`image.scene` v3 → v5)

### Calibrating the metric first

Raw pairwise overlap cannot be read on its own. Scenes drawn from three
*different stories* — definitionally unrelated — still score **0.161**, because
cinematic prose shares a lot of unavoidable vocabulary. That is the floor, not
zero. Identical scenes score 1.000. So the honest reading is *excess over
floor*, and a second metric was added for the symptom actually being reported:
`tableau_rate`, the share of frames containing a desk, laptop, screen, monitor,
keyboard, phone or office.

### Changes

1. **Split continuity in two.** v3 said *"keep the same world, cast and place
   where the story has not moved on"*. That instruction — mine, added for
   cross-shot continuity — was telling the model to repeat the subject. v4
   holds era, palette, scale and indoors/outdoors constant while requiring the
   subject to change.
2. **Pass prior SUBJECTS, not prior scenes.** Shown the full text of previous
   prompts, the model continued the prose. It now receives a bare noun list
   framed as things to avoid.
3. **A rotating visual register**, binding per beat: human scale, material,
   architectural, mechanism, landscape, trace. Camera angle was never the
   problem — `shot_coverage` was already 0.64 while subjects repeated — so this
   varies *what is in frame* rather than where the camera stands. Rotated
   rather than random, so consecutive beats differ structurally.
4. **Demoted the spoken line** from the top of the template to context at the
   bottom, with an explicit note that a line mentioning a device does not mean
   the picture is of a device. The line was anchoring every frame on hardware.

### Result

| metric | v3 baseline | v4 | v5 |
|---|---|---|---|
| tableau_rate | 0.413 | 0.319 | **0.315** |
| lexical diversity | 0.460 | 0.495 | **0.502** |
| excess overlap | 0.157 | 0.156 | **0.150** |
| distinct head nouns | 0.891 | 0.958 | 0.917 |

**tableau_rate fell 24%** — roughly one frame in four stopped being another
picture of a desk. Vocabulary diversity rose 9%.

**What did not move: excess overlap, 0.157 → 0.150.** Worth stating plainly.
That metric is dominated by prose style rather than subject, so it was the
wrong instrument for this failure; `tableau_rate` is the one that tracks what a
viewer notices. Keeping both, because a future change that games one will
show up in the other.

Qualitatively, a take that previously ran laptop-on-desk / thumb-on-phone /
two-desks / laptop-on-island now runs hands-and-laptop / workbench with circuit
fragments / two attic desks / **a mechanic beneath a diesel engine** / **a brass
ball on a marble incline** / **glass vials on a lab bench**. Registers are being
obeyed.

---

## Round 3 — the script prompt (`script.write` v1 → v5, plus a guard)

Baseline script metrics were mostly healthy — switch rate 0.456, no repeated
openings, lexical diversity 0.748 — so the target was the two visible defects:
one story rendered a rich article as **six** sections against a requested
10-16, and section lengths clustered.

### What was tried, and what each attempt did

| attempt | change | sections (3 stories) | length variation |
|---|---|---|---|
| v1 baseline | — | 16 / **6** / 9 | 0.224 |
| v3 | numeric rhythm quota ("two under ten words, two over twenty-five") + firmer section floor | 14 / 15 / 8 | **0.139** |
| v4 | rhythm reframed as function-driven, softer floor | 10 / 12 / **3** | 0.146 |
| v5 | v3's floor + the plain one-line rhythm note | 14 / 14 / 6 | 0.165 |

Two honest negatives worth keeping:

- **The numeric rhythm quota backfired.** Asking for "at least two sections
  under ten words and two over twenty-five" produced *fewer* of both — short
  sections went from 2/0/0 to 0/0/0. Giving a model numeric targets made it
  aim for the middle.
- **Softening the section floor collapsed one script to three sections.** The
  firmer wording was doing real work.

### The actual fix was not a prompt

Across four samples of the same story with the same prompt, section count came
back as 9, 8, 3 and 6. It is unstable run to run, and no wording made it
reliable — the same lesson as speaker runs and teaser grounding. So the floor
is enforced in code: a script under eight sections built from more than 3,000
characters of source is retried once, and the fuller of the two is kept.

| metric | before | after |
|---|---|---|
| **minimum sections across the three stories** | **6** | **12** |
| visual_intent overlap | 0.028 | 0.021 |
| intent lexical diversity | 0.796 | 0.817 |

**Pattern across three rounds:** where output is *structurally* wrong —
speaker runs, teaser subject, section count — prompt wording is unreliable and
a deterministic guard is not. Where output is a matter of *content* — which
subject to draw — the prompt is the only lever, and it works.

---

## Report

The whole cycle is written up in `evals/reports/prompt-evolution.pdf`, built by
`evals/build_report.py` straight from the round JSON in `outputs/evals/` — so
regenerating it after a new round picks the new numbers up rather than needing
the prose edited. Rendered with headless chromium in the `hyperframes`
container, which is the only image in the stack that already carries one. The
same PDF is served at `/prompt-evolution.pdf` and linked from **Evolution** in
the UI.
