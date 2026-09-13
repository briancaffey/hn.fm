# HNFM on air — the operator's page

The internet radio station built from the pipeline (plans/20). Read this
before turning it on; it says what runs, what is exposed, and how to stop it.

## What it is, in one picture

```
outputs/  (episode MP3s, the bank)
    │ file paths
    ▼
hn.fm API ──"what's next?"──▶ Liquidsoap ──MP3 128k──▶ Icecast ──HTTP──▶ listeners
 /api/radio/next   ◀──"now playing"────┘              /radio/hnfm.mp3
 /api/radio/events
```

- **Icecast** is the transmitter. One feed in, any number of listeners out.
- **Liquidsoap** is the DJ. It asks the API what to play next, crossfades,
  never lets the stream drop (safety bed, then silence), pushes one MP3 to
  Icecast, and reports every track change. Its script is `radio.liq` here:
  compose bind-mounts it; the chart's init container fetches it from
  `GET /api/radio/script` at pod start, so it deploys with the backend.
- **The producer** (`producer.py`) plans a block of programming — about
  thirty minutes — with one structured call to the local model. The
  station's sound is quick: six to nine **briefs** (thirty seconds on a
  story that just landed on /new — headline, then the two or three things
  worth knowing, written by the Punchline prompt and read by a host over a
  quiet bed), short music beds between every two or three items, a station
  ID every few items, a time check near the top, and at most one deep-dive
  episode in the middle. It never repeats a story or episode that aired in
  the last twelve hours or is already on the belt. If the model is down, a
  deterministic fallback plans the same shape.
- **Voices** (`voice.py`): Mia, Jason, Sofia, Leo, Aria and Ray on Magpie,
  each with moods the server lists (calm is the house mood; neutral and sad
  when a line wants them), plus Dia. Spoken items end in a beat of silence
  and the DJ's crossfade is short, so nothing steps on the last word.
- **The director** (`director.py`) serves the block one item at a time,
  honours the queue ("play this next"), keeps history, and asks for the
  next block when the current one runs low.
- **The bank** (`bank.py`) keeps station IDs and music beds ready, and
  voices the lines the producer wrote for each block, so the air never
  waits on TTS or the music model.

## Off by default, at every layer

| Layer | Switch | Off means |
|---|---|---|
| compose | `docker compose --profile radio up -d` | `docker compose up` never starts Icecast or Liquidsoap |
| API, beat, nav | `RADIO_ENABLED=true` | `/api/radio/*` answer 404; no beat jobs; no menu entry. `/api/radio/status` says `{enabled: false}` |
| chart | `radio.enabled: true` | no Deployments, Services or ingress paths are rendered |
| public host | `radio.publicHost: radio.example.com` | no second host rule at all |

Both switches are needed locally: the profile starts the containers, the
env flag makes the API answer them. With the flag on and the profile off,
Liquidsoap is simply not running and the page says the transmitter is down.

## Turn it on locally

```sh
# .env
RADIO_ENABLED=true
ICECAST_SOURCE_PASSWORD=<something>
ICECAST_ADMIN_PASSWORD=<something else>

docker compose up -d --no-deps web celery-worker celery-worker-ingest celery-worker-triage celery-beat   # re-read .env
docker compose --profile radio up -d                                                                     # icecast + liquidsoap
curl -s -X POST localhost:8000/api/radio/bank/fill                                                       # first station IDs and beds
```

Listen at `http://localhost:8010/hnfm.mp3`. The control room is `/radio`
in the dashboard; the public page is `/listen`.

## Turn it on in the cluster

In the home-lab values overlay:

```yaml
radio:
  enabled: true
  publicHost: ""            # or radio.inference.club, see below
```

and add `ICECAST_SOURCE_PASSWORD` and `ICECAST_ADMIN_PASSWORD` to the
Vaultwarden item (and to `externalSecret.keys`). Listeners use
`https://hnfm.lan/radio/hnfm.mp3`.

## The public host

Setting `radio.publicHost` adds a second hostname rule that exposes exactly:

- `/radio/` — the stream (Icecast)
- `/listen` and `/_nuxt` — the public listen page (player, now playing, recent)
- `/api/radio/status`, `/api/radio/now`, `/api/radio/history` — read-only

Nothing else on that host resolves. The dashboard, every other API route,
the queue and skip controls stay on the LAN host. Getting traffic to the
cluster from the internet (tunnel, TLS, bandwidth) is outside this chart.

## How to check it is actually off

```sh
docker compose ps | grep -c "icecast\|liquidsoap"      # 0
curl -s localhost:8000/api/radio/status                # {"enabled": false}
curl -s -o /dev/null -w "%{http_code}\n" localhost:8000/api/radio/next   # 404
helm template hnfm charts/hnfm | grep -c icecast       # 0
```

## Costs

- One LLM call per block, measured at about 1,900 tokens in and 700 out
  for a thirty-minute block — a few thousand tokens an hour, on the local
  model, and about thirty-five seconds of its time.
- TTS for the block's lines (a handful of short sentences) and, now and
  then, a 60 s music bed from ACE-Step to keep the bank stocked.
- Liquidsoap encodes continuously: about a third of a core.
- 58 MB per listener-hour of bandwidth.

## Inspecting

- `/radio` — now playing, last three hours, the planned blocks with their
  token cost, listener count, queue, skip.
- `GET /api/radio/sheets` — the blocks, with `source: llm | fallback`.
- `GET /api/radio/history` — every track change the DJ reported.
- Services page — Icecast and Liquidsoap health, listed only when on.
- `liquidsoap --check src/hnfm/radio/radio.liq` (via the
  `savonet/liquidsoap:v2.4.5` image) type-checks the script without
  running it; CI should run it.
