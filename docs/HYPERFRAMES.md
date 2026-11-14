# Story videos: HyperFrames and Hermes

A story video is one [HyperFrames](https://github.com/heygen-com/hyperframes)
composition: HTML and GSAP rendered to MP4 by headless Chrome. The narration
is the spine. Everything on screen is timed against it.

```
narrated segment ──▶ brief ──▶ pictures + music ──▶ project ──▶ direct ──▶ review ──▶ render
 script, audio,      story.py   pictures.py          kit.py       author.py   sidecar    sidecar
 word timings        (beats)    music.py             cinema.py    ▲
                                ▲                                 └─ Hermes: one card per shot
                                └─ Hermes describes, FLUX draws, ACE-Step plays
```

| Step | Module | What it does |
|---|---|---|
| Brief | `hyperframes/story.py` | Turns a narrated segment into one dictionary. Each section is cut into **beats** of about 4-6 s at its caption phrases; every beat is a scene (a shot) with its text, cues, word times and the section's frames. No model. |
| Pictures | `hyperframes/pictures.py` | Every beat after a section's first gets a picture of its own: Hermes describes it from the line (no style words), FLUX on the 4090 draws it in the story's art direction. Kept by the beat's words, so a remake reuses them. |
| Music | `hyperframes/music.py` | Hermes names the mood in a tag line; ACE-Step on the spark plays an instrumental bed of the video's length, laid at 13% under the voice. |
| Build | `hyperframes/kit.py`, `cinema.py` | Writes the project. Every shot is a picture first: one to three pictures with camera moves (push, pull, pan, rise), cut or dissolved inside the beat, entering through a transition chosen by where the beat sits (whip, iris, dip for a new section; blur swap, push or a cut inside one). Words sit on a paper panel wiped into the picture. |
| Direct | `hyperframes/author.py` | Asks Hermes for a card per shot, checks it, builds the shot from the card, has the renderer review it, sends findings back (three rounds at most). |
| Treatments | `hyperframes/scenes.py` | The eight layouts a card can ask for. Numbers count up to themselves; a `phrase` reveals each word when the narrator says it; a `quote` turns each word from faint to ink as it is said. |
| Run | `hyperframes/videos.py` | The whole job and its status file; what the desk and the API read. |
| Render | `services/hyperframes/` | The sidecar: `POST /render`, `/check`, `/frames`, plus the screenshot endpoints it already had. |

A video is always made. With no agent, or one that fails, scenes keep their
plain version, and the sign-off says how many scenes were directed.

## Who writes what

Code owns the shape and the model supplies the words: the same split the
radio settled on.

The first version asked the agent to write each scene's markup. The local
model returned the worked example with a number of its own ("24 GB" for a
line about 64 GB). So the agent now does a director's job. For each scene it
is sent the line of narration, its spoken cues, the numbers the narrator
says, and what the last few scenes showed. It replies with one JSON card:

```json
{"treatment": "figure", "value": "64 GB", "label": "unified memory", "why": "the line turns on one number"}
```

The treatments: `figure`, `compare`, `bars`, `list`, `steps`, `phrase`,
`quote`, `picture`. `scenes.TREATMENTS` holds their fields and word limits;
that table is also what the agent is shown.

A card is refused, with the reason sent back, when:

- it names a treatment or a field that does not exist;
- it shows a number the narrator does not say in that line;
- its words are not in the narration (more than a third of them);
- a `phrase` is not a run of consecutive words from the line, or ends on a
  word like "the";
- it repeats the previous scene's treatment (asked once);
- the built scene fails the renderer's review (text off the frame, text
  under another element, unreadable contrast, a script error).

Markup written by the agent is still supported (`author.write_scene`, the
page `skill/FREEFORM.md`) for a stronger model: there the agent returns
styles, markup and tween lines, code wraps them, and a list of rules keeps
out network addresses, clocks and randomness.

## Hermes

hn.fm talks to one Hermes profile of its own, `hnfm`, over the agent's HTTP
API (`POST /p/hnfm/v1/runs`, then poll). `hyperframes/hermes.py` is the
whole client.

- **The profile has no tools.** What it is sent is written from pages by
  strangers, and a general-purpose agent profile can usually reach a shell.
  The `hnfm` profile can do nothing but answer.
- **Its key is its own.** The main key is refused on `/p/hnfm`, and the
  profile's key is refused everywhere else. hn.fm holds only the profile's.
