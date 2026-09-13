# 20 — HNFM on air: an internet radio station from the pipeline

## The idea in one sentence

Internet radio is one always-running programme, encoded once, that any number
of listeners tune into at a URL. hn.fm already makes the programme material
(episodes, voices, music); what it lacks is a DJ that plays it continuously
and a transmitter that lets people listen.

## Vocabulary (the six words that matter)

| Word | Meaning |
|---|---|
| **Icecast** | The transmitter. A server that takes one audio feed in and fans it out to listeners over plain HTTP. Listeners open a URL and their player just plays. |
| **Mount point** | A station's address on Icecast: `/hnfm.mp3`. One Icecast can host several. |
| **Source client** | Whatever feeds the mount. Could be `ffmpeg`, could be a DJ app. Ours is Liquidsoap. |
| **Liquidsoap** | The DJ. A scripting language for radio: pick the next track, crossfade, fall back to a safe loop if anything fails, encode to MP3, push to Icecast, tell you what is playing. |
| **Encoder / bitrate** | The audio is compressed once, for everyone. 128 kbps MP3 is the radio norm: about 58 MB per listener per hour. |
| **Now-playing metadata** | The title Icecast shows in the listener's player. Liquidsoap sets it per track; Liquidsoap can also call hn.fm back on every track change. |

## How the pieces connect

```
outputs/ (episodes, jingles, music beds)
        │ file paths
        ▼
hn.fm API ──"what's next?"──▶ Liquidsoap ──MP3 128k──▶ Icecast ──HTTP──▶ listeners
 /api/radio/next   ◀──"now playing X"──┘ (callback)   /hnfm.mp3        (browser, VLC, phone)
 /api/radio/events
 /api/radio/status ◀────────── status-json.xsl ─────────┘
```

hn.fm is the programme director. Liquidsoap asks it what to play next and
reports what it played. Icecast just distributes.

## What already exists

- Episode MP3s with intro, loudness-normalised, ID3-tagged (`build_segment_episode`, served at `/api/podcast`).
- Text-to-speech (Magpie, Dia) for any line we write.
- Generated music beds (`audio/music_service.py`, ACE-Step).
- A shared `outputs/` volume that every service sees at the same path, on the Mac and on the cluster.
- The chart, with the pattern for chart-owned services (Postgres, Redis, MinIO behind `<name>.enabled`).

## What to add

| Piece | What it is | Where |
|---|---|---|
| Icecast | `libretime/icecast:2.4.4`, port 8000, mount `/hnfm.mp3`, passwords from the secret | compose service + chart Deployment, `radio.enabled` |
| Liquidsoap | `savonet/liquidsoap:v2.4.5` running `radio/radio.liq`, with `outputs/` mounted | compose service + chart Deployment |
| Programme director | `/api/radio/next`, `/events`, `/now`, `/history`, `/queue`, `/skip`, `/status` | `web/api.py` + `radio/` package |
| Rotation | The clock: what kind of item comes next (episode, station ID, music, "coming up") and which one | `radio/rotation.py`, pure and unit-tested |
| Station voice | A Celery task keeping a bank of ready interstitials: station IDs, time checks, "coming up" lines, music beds | `tasks.py` on the render lane |
| `/radio` page | Player, now playing, history, listeners, queue and skip | frontend |

No Helm chart exists for Icecast or Liquidsoap on Artifact Hub (only an
all-in-one LibreTime chart), so both become chart-owned deployments the way
Postgres already is. AzuraCast bundles all of this but is compose-only and
would sit beside hn.fm rather than inside it.

## Steps

### 1. Hear a stream (30 minutes)

Run Icecast alone and push one episode into it with ffmpeg as the source
client. Open `http://localhost:8000/hnfm.mp3` in a browser. You hear the
episode; `http://localhost:8000/status-json.xsl` shows one listener. That is
the whole protocol.

```yaml
icecast:
  image: libretime/icecast:2.4.4
  environment:
    ICECAST_SOURCE_PASSWORD: ${ICECAST_SOURCE_PASSWORD}
    ICECAST_ADMIN_PASSWORD: ${ICECAST_ADMIN_PASSWORD}
  ports: ["8000:8000"]
```

```sh
ffmpeg -re -i outputs/.../episode.mp3 -c copy -f mp3 \
  icecast://source:$ICECAST_SOURCE_PASSWORD@localhost:8000/hnfm.mp3
```

### 2. Let a DJ run it (half a day)

Replace ffmpeg with Liquidsoap playing every episode MP3 on a loop, with a
crossfade and a safety source, so the stream never stops even if the
playlist is empty.

```liquidsoap
episodes = playlist(mode="randomize", reload=300, "/app/outputs/radio/episodes.m3u")
safety   = single("/app/outputs/radio/safety.mp3")
radio    = fallback(track_sensitive=false, [crossfade(episodes), safety])
output.icecast(%mp3(bitrate=128), host="icecast", port=8000,
  password=getenv("ICECAST_SOURCE_PASSWORD"), mount="/hnfm.mp3",
  name="HNFM", description="Hacker News, on air", radio)
```

