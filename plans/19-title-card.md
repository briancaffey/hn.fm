# 19 — The title card

## Why

Every episode opened on `media/hnfm_square.png`: one square picture,
letterboxed into 16:9 and 9:16, crediting tools the pipeline no longer uses.

## What

`video/title_card.py` builds the card as HTML — the five-square orange ramp
over the HNFM wordmark, "presented by brian", a tagline for the episode, and
a credits strip — laid out per aspect ratio, and the Chromium sidecar's new
`/card` endpoint renders it to a PNG at the frame's exact size.

- **Credits are derived.** The language and vision model from the steps the
  story ran, the image model from the configured backend, the voice from
  `TTS_BACKEND`, motion only if the segment has an LTX clip, HyperFrames
  only if its media plan used one.
- **The tagline costs nothing.** The Story Brief's thesis (unless it merely
  repeats the headline), else the run's short description, with reviewer
  framing ("The article announces…") stripped and long lines cut at a
  clause boundary.
- **Logos.** Vendors get a monogram tile. Drop an SVG at
  `video/media/logos/<vendor>.svg` and it is used instead; the repo ships no
  third-party brand files.
- **In the pipeline.** The video step renders `segments/<seg>/title/
  title_<fmt>.png` before the timeline is built; the timeline prefers it and
  falls back to the static square if the sidecar is down.
- **Preview.** `/title-cards` shows the live HTML in all three formats for
  any story, and renders the exact PNG on request.
