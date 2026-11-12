# HNFM on air — the operator's page

An internet radio station made from Hacker News by local models. Read this
before turning it on: what runs, what it costs, what is exposed, how to stop it.

## What it is

```
 format clock ──▶ planner ──▶ writers' room ──▶ booth ──▶ block (files + sheet)
 (code: shows,    (1 call:    (fact sheet,      (voice,        │
  quarters,        stories     draft, rules,     listen-back,  ├──▶ archive (one MP3 + feed)
  slots)           to slots)   editor, rewrite)  mix)          ▼
                                                 director ──"what's next?"──▶ Liquidsoap ──▶ Icecast ──▶ listeners
```

- **The format** (`format.py`) is code. Six shows cover the day, each with
  hosts, a tone, a music palette and a clock of four quarters. A quarter is
  an ordered list of slots; a slot names a segment type. A model cannot
  change the running order.
- **Segments** (`segments.py`) are one spec each: headline, two-hander, The
  Comment Line (callers on a phone line), the bulletin, Show HN desk, Ask
  HN, Front Page Forecast, a mock sponsor read, four short bits, the show
  open, the handoff, and the song of the hour. Add a segment by adding a
  spec and a worked example.
- **The planner** asks the model one thing per block: which story goes in
  which story slot. Picks are checked against each slot's rule and gaps are
  filled by freshness, so a block has the same shape with the model away.
- **The writers' room** writes each piece from a per-story fact sheet (made
  once, kept on disk), checks it with rules, has an editor prompt read it,
  rewrites once, and finally cuts any sentence the rules still reject.
- **The booth** speaks each line, transcribes it back and compares it with
  the script, re-takes a line that came out wrong, puts callers down a
  phone line, ducks a bed under the voice, and checks loudness.
- **The director** serves finished files. With nobody tuned in it plays
  from the library and makes nothing.

## Off by default, at every layer

| Layer | Switch | Off means |
|---|---|---|
| compose | `docker compose --profile radio up -d` | Icecast and Liquidsoap never start |
| API, beat, nav | `RADIO_ENABLED=true` | `/api/radio/*` answer 404; no beat jobs; no menu entry |
| chart | `radio.enabled: true` | no Deployments, Services or ingress paths are rendered |
| public host | `radio.publicHost` | no second host rule at all |

## What it costs, and when

The station makes new programming only when it has a reason to
(`RADIO_PRODUCE`, chart `radio.produce`):

| Mode | Makes a block when |
|---|---|
| `listeners` (default) | someone is tuned in, or was in the last ten minutes; and at the edition hours |
| `always` | a block is running low, around the clock |
| `off` | someone presses "Plan a block" |

Edition hours (`RADIO_EDITION_HOURS`, default `8,13,19`) make one block
each whoever is listening, so the archive has something every day.

Measured on the home cluster (Nemotron 3.5 Lightning, Magpie, ACE-Step):

| | per block (one quarter) |
|---|---|
| Air time | 5 to 9 minutes |
| Wall time to make | 70 to 170 seconds |
| Model calls | 13 to 29 (a fact sheet per new story, two per piece, one plan) |
| Tokens | 19,000 to 47,000, most of it the unchanging system prompt (prefix-cached) |
| Speech | 2.5 to 7 minutes synthesised; a repeated line is read from the cache |
| Music | none per block; beds, tracks and jingles are stocked per show and reused |

Stocking a show's shelf (four beds, six two-minute tracks, two sung
jingles, three station IDs) takes the music model a few minutes, once.

## Turn it on in the cluster

In the environment overlay:

```yaml
radio:
  enabled: true
```

Nothing else. The transmitter's passwords are derived inside the pods from
a secret the release already has (`radio.passwords`). Listeners use
`https://<host>/radio/hnfm.mp3`; the page is `/listen`, the control room
`/radio`, the studio `/studio`.

## Turn it on locally

```sh
# .env
RADIO_ENABLED=true
ICECAST_SOURCE_PASSWORD=<something>
ICECAST_ADMIN_PASSWORD=<something else>

docker compose up -d --no-deps web celery-worker celery-worker-ingest celery-worker-triage celery-beat
docker compose --profile radio up -d
curl -s -X POST localhost:8000/api/radio/bank/fill
curl -s -X POST localhost:8000/api/radio/plan -H 'content-type: application/json' -d '{"force": true}'
```

Listen at `http://localhost:8010/hnfm.mp3`.

## The public host

Setting `radio.publicHost` adds a second hostname that exposes exactly: the
stream (`/radio/`), the listen page (`/listen`, `/_nuxt`), and the read-only
`/api/radio/status`, `/now`, `/history` and `/archive`. Nothing else on that
host resolves. Getting traffic to the cluster from the internet is outside
this chart.

## Changing how it sounds

| To change | Edit |
|---|---|
| The shows, their hours, hosts, music | `format.py` (`SHOWS`) |
| What a quarter hour contains | `format.py` (`_DAY`, `_NIGHT`) |
| What a segment is | `segments.py` |
| How a kind of piece is written | its worked example in `prompts/examples/radio.yaml` — the local model follows the example far more closely than any rule |
| The station's rules for writers | `prompts/radio.write.yaml` (system); enforced by `writers.lint` |
| What the editor checks | `prompts/radio.edit.yaml` |
| The mix | `mix.py` |

Things learned the hard way, all encoded in tests:

- The local model reads its instructions aloud. Labels in the material
  ("The hook:") were read out, so fact sheets carry none, and a sentence
  that recites is cut before the booth.
- It cannot think and return schema-constrained JSON at once, and its
  thinking does not stop on a long prompt. Everything runs with thinking
  off; the writer plans in three short JSON fields before the lines.
- It follows an example over a rule. A test checks that every example
  obeys the station's own rules.
- Speakers and moods are enums in the response schema, so a line cannot be
  given to a host who is not in the piece.

## Inspecting

- `/radio` — now playing, history, blocks with their token cost, stock, skip.
- `/studio` — the station at work, with its running commentary.
- `GET /api/radio/sheets` — each block with every item's words, editor
  scores (`review`), listen-back (`qa`) and the writer's plan.
- `GET /api/radio/archive` and `/api/radio/archive/feed.xml`.
- `GET /api/radio/schedule` — the day and the current quarter's slots.
- `liquidsoap --check src/hnfm/radio/radio.liq` (image
  `savonet/liquidsoap:v2.4.5`) type-checks the DJ's script.