- **The model is local.** The profile's only provider is the in-cluster
  LiteLLM gateway's `nemotron-lightning` route: Nemotron 3.5 Lightning on
  the spark box's vLLM. That route has no fallbacks, the profile has no
  fallback providers, and it holds no cloud key. (Until 2026-11-14 it
  called NVIDIA's hosted copy of the same model.)
- **Thinking is off.** With it on, a card takes minutes; off, seconds. The
  provider entry sends `chat_template_kwargs: {enable_thinking: false}`,
  which the gateway passes through to vLLM.
- **The skill travels with the request.** `skill/SKILL.md` is sent as the
  run's instructions. Given a tool to read skills, the model spent its turns
  trying to save its answer as a new skill. The same file is installed in
  Hermes as the `hnfm-video` skill for use by hand.

`deploy/hermes-profile.sh` creates the profile and the secret. Read the
warning at the top of it before running it.

`deploy/check-local-inference.sh` proves the whole chain is local: hn.fm's
service URLs and model routes, the gateway's deployments and fallbacks for
those routes, the profile's provider, model and keys, and one live turn that
must move the spark vLLM's completed-request counter. It exits non-zero on
any failure. `TestLocalOnlyAgent` in the tests reads the profile script so a
cloud provider can't be reintroduced unnoticed.

Each round in a video's `status.json` keeps the Hermes `run_id`, so any
scene can be traced to the agent run that directed it.

### Why Hermes directs and does not render

Hermes answers with a card; hn.fm builds, reviews and renders the scene
itself. Nothing has to come back from the agent but text. The other shape,
an agent with the HyperFrames CLI that renders and uploads the MP4, was
rejected on three counts:

- **Untrusted input.** Scene text comes from pages written by strangers. A
  profile that can run a renderer can be talked into running other things.
- **The model.** Lightning makes a good card in a few seconds. Driving a
  render, checking frames and uploading over many tool turns is where the
  local model is weakest.
- **The file.** The renderer already writes to hn.fm's own volume. Sending
  a large MP4 back across services adds a failure with no benefit.

Settings (chart `hermes:` block):

| env | meaning |
|---|---|
| `HERMES_BASE_URL` | the agent's API root; empty means no agent |
| `HERMES_PROFILE` | the profile to talk to (`hnfm`) |
| `HERMES_API_KEY` | that profile's key, from the `hnfm-hermes` secret |
| `HERMES_TIMEOUT_SECONDS` | per turn, default 300 |

## The project on disk

```
outputs/hyperframes/videos/<item>-<run>-<seg>/
  status.json          state, per-scene record (cards, findings, rounds), timings
  video.mp4            1280x720, 24 fps
  poster.jpg sheet.jpg the title frame, and one frame per scene
  project/
    index.html         host: written by code, never by the agent
    compositions/      intro, scene-NN, outro: one file each
    plain/             the plain version of each scene, to fall back to
    assets/            narration.mp3, stills, the page thumbnail
    brief.json
```

Scenes are sub-compositions: a `<template>` holding a style block, a root
with `data-composition-id`, and one paused GSAP timeline registered under
the same id. `kit.wrap` writes that wrapper for every scene, plain or
directed.

The shared look is in `kit._css`: CSS variables for the theme's palette and
fonts (`--bg --ink --muted --accent --veil --panel --display --body`) and a
few classes (`k-safe`, `k-title`, `k-stat`, `k-card`, ...). The bottom 150
pixels belong to the captions.

## API and desk

- `GET /api/videos`: videos, and narrated stories without one.
- `POST /api/videos {item_id, run, seg, direct}`: make one. `direct: false`
  renders the plain scenes without asking the agent.
- `GET /api/videos/{id}`: status with the per-scene record.
- `GET /api/videos/{id}/video.mp4 | poster.jpg | sheet.jpg`
- `DELETE /api/videos/{id}`

The desk (`/desk`) has all of this in its third column.

## The sidecar

`services/hyperframes/`: Node, Chromium, ffmpeg and the `hyperframes` CLI
behind a small HTTP server. It mounts the outputs volume at the same path
as the workers, so absolute paths mean the same thing on both sides.

- The CLI version is pinned in the Dockerfile, and
  `HYPERFRAMES_NO_UPDATE_CHECK=1` is set. Left alone, the CLI installs a
  newer version of itself the first time it runs, replacing its own files
  under a render in progress.
- Telemetry is off (`HYPERFRAMES_NO_TELEMETRY=1`, `DO_NOT_TRACK=1`).
- Renders, reviews and screenshots share one gate (`SHOT_CONCURRENCY`).
- It uses the system Chromium, which exists for both arm64 and amd64.
  Capture is by screenshot, about 0.8 seconds of render per second of
  video at 1280x720.

## Older use

`compositions.py`, `design_identity.py` and `produce.py` make the short
accent clips the image-based video pipeline can drop between sections
(`recipes`: keypoints, bigstat, quote, compare). They still work and share
the palette table with the story video.
