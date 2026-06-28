# hn.fm — Revival Notes & Improvement Roadmap

_Status as of 2026-06-28. hn.fm was revived against the **inference-club k3s
cluster** and is producing finished HN → video segments again._

---

## 1. What was done to revive it

The project was dead on this machine: `.env` pointed at LAN IPs/services that no
longer exist, and the original AI stack (Dia TTS, NVIDIA Studio Voice NIM,
WhisperX) is gone or scaled to zero. It was re-pointed at the services that are
**actually running** in the `inference-club` namespace, with no changes to that
production namespace (cluster services are ClusterIP-only, so they're reached via
`kubectl port-forward` + `host.docker.internal`, except LiteLLM which has a
NodePort).

| Stage | Was | Now |
|---|---|---|
| LLM (summary, script, prompts) | gpt-oss-20b @ LM Studio LAN IP | **LiteLLM gateway** → `nemotron-omni` (NodePort 30400). Fixed two bugs: client hardcoded `api_key="not-needed"` (LiteLLM 401'd → garbage fallback script); and nemotron is a reasoning model returning null `content` → added `chat_template_kwargs.enable_thinking=false` + `reasoning_content` fallback. |
| TTS | Dia `/generate` (single model voices both hosts) | **Magpie TTS** (`/v1/audio/synthesize`). New dual-backend client: splits `[S1]/[S2]` and voices two distinct speakers (Mia + Jason), concatenates WAVs. **Both backends supported** via `TTS_BACKEND=magpie|dia`. |
| Audio enhance | Studio Voice NIM (gRPC) | **no-op stub** (`STUDIO_VOICE_ENABLED=false`); Magpie output is already clean 22 kHz WAV. |
| ASR / subtitles | WhisperX `/process-audio` | not deployed → **fast-fail (1 attempt)**, falls back to coarse VTT. |
| Image | InvokeAI exported-workflow (hardcoded node/model keys) | **flux2-klein** OpenAI-style `/v1/images/generations` (rewrote the NIM backend). Avoids InvokeAI's fragile per-install workflow keys. |
| Scrape | Firecrawl **/v0/scrape** (404 on current Firecrawl) | **/v1/scrape**, and made **non-fatal**: on failure, degrade to the HN title/text so paywalled/blocked URLs don't kill the pipeline. |
| Outputs | `OUTPUTS_DIR`/`OUTPUTS_ROOT` split (cwd-dependent) | both pinned to `/app/outputs`. |
| Config plumbing | several env vars not passed into containers | added `TTS_BACKEND`, `ASR_MAX_ATTEMPTS`, `MAGPIE_*`, `STUDIO_VOICE_ENABLED`, `OUTPUTS_*` to compose. |

**Result:** the full 5-stage `full_pipeline` runs in ~3 min/segment (scrape →
LLM script → magpie audio → flux images → ffmpeg video). Verified multiple
finished `segment.mp4`s serving through the app's own `/api/video/...` endpoint,
with the `/segments` gallery and segment pages rendering.

### How to run it now
```sh
# 1. tunnels to the ClusterIP AI services (LiteLLM is direct via NodePort)
kubectl -n inference-club port-forward svc/magpie-tts 9000:9000 &
kubectl -n inference-club port-forward svc/firecrawl  3002:3002 &
kubectl -n inference-club port-forward svc/flux2-klein 8500:8000 &
# 2. backend + 3. frontend
docker compose up -d redis web celery-worker flower
cd frontend && yarn && yarn dev   # needs `yarn add better-sqlite3` once
# 4. queue + run
curl -XPOST 'localhost:8000/api/hn/queue-top?limit=10'
curl -XPOST localhost:8000/api/hn/single-task-pipeline -d '{"item_id":<id>}'
```

---

## 2. Shortcomings found (the honest list)

**Reliability**
- **Redis is the only datastore** — all item/run/segment metadata lives in Redis
  (disk JSON is a partial, never-reloaded mirror). Lose the volume = lose the
  catalog. No Postgres, no migrations.
- **Hard failures abort the whole pipeline** (scrape was one; now patched). Each
  stage should degrade, not crash.
- **Silent LLM fallback** still exists elsewhere: a broken LLM yields a
  "successful" one-line garbage script instead of failing loudly.
- **Polling UI with fixed 30–60s timeouts** — long image/video steps routinely
  exceed them, so the UI shows "timed out" on success.

**Automation / agentic (currently thin)**
- Pipeline is **linear and hardcoded**; the "agentic" angle is unrealized.
- **No batch/queue UX** — you trigger one item at a time by hand.
- **No quality loop** — no scoring/regeneration of bad scripts/images/audio.
- `celery-beat` runs with an **empty schedule** (does nothing).

**Code smells**
- Two env-var styles; `llm_service` bypasses `config.yaml`; `prompts_template.json` is dead.
- Section/image "Save" buttons are **no-ops** (`// TODO: Implement API endpoint`).
- InvokeAI hardcoded workflow node IDs; manual thread+queue timeout wrappers that can leak.
- Route duplication (`run-[runId].vue` vs `run/[runId]/`), malformed `<span v-else">` templates.

---

## 3. Roadmap

### Phase 0 — Stabilize (small, high-value)
- [ ] Make **every** external stage degrade gracefully (scrape ✓; do the same for LLM, image, TTS) — never abort `full_pipeline`.
- [ ] Replace silent LLM fallback with a real error + retry; surface failures in the UI.
- [ ] Fix the no-op Save buttons + the polling timeouts (use SSE/websocket or backoff).
- [ ] Delete dead config/routes; unify env handling on `config.yaml`.

### Phase 1 — Quality of the videos
- [ ] **Real subtitles**: wire ASR to Magpie's `/v1/audio/transcriptions` (already available) for word-level timing → animated captions instead of coarse VTT.
- [ ] **Better visuals**: per-section style consistency (seed/character continuity), Ken Burns motion on stills, optional **LTX-2 generative video** clips (`ltx2` is running) for hero shots.
- [ ] **Voice direction**: use Magpie's emotion variants (Mia.Happy/Calm, Jason.Neutral…) driven by script sentiment; tune turn gaps.
- [ ] **Music bed**: `acestep` (running) for intro/outro/background music.
- [ ] **Script craft**: better host personas, hooks, pacing; length controls.

### Phase 2 — Agentic, automated production
- [ ] **Editor agent**: an LLM agent that reads the scraped article + HN comments and *plans* the segment (angle, beats, which images, which b-roll), then drives the stages as tools — instead of the fixed linear chain. This is the "use agentic AI to the utmost" piece.
- [ ] **Critic/QA agent**: score each script/image/audio; auto-regenerate below threshold (loop until good).
- [ ] **Auto-curation**: `celery-beat` job that pulls top HN hourly, ranks by "video-worthiness", and produces a daily batch unattended.
- [ ] **Batch UX** in the app: select N stories → produce all; progress dashboard.

### Phase 3 — Reliability & scale
- [ ] **Postgres** for durable item/run/segment state (Redis stays as broker only); reload-from-disk recovery.
- [ ] **Service discovery / health-gated stages** — detect which AI backends are up and route accordingly (so a scaled-to-zero `dia` automatically falls back to `magpie`, etc.). The dual-backend TTS is the template.
- [ ] **Parallelism**: image/TTS sections are independent — fan them out (Celery group) instead of serial; cut per-video time substantially.
- [ ] **Observability**: pipeline traces to Phoenix/Langfuse (already in the cluster); per-stage timing + cost.

### Phase 4 — inference.club adoption (the end goal, not yet)
- [ ] Treat hn.fm as an **inference.club workflow**: each stage maps to an existing platform capability (LLM, TTS, image, video, music) routed through the agent/LiteLLM — no bespoke service URLs.
- [ ] Move outputs to **GCS media** + the platform's media pipeline; segments become shareable inference.club content (visibility/collections).
- [ ] Multi-tenant: any user feeds a URL (not just HN) → video, using their own keys/quota and the platform's job/queue system.
- [ ] The dual-backend, health-gated, degrade-gracefully patterns built here are exactly what makes it portable into the platform.

---

## 4. Backend mapping (reference)

| hn.fm need | inference-club service | endpoint | reached via |
|---|---|---|---|
| LLM | `nemotron-omni` (or lmstudio/*) | LiteLLM `/v1/chat/completions` | NodePort `192.168.5.173:30400` (Bearer = LiteLLM master key) |
| TTS | `magpie-tts` (or `dia` when up) | `/v1/audio/synthesize` | `port-forward 9000` → `host.docker.internal:9000` |
| Image | `flux2-klein` | `/v1/images/generations` | `port-forward 8500` |
| Scrape | `firecrawl` | `/v1/scrape` | `port-forward 3002` |
| (future) ASR | `magpie-tts` or `nemotron-asr` | `/v1/audio/transcriptions` / `:8105` | port-forward |
| (future) video | `ltx2` | `:8023` | port-forward |
| (future) music | `acestep` | `:8015` | port-forward |
