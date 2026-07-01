#!/usr/bin/env python3
"""Upload all existing media files under outputs/ into the MinIO object store.

Idempotent: objects that already exist with the same size are skipped, so
re-running only uploads what's new or changed. Local files are NOT deleted —
outputs/ remains the pipeline's working directory; reclaim disk manually once
you've verified the store.

Usage:
  uv run python scripts/migrate_media_to_minio.py [--outputs outputs] [--workers 8]

Environment (host defaults):
  S3_ENDPOINT_URL   default http://localhost:9400
  S3_BUCKET         default hnfm-media
  S3_ACCESS_KEY / S3_SECRET_KEY
"""

import argparse
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from threading import Lock

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

from hnfm.storage import object_store  # noqa: E402

MEDIA_EXTENSIONS = {".wav", ".mp3", ".png", ".jpg", ".jpeg", ".webp", ".mp4", ".webm", ".vtt", ".ass"}

stats = {"uploaded": 0, "skipped": 0, "failed": 0, "bytes": 0}
_stats_lock = Lock()


def _bump(key, n=1):
    with _stats_lock:
        stats[key] += n


def _remote_size(client, bucket, key):
    try:
        return client.head_object(Bucket=bucket, Key=key)["ContentLength"]
    except Exception:
        return None


def upload_one(path: Path, outputs_root: str):
    rel_key = str(path.relative_to(outputs_root)).replace(os.sep, "/")
    client = object_store.get_client()
    bucket = object_store.bucket_name()
    size = path.stat().st_size

    if _remote_size(client, bucket, rel_key) == size:
        _bump("skipped")
        return

    try:
        client.upload_file(
            str(path),
            bucket,
            rel_key,
            ExtraArgs={"ContentType": object_store.content_type_for(str(path))},
        )
        _bump("uploaded")
        _bump("bytes", size)
    except Exception as e:
        print(f"  ⚠️  {rel_key}: {e}")
        _bump("failed")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--outputs", default=os.getenv("OUTPUTS_ROOT", "outputs"))
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()

    outputs_root = os.path.abspath(args.outputs)
    files = [
        p
        for p in Path(outputs_root).rglob("*")
        if p.is_file() and p.suffix.lower() in MEDIA_EXTENSIONS
    ]
    total_bytes = sum(p.stat().st_size for p in files)
    print(f"{len(files)} media files ({total_bytes / 1e9:.2f} GB) under {outputs_root}")
    print(f"target: {object_store._endpoint()} bucket={object_store.bucket_name()}")

    object_store.ensure_bucket()

    done = 0
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = [pool.submit(upload_one, p, outputs_root) for p in files]
        for _ in as_completed(futures):
            done += 1
            if done % 500 == 0:
                print(f"  … {done}/{len(files)}")

    print(
        f"\ndone: uploaded={stats['uploaded']} "
        f"({stats['bytes'] / 1e9:.2f} GB), skipped={stats['skipped']}, "
        f"failed={stats['failed']}"
    )
    if stats["failed"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
