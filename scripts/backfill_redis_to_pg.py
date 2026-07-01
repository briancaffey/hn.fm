#!/usr/bin/env python3
"""Backfill the Postgres data store from Redis and the outputs/ disk mirror.

Idempotent: safe to re-run. Order of precedence per entity:
  1. Redis (most up-to-date at cutover time), if reachable
  2. outputs/ disk mirror (item.json / processed.json / segment.json /
     audio/sections/*/meta.json / images/*/meta.json)

Metrics only ever lived in Redis, so those come from Redis alone.
After entity import, id_counters are bumped to MAX(run)/MAX(seg) so newly
allocated numbers don't collide with existing ones.

Usage:
  uv run python scripts/backfill_redis_to_pg.py [--outputs outputs] [--no-redis]

Environment:
  DATABASE_URL              target Postgres (default localhost hnfm/hnfm)
  REDIS_HOST/PORT/DB        source Redis (default localhost:6379/0)
"""

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

from hnfm.db import ensure_schema  # noqa: E402
from hnfm.db import repo  # noqa: E402
from hnfm.web.models import HNItem, ProcessedRun, Segment, SegmentImage, SegmentSection  # noqa: E402

stats = {}


def bump(key, n=1):
    stats[key] = stats.get(key, 0) + n


def _load_json(path: Path):
    if not path.exists():
        return None  # partial render — normal, skip quietly
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"  ⚠️  unreadable JSON {path}: {e}")
        return None


# ---------------------------------------------------------------------------
# Disk walkers
# ---------------------------------------------------------------------------

def backfill_from_disk(outputs_root: Path):
    items_root = outputs_root / "hn" / "item"
    if not items_root.is_dir():
        print(f"no disk outputs at {items_root}, skipping disk pass")
        return

    for item_dir in sorted(items_root.iterdir()):
        if not item_dir.is_dir() or not item_dir.name.isdigit():
            continue
        item_id = int(item_dir.name)

        data = _load_json(item_dir / "item.json")
        if data:
            try:
                repo.upsert_item(HNItem(**data))
                bump("items")
            except Exception as e:
                print(f"  ⚠️  item {item_id}: {e}")

        runs_dir = item_dir / "runs"
        if not runs_dir.is_dir():
            continue
        for run_dir in sorted(runs_dir.iterdir()):
            if not run_dir.is_dir() or not run_dir.name.isdigit():
                continue
            run = int(run_dir.name)

            pr_data = _load_json(run_dir / "processed.json")
            if pr_data:
                try:
                    repo.save_run(ProcessedRun(**pr_data))
                    bump("runs")
                except Exception as e:
                    print(f"  ⚠️  run {item_id}:{run}: {e}")
            else:
                continue  # segments need the run row (FK)

            src_data = _load_json(run_dir / "source_images" / "source_images.json")
            if src_data:
                try:
                    repo.set_run_source_images(item_id, run, src_data)
                    bump("source_images")
                except Exception as e:
                    print(f"  ⚠️  source_images {item_id}:{run}: {e}")

            segs_dir = run_dir / "segments"
            if not segs_dir.is_dir():
                continue
            for seg_dir in sorted(segs_dir.iterdir()):
                if not seg_dir.is_dir() or not seg_dir.name.isdigit():
                    continue
                seg = int(seg_dir.name)

                seg_data = _load_json(seg_dir / "segment.json")
                if not seg_data:
                    continue
                try:
                    repo.save_segment(Segment(**seg_data))
                    bump("segments")
                except Exception as e:
                    print(f"  ⚠️  segment {item_id}:{run}:{seg}: {e}")
                    continue

                sections_dir = seg_dir / "audio" / "sections"
                if sections_dir.is_dir():
                    for sec_dir in sorted(sections_dir.iterdir()):
                        meta = _load_json(sec_dir / "meta.json")
                        if meta:
                            try:
                                repo.save_section(SegmentSection(**meta))
                                bump("sections")
                            except Exception as e:
                                print(f"  ⚠️  section {sec_dir}: {e}")

                images_dir = seg_dir / "images"
                if images_dir.is_dir():
                    for img_dir in sorted(images_dir.iterdir()):
                        meta = _load_json(img_dir / "meta.json")
                        if meta:
                            try:
                                repo.save_image(SegmentImage(**meta))
                                bump("images")
                            except Exception as e:
                                print(f"  ⚠️  image {img_dir}: {e}")


# ---------------------------------------------------------------------------
# Redis walkers
# ---------------------------------------------------------------------------

def _scan(rc, pattern):
    cursor = 0
    while True:
        cursor, keys = rc.scan(cursor, match=pattern, count=200)
        for k in keys:
            yield k.decode() if isinstance(k, bytes) else k
        if cursor == 0:
            break


