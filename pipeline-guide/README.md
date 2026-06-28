# Pipeline Guide

Shareable, on-brand documentation of how hn.fm turns a Hacker News link into an
AI-directed video — the inference services, the Celery orchestration, the
prompts, the agentic "director," and a real worked example with performance.

## Artifacts

| File | Format | Use |
|---|---|---|
| `pipeline.pdf` | A4 PDF (8 pages) | the full deep-dive — share / print |
| `pipeline.html` | HTML | the PDF source (edit this, then re-render) |
| `assets/card_wide.png` | 1200×630 | Twitter / LinkedIn / OG link preview |
| `assets/card_square.png` | 1080×1080 | Instagram — the 6-step flow |
| `assets/card_director.png` | 1080×1080 | Instagram — the 3 ways a section is told |
| `cards.html` | HTML | source for the social cards (`?c=wide\|sq\|perf`) |

## How it was made (so we can regenerate)

The doc is **self-documenting** — the last PDF page lists this process too.

1. **Prompts** — summarized from source (`src/hnfm/utils/segment_utils.py`,
   `src/hnfm/content/meta_sequencer.py`).
2. **Worked example** — pulled a real recent generation from Redis (script,
   image prompts, the director's `meta_plan`, hyperframe content, source-image
   descriptions).
3. **Performance** — pulled real per-stage time + token counts from a metrics
   record (`GET /api/metrics`, also live at `/observability`).
4. **Authoring** — a single on-brand HTML file; all diagrams are CSS/flex (no
   external chart libs). Brand: Space Grotesk + IBM Plex Mono, hn.fm orange
   `#f97316`, stage colors matching the dashboard.
5. **Rendering** — headless Chromium inside the HyperFrames render sidecar
   (already in the compose stack), via the shared `outputs/` volume:

```bash
# from repo root, with `docker compose up -d hyperframes`
mkdir -p outputs/_guide && cp pipeline-guide/pipeline.html pipeline-guide/cards.html outputs/_guide/

# PDF (wait for web fonts via virtual-time-budget)
docker compose exec -T hyperframes chromium --headless=new --no-sandbox --disable-gpu \
  --virtual-time-budget=6000 --no-pdf-header-footer \
  --print-to-pdf=/app/outputs/_guide/pipeline.pdf file:///app/outputs/_guide/pipeline.html
cp outputs/_guide/pipeline.pdf pipeline-guide/pipeline.pdf

# social cards (one per ?c=)
for c in wide:1200,630 sq:1080,1080 perf:1080,1080; do
  name=${c%%:*}; size=${c##*:}
  docker compose exec -T hyperframes chromium --headless=new --no-sandbox --disable-gpu \
    --virtual-time-budget=5000 --hide-scrollbars --window-size=$size \
    --screenshot=/app/outputs/_guide/card_$name.png "file:///app/outputs/_guide/cards.html?c=$name"
done
cp outputs/_guide/card_*.png pipeline-guide/assets/
```

To update: edit `pipeline.html` / `cards.html`, refresh the example data + metrics
if the pipeline changed, then re-render with the commands above.
