# hn.fm

Hacker News, turned into things to listen to and watch by models that run at home: narrated episodes, a daily digest for an e-reader, and an internet radio station.

## What it does

1. **Fetches** new and front-page stories and scrapes what they link to.
2. **Scores** each one for interest and for how well it can be produced. Most go no further.
3. **Researches** the ones worth making: a brief with the thesis, the facts, the numbers and what the comment thread added.
4. **Makes** things from the briefs:
   - **Episodes**: a two-host script, voiced, illustrated and cut to video.
   - **Digests**: written editions, sent to an e-reader on a schedule.
   - **HNFM**: a radio station with six shows, a cast of ten and its own sound effects. It makes episodes: a whole hour of a show with chapters, a transcript, cover art and a video. See [`src/hnfm/radio/README.md`](src/hnfm/radio/README.md).

All three are run from one page, **the desk** (`/desk`): what was last made, a button to make the next one, and the switch for each. The public pages are under `/listen`.

Every step is recorded with its inputs and can be looked at and run again.

## Models

All local, reached over HTTP. Nothing calls a paid API.

| Job | Model |
|---|---|
| Writing, scoring, planning | Nemotron 3.5 Lightning (vLLM), through a LiteLLM gateway |
| Speech | Magpie TTS |
| Listening (subtitles, and checking spoken lines) | Nemotron ASR |
| Pictures | FLUX.3 Klein |
| Music | ACE-Step 1.5 |
| Video clips | LTX 2.5 (optional; skipped when its server is not running) |
| Scraping | Firecrawl |

## Running it

**On a cluster.** `charts/hnfm` is a Helm chart with in-chart Postgres, Redis and an S3-compatible store. [`deploy/README.md`](deploy/README.md) describes the GitOps loop: a push builds three images and a deploy controller rolls them out.

**On one machine.** `docker compose up` starts the API, the workers and the datastores; `cd frontend && yarn && yarn dev` starts the dashboard. Point the service URLs in `.env` at your model servers (`.env.example` lists them).

## Where things are

| Path | What |
|---|---|
| `src/hnfm/web` | The API and the Celery tasks |
| `src/hnfm/content` | Scoring, briefs, scripts, the model client and the prompt registry |
| `src/hnfm/radio` | The radio station |
| `src/hnfm/digest` | The written editions |
| `prompts/` | Every prompt, versioned. `prompts/examples/` holds the worked examples the radio's writers follow |
| `evals/` | Evaluation rounds and their reports |
| `frontend/` | The dashboard, the listen page and the studio (Nuxt) |
| `charts/hnfm`, `deploy/` | The chart and the deploy notes |
| `plans/` | Design notes from before the issue tracker; current work is in GitHub issues |

## Tests

```sh
uv run pytest src/hnfm/test
```

No test calls a model or runs ffmpeg.

## Output layout

Generated artifacts live under `outputs/`, in exactly three places:

| path | contents |
|---|---|
| `outputs/hn/item/<id>/runs/<n>/segments/<n>/` | audio, images, video and the segment record for one take |
| `outputs/digests/` | rendered digests (`.html`, `.epub`) |
| `outputs/reports/` | analysis reports |

Nothing else belongs at the top level. An older layout wrote one
slug-named directory per story (`outputs/holga_120_degree_wide_pinhole_camera_68ae49`);
70 of those had accumulated to 1.7 GB with nothing reading them, and they were
removed. If a top-level directory appears here that is not one of the three
above, it is a leak.

Object-store keys mirror this tree, so the same paths address a local file and
an object in the store.

The radio keeps its own files under `outputs/radio/`: stock in `bank/`, each
block's pieces in `blocks/<sheet>/`, finished blocks in `archive/<date>/`, fact
sheets in `sheets/`, spoken lines in `cache/voice/`, sound effects in `fx/`
and cover art in `art/`.