def backfill_from_redis(rc):
    # Items: hnfm:item:{id} (exactly 3 segments). Only GET string-shaped keys —
    # `:runs` lists and `:run_seq` counters raise WRONGTYPE / don't apply.
    for key in _scan(rc, "hnfm:item:*"):
        parts = key.split(":")
        is_item = len(parts) == 3 and parts[2].isdigit()
        is_run = len(parts) == 5 and parts[3] == "run" and parts[4].isdigit()
        is_src = len(parts) == 6 and parts[3] == "run" and parts[5] == "source_images"
        if not (is_item or is_run or is_src):
            continue
        try:
            raw = rc.get(key)
            if not raw:
                continue
            if is_item:
                repo.upsert_item(HNItem(**json.loads(raw)))
                bump("items(redis)")
            elif is_run:
                repo.save_run(ProcessedRun(**json.loads(raw)))
                bump("runs(redis)")
            else:
                repo.set_run_source_images(int(parts[2]), int(parts[4]), json.loads(raw))
                bump("source_images(redis)")
        except Exception as e:
            print(f"  ⚠️  {key}: {e}")

    # Segments / sections / images: hnfm:seg:{item}:{run}:{seg}[...]
    seg_keys, sec_keys, img_keys = [], [], []
    for key in _scan(rc, "hnfm:seg:*"):
        parts = key.split(":")
        if any(p in ("list", "seq") for p in parts):
            continue
        if len(parts) == 5:
            seg_keys.append(key)
        elif len(parts) == 7 and parts[5] == "sec":
            sec_keys.append(key)
        elif len(parts) == 7 and parts[5] == "img":
            img_keys.append(key)

    for key in seg_keys:  # parents first (FKs)
        try:
            raw = rc.get(key)
            if raw:
                repo.save_segment(Segment(**json.loads(raw)))
                bump("segments(redis)")
        except Exception as e:
            print(f"  ⚠️  {key}: {e}")
    for key in sec_keys:
        try:
            raw = rc.get(key)
            if raw:
                repo.save_section(SegmentSection(**json.loads(raw)))
                bump("sections(redis)")
        except Exception as e:
            print(f"  ⚠️  {key}: {e}")
    for key in img_keys:
        try:
            raw = rc.get(key)
            if raw:
                repo.save_image(SegmentImage(**json.loads(raw)))
                bump("images(redis)")
        except Exception as e:
            print(f"  ⚠️  {key}: {e}")

    # Metrics: hnfm:metrics:{item}:{run}:{seg}; index set marks finalized
    finalized = set()
    try:
        finalized = {
            (m.decode() if isinstance(m, bytes) else m)
            for m in rc.smembers("hnfm:metrics:index")
        }
    except Exception:
        pass
    for key in _scan(rc, "hnfm:metrics:*"):
        if key == "hnfm:metrics:index":
            continue
        parts = key.split(":")
        if len(parts) != 5:
            continue
        try:
            raw = rc.get(key)
            if not raw:
                continue
            data = json.loads(raw)
            repo.save_metrics(
                int(parts[2]), int(parts[3]), int(parts[4]), data,
                finalized=(key in finalized),
            )
            bump("metrics(redis)")
        except Exception as e:
            print(f"  ⚠️  {key}: {e}")


# ---------------------------------------------------------------------------
# Counters
# ---------------------------------------------------------------------------

def sync_counters():
    """Raise id_counters to at least MAX(run)/MAX(seg) per scope."""
    from sqlalchemy import func, select
    from hnfm.db import db_session
    from hnfm.db.orm import RunRow, SegmentRow

    with db_session() as s:
        run_max = s.execute(
            select(RunRow.item_id, func.max(RunRow.run)).group_by(RunRow.item_id)
        ).all()
        seg_max = s.execute(
            select(
                SegmentRow.item_id, SegmentRow.run, func.max(SegmentRow.seg)
            ).group_by(SegmentRow.item_id, SegmentRow.run)
        ).all()

    for item_id, mx in run_max:
        repo.bump_counter_to(f"run:{item_id}", int(mx))
    for item_id, run, mx in seg_max:
        repo.bump_counter_to(f"seg:{item_id}:{run}", int(mx))
    bump("counters", len(run_max) + len(seg_max))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--outputs", default=os.getenv("OUTPUTS_ROOT", "outputs"))
    parser.add_argument("--no-redis", action="store_true", help="disk mirror only")
    args = parser.parse_args()

    print("ensuring schema …")
    ensure_schema()

    print(f"disk pass: {args.outputs}")
    backfill_from_disk(Path(args.outputs))

    if not args.no_redis:
        try:
            import redis

            rc = redis.Redis(
                host=os.getenv("REDIS_HOST", "localhost"),
                port=int(os.getenv("REDIS_PORT", "6379")),
                db=int(os.getenv("REDIS_DB", "0")),
            )
            rc.ping()
            print("redis pass …")
            backfill_from_redis(rc)
        except Exception as e:
            print(f"redis unavailable ({e}); disk-only backfill")

    print("syncing counters …")
    sync_counters()

    print("\ndone:")
    for k in sorted(stats):
        print(f"  {k}: {stats[k]}")


if __name__ == "__main__":
    main()