### 3. Make hn.fm the programme director (a day)

Liquidsoap stops choosing and asks hn.fm. `request.dynamic` calls
`GET /api/radio/next`, which returns a file path and metadata from the
rotation. `source.on_track` posts to `POST /api/radio/events` so hn.fm knows
what is on air, keeps history, and can show it.

```liquidsoap
def next_item() =
  r = http.get("http://web:8000/api/radio/next")
  j = json.parse(r)
  request.create(j.path, metadata=[("title", j.title), ("hnfm_kind", j.kind)])
end
programme = request.dynamic(next_item)
programme.on_track(fun (m) -> ignore(http.post(
  "http://web:8000/api/radio/events", data=json.stringify(m))))
```

The rotation is a pure function: given the clock and what played recently,
return the next kind and item. Something like: episode, station ID, music,
episode, "coming up", episode, music. Newest episodes weighted up; nothing
repeats within two hours.

### 4. Give the station a voice (a day)

A Celery task keeps a bank of interstitials ready, so the rotation never
waits on a model: twenty station IDs ("You're listening to HNFM"), time
checks, "coming up" lines from the next episodes' titles, and a dozen
60–90 s music beds from ACE-Step. All written to `outputs/radio/`.

### 5. The `/radio` page (a day)

An audio player pointed at the stream, now playing with the episode's card,
the last hour's history, the listener count from Icecast's status JSON, a
queue box to push a story on next, and a skip button. Skip and queue are
API calls; Liquidsoap exposes a tiny HTTP endpoint (`harbor.http.register`)
for skip, and reads the queue through `/api/radio/next`.

### 6. On the cluster (half a day)

`radio.enabled: true` adds the two deployments beside the workers, both
pinned to the outputs node; the ingress routes `/radio/` to Icecast so
listeners use `https://hnfm.lan/radio/hnfm.mp3`; the Liquidsoap script
ships in the backend image (or a ConfigMap) so a change deploys like any
other; passwords come from the Vaultwarden item.

### 7. Tests and inspection (half a day)

- `liquidsoap --check radio/radio.liq` in CI — the script parses and
  type-checks without running.
- Unit tests for the rotation: no repeats within the window, the clock
  order, empty banks degrade to music.
- A smoke test that reads ten seconds of the stream with `ffprobe` and
  asserts a decodable 128 kbps MP3.
- `/api/radio/status` proxies Icecast's status JSON: listeners, uptime,
  current title — on the Services page beside the other backends.
- Every track change is an event row, so the Live page shows the station
  the way it shows the pipeline.

## Opt-in, and out of the way when it is off

The station is off by default at every layer, and "off" means nothing runs,
nothing is exposed and nothing is required — not "running but hidden".

| Layer | Switch | When off |
|---|---|---|
| Mac compose | `docker compose --profile radio up` — Icecast and Liquidsoap sit in the `radio` profile | `docker compose up` never starts them; no ports, no env needed |
| Chart | `radio.enabled: false` (default) in `charts/hnfm/values.yaml` | No Deployments, no Services, no ingress paths, no secret keys demanded. `helm template` output is byte-identical to today |
| Public host | `radio.publicHost: ""` (default) | No second host rule. Set it to `radio.inference.club` and only the listen page and the stream are exposed there; the dashboard never is |
| API | `RADIO_ENABLED=false` (default) | `/api/radio/*` answer 404 with "radio is off"; `/api/radio/status` still answers `{enabled: false}` so the UI knows |
| Beat | The interstitial-bank task is scheduled only when enabled | No TTS or music calls happen for the station |
| Frontend | The `Radio` nav entry appears only when the API says enabled | No dead page in the sidebar |

One `radio/` package holds all of it — rotation, the director endpoints, the
Liquidsoap script, the bank task — so it can be read (or deleted) as a unit.
`radio/README.md` is the operator's page: what the public host exposes (a
listen page and one stream URL), what it never exposes (everything else),
how to turn the station on and off at each layer, and how to check it is
actually off.

## Things to decide early

- **Bitrate.** 128 kbps MP3 everywhere; AAC later if phones matter.
- **Bandwidth.** 58 MB per listener-hour. Ten listeners around the clock is
  14 GB a day out of the cluster.
- **Always on.** Liquidsoap encodes continuously: about a third of a core.
- **Silence.** Liquidsoap's `blank.skip` guards against a broken file
  putting dead air on the station.
- **Rights.** Everything on air is generated here; no licensed music.

## Recommended first move

Steps 1 to 3 in one go. At the end of that you have a station that plays
real episodes chosen by hn.fm, reports what it plays, and can be heard from
any phone on the LAN. The voice, the page and the cluster follow.
