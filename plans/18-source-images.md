# 18 — Source images: the article's own pictures, analysed and usable

## Why

Real images from the linked page are often better at telling the story than
anything we generate: the chart the post is about, the board someone built,
the screenshot of the bug. A v0 of this existed (`scraper/source_images.py`)
but was off by default, bypassed the LLM service (no prompt registry, no
token accounting, wrong model selection), stored a JSON blob nobody could
see, and nothing downstream could actually put a picture in a video.

## Pieces

1. **Collect.** From the page's HTML: `<img>` (largest `srcset` candidate),
   `og:image` / `twitter:image`. Drop chrome by URL hint, SVG/GIF, tiny
   images, and duplicates by content hash. Download with a size cap, keep
   the original dimensions and byte count, downscale anything over
   `SOURCE_IMAGES_MAX_DIM` (1536) and store as JPEG. One row per image in a
   new `source_images` table; the run's legacy JSON column is kept in sync so
   the media planner's listing still works.

2. **Analyse.** One vision call per stored image through `LLMService`
   (`source_image.analyze`, pinned to the omni route like `sequence.plan`),
   structured output: description, kind, subjects, text in the image,
   interest 0-100, whether it is usable in a video, and how. Tokens, model
   and seconds are recorded on the row. The image is sent at 768px, never
   at storage size.

3. **Use.** Before the image builder draws the root frame for each section,
   one text call (`source_image.cast`) matches analysed images to sections:
   which section, which image, and whether to place it as-is or have flux
   re-render it in the take's theme (`/v1/images/edits`, which the sequence
   frames already use). Guardrails: only usable images above an interest
   floor, each image at most once, at most `SOURCE_IMAGES_MAX_USES` sections
   per take. A restyled image is catalogued in `generated_images` with
   `source_image_id` pointing back at its source.

4. **See.** `/source-images`: every collected image with its original and
   stored size, whether it was resized, the analysis, tokens used, and any
   restyles made from it. Collect and restyle on demand from the page.

5. **Wire.** A Celery task on the ingest lane (network, no GPU), dispatched
   from triage alongside the Story Brief so images are ready before a video
   is made; `full_pipeline` reuses what is already collected.

## Not in scope

Video clips from source images (LTX from a photo), cropping to a subject,
and OCR-driven hyperframes. All three become possible once the rows exist.
