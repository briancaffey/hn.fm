# Plan 5 — Voice onboarding (YouTube → DIA voice sample)

Make creating a new cloned voice a two-minute job: paste a YouTube link + timestamps (or upload a file), and the system downloads, trims, transcribes with speaker labels, formats the DIA sample pair, and gives you a test generation to approve.

## What exists

- DIA (`services/dia/server.py`) already does voice cloning: `POST /generate` takes `audio_prompt` (WAV) + `audio_prompt_text` (its exact transcript with `[S1]`/`[S2]` tags) and conditions generation on it. It returns the seed used via `x-seed`.
- Voices are just directories: `voices/<name>/sample.wav` (mono 44.1 kHz) + `sample.txt` (tagged transcript). Loaded by `tts_api_service.py:191-201`. Creation is 100% manual today.
- WhisperX service (`services/whisperx/server.py`, port 8042) already provides transcription **with word timestamps and speaker diarization** — exactly the ASR needed to build the transcript automatically.
- No YouTube tooling exists yet.

## Pipeline

```
input (YouTube URL + start/end, or uploaded file + optional start/end)
  → yt-dlp: download bestaudio
  → ffmpeg: trim to [start,end], convert to mono 44.1 kHz WAV
  → WhisperX /process-audio: segments + speakers (min/max speakers from user hint, default 1-2)
  → speaker mapping: first distinct speaker → [S1], second → [S2] (UI lets you swap/rename)
  → format sample.txt: "[S1] …exact transcribed text… [S2] …"
  → write voices/<name>/{sample.wav, sample.txt}
  → test generation: POST DIA /generate with a fixed test script using the new sample
  → user listens, approves (keep) or tweaks (re-trim, edit transcript, retry)
```

Quality guardrails baked in:
- **Length:** DIA audio prompts work best around 5–15 s. Warn outside that range; hard-cap ~20 s.
- **Transcript fidelity matters more than anything** — the transcript must be verbatim (DIA prepends it to the script). Show the transcript for manual correction before saving; keep filler words.
- Normalize loudness (`ffmpeg loudnorm`) and strip leading/trailing silence.
- Single-speaker samples get everything tagged `[S1]`; a note in the UI that two-speaker samples give DIA a distinct S2 voice.

## Backend

- New module `src/hnfm/voices/` + endpoints:
  - `POST /api/voices` `{name, source: {youtube_url|upload}, start_s, end_s, speakers_hint}` → Celery task runs the pipeline above → returns draft voice with transcript + audio for review
  - `PUT /api/voices/{name}` — edit transcript / re-trim / re-transcribe
  - `POST /api/voices/{name}/test` — DIA test generation, returns audio (+ seed)
  - `GET /api/voices`, `DELETE /api/voices/{name}`
- `voices` table (name, source_url, start_s, end_s, transcript, num_speakers, sample_path, status draft|ready, created_at) — files remain the source of truth for DIA; DB is the catalog.
- Dependencies: add `yt-dlp` to pyproject (Python API, no shelling out needed); ffmpeg already in the image.

## UI (ties into Plan 3)

- **Voices page:** card per voice (name, duration, transcript preview, play sample, play latest test gen, set-as-default), "New voice" flow: URL + start/end fields → progress → waveform + editable transcript + speaker tags → test → save.
- Voice picker on the generation trigger (story detail / triage page): choose backend (magpie/dia) + voice per generation instead of env-var-only (`TTS_DEFAULT_VOICE` today). Persist choice on the Segment so the X-ray shows which voice made it.

## Tasks

- [ ] `yt-dlp` + ffmpeg trim/normalize helpers in `src/hnfm/voices/extract.py`
- [ ] WhisperX integration → tagged-transcript builder with speaker mapping
- [ ] Voice CRUD endpoints + Celery task + `voices` table (catalog only)
- [ ] DIA test-generation endpoint (fixed test script, returns audio + seed)
- [ ] Voices page UI: create flow, transcript editor, test playback
- [ ] Per-generation voice selection (API param + Segment field + UI picker); deprecate env-only selection
- [ ] Containerize/deploy DIA properly (Dockerfile exists uncommitted in `services/dia/` — finish CI + add to port-forwards or compose so the voice flow works end-to-end)
