# HyperFrames in hn.fm

HyperFrames ([heygen-com/hyperframes](https://github.com/heygen-com/hyperframes),
npm `hyperframes`) is "Write HTML. Render video." — HTML + GSAP compositions
rendered to MP4/WebM via headless Chrome. We use it for **short, beautiful,
animated structured-text accent clips** sprinkled through a video — *not* as
slideware. The agent decides where a hyperframe earns its place; each one shares
the video's design language but the layout/recipe can differ per section.

> **Philosophy.** Leverage what HyperFrames is genuinely great at: kinetic
> typography and clean structured information. Avoid the "powerpoint with little
> animations" trap. Keep it **modular** — if HyperFrames isn't the long-term
> tool, the whole layer can be swapped without touching the rest of the pipeline.

## Architecture

```
celery worker ──HTTP──▶ hyperframes sidecar (Node + Chromium + ffmpeg + hyperframes CLI)
   │  build HTML composition          │  hyperframes render <project> -o out.mp4
   │  (Python, theme-driven)          ▼
   └── shared ./outputs volume ◀── writes the rendered clip
```

- **Sidecar** — `services/hyperframes/` (`Dockerfile` + `server.mjs`). A small
  HTTP service: `POST /render {project, output, format, fps, quality}`. Shares the
  `./outputs` volume at the **same path** (`/app/outputs`) as the worker so
  absolute paths resolve identically on both sides. Reached over the compose
  network as `http://hyperframes:8088` → maps cleanly to a k3s Service later.
- **Generator** (`src/hnfm/hyperframes/`):
  - `design_identity.py` — maps each art-direction theme → palette + tasteful
    **non-banned** font pairing (the skill bans Inter/Roboto/Poppins/Outfit/Syne…)
    with extreme weight contrast. This is the per-take **common design language**.
  - `compositions.py` — recipes (`keypoints`, `bigstat`, `quote`, `compare`) that
    emit a complete self-contained composition `index.html` (stage div +
    `data-composition-id/duration/width/height` + a GSAP timeline on
    `window.__timelines`). Type/spacing scale with canvas size → works for
    16:9 / 1:1 / 9:16.
  - `render_client.py` — calls the sidecar.
  - `produce.py` — `produce_hyperframe_clip(...)`: build → render → clip path.

## A composition, minimally

```html
<div id="stage" data-composition-id="main" data-start="0" data-duration="5"
     data-width="1280" data-height="720"> … </div>
<script>
  const tl = gsap.timeline(); /* entrances */ window.__timelines = {main: tl};
</script>
```

The render reads `data-duration` for length and the `__timelines` entry to drive
animation. Fonts load from Google Fonts at render time (the render env has
network — it already pulls GSAP from a CDN).

## Recipes (the modular palette)

| recipe | content keys | use |
|---|---|---|
| `keypoints` | `kicker, title, points[]` | a titled list of 2-4 takeaways |
| `bigstat` | `stat, label, sub?` | one number that matters |
| `quote` | `quote, attribution?` | a pulled line / claim |
| `compare` | `title?, left{label,text}, right{label,text}` | A-vs-B |

Add a recipe = add one function returning `(body_html, gsap_js)` to `RECIPES`.
The agent (meta-sequencer) picks the recipe and supplies the content; identity
handles the look. Optional `bg_image` puts a generated/source image behind a
scrim so a hyperframe can blend with the surrounding visuals.

## How the agent uses it (flexibility)

The meta-sequencer decides, per section, whether a hyperframe fits and which
recipe + content to use — so each video can use HyperFrames in a new way. The
rendered clip is folded into the timeline exactly like an LTX motion clip
(`video_clip_path` / partial coverage), so no special-casing downstream.

## Config

| env | default | meaning |
|---|---|---|
| `HYPERFRAMES_ENABLED` | `false` | turn the layer on |
| `HYPERFRAMES_BASE_URL` | `http://hyperframes:8088` | sidecar URL |
| `HYPERFRAMES_TIMEOUT_SECONDS` | `600` | render timeout |

Run the sidecar: `docker compose up -d hyperframes`.

## Gotchas / decisions

- **arm64**: `@puppeteer/browsers` only ships `chrome-headless-shell` for x86-64,
  which fails under Rosetta in an arm64 container (`rosetta error: …ld-linux-x86-64`).
  We use the apt **system chromium** (arch-native) instead — portable across
  arm64/amd64. (Trade-off: screenshot capture vs BeginFrame; fine for our clips.)
- Compositions must be **self-contained** (no missing `__VIDEO_SRC__`-style
  placeholders) or the render fails at encode.
- Keep clips short (a few seconds). HyperFrames shines as an accent, not the whole
  video.

## Portability / forward-looking

The sidecar is a standard image with no host coupling — moving to k3s is a
Deployment + Service (NodePort/ClusterIP) and pointing `HYPERFRAMES_BASE_URL` at
it. The generator is pure Python/strings. The layer is isolated behind
`produce_hyperframe_clip` + `video_clip_path`, so swapping HyperFrames for another
renderer later is a localized change.
