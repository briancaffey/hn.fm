# Plan 7 — MinIO object store for media artifacts

Make MinIO (S3-compatible, in docker-compose) the store of record for all
generated media — audio sections, combined audio, images, sequence frames,
LTX/hyperframe clips, final videos, subtitles.

## Architecture

- **Local `outputs/` stays the pipeline's working directory.** ffmpeg, WAV
  stitching, and image-to-image editing all need local files; generation is
  unchanged.
- **Artifacts publish to MinIO at the existing save choke-points** (non-fatal —
  the store being down can never fail a render):
  - `audio_utils.save_section_meta` → section WAV
  - `audio_utils.update_segment_audio_status` → combined WAV
  - `segment_utils.save_segment_image` → root frame + sequence frames + motion clip
  - `segment_utils.update_segment_video_fields` → video + subtitles
- **Object keys mirror the outputs/ tree** (`hn/item/{id}/runs/{run}/…`),
  derived from local paths by `storage/object_store.key_for_path` — no DB
  schema change needed.
- **Serving prefers MinIO**: `/api/audio|images|video/...` redirect (307) to
  presigned URLs — MinIO handles Range requests for video scrubbing. Subtitles
  (`captions.vtt`) are proxied through the API instead, because `<track>`
  requires same-origin delivery. Local file remains the fallback.
- Presigned URLs are signed against `S3_PUBLIC_URL` (browser-reachable,
  default `http://localhost:9400`), while the app talks to `S3_ENDPOINT_URL`
  (`http://minio:9000` in-network).

## Configuration

| Env | Default | Meaning |
|-----|---------|---------|
| `S3_ENDPOINT_URL` | `http://minio:9000` (compose) / `http://localhost:9400` (host) | app-side endpoint |
| `S3_PUBLIC_URL` | `http://localhost:9400` | browser-side endpoint for presigned URLs |
| `S3_BUCKET` | `hnfm-media` | bucket |
| `S3_ACCESS_KEY` / `S3_SECRET_KEY` | `hnfm` / `hnfm-minio-secret` | credentials (also MinIO root user) |
| `MEDIA_UPLOAD_ENABLED` | `true` (`false` in tests) | master switch for publish + MinIO-first serving |

Host ports: **9400** (S3 API), **9401** (web console) — 9000/9090/9100 were
taken by cluster tunnels and other local services.

## Tasks

- [x] MinIO service in docker-compose (volume, healthcheck, app `depends_on`)
- [x] `src/hnfm/storage/object_store.py` (publish, presign, proxy-stream, key derivation)
- [x] Publish hooks at the four save choke-points
- [x] API media endpoints: MinIO-first with local fallback
- [x] `scripts/migrate_media_to_minio.py` (idempotent, size-skip, concurrent) + initial migration run
- [x] Initial migration completed 2026-07-01: all 5,911 media files (9.4 GB), 0 failures. Serving verified end-to-end: video/image/audio via presigned 307 redirects, `.vtt` proxied same-origin. (First attempt crashed Docker — host disk was 99% full; ~20 GB of caches were cleared first.)
- [ ] Once verified over a few generations: reclaim local disk (delete old media under `outputs/`, keeping the JSON mirrors), or add a retention script — host disk is at 97% again with the media now duplicated, so do this soon

## Notes

- Data JSONs (item/processed/segment/meta/ASR) intentionally stay on disk +
  Postgres; MinIO holds *media*.
- Backups: the `minio_data` docker volume now holds the media of record once
  local copies are reclaimed.
