"""Pipeline metrics — per-stage time, LLM tokens, and output counts.

Gives x-ray vision into every render: how long each stage took, how many tokens
each stage burned, and what it produced (images, LTX clips, hyperframes, source
images, failures). Stored per (item,run,seg) in Redis under `hnfm:metrics:*` so
the dashboard can show both aggregate trends and individual breakdowns.

Single-worker (concurrency 1), so a module-global "current stage" is enough to
attribute LLM token usage to whatever stage is running — no plumbing through
every call site.
"""

import json
import time
import logging
from contextlib import contextmanager

logger = logging.getLogger(__name__)

# (item, run, seg, stage) currently executing — set by stage(); read by record_tokens.
_CURRENT = {"item": None, "run": None, "seg": None, "stage": None}


def _redis():
    from ..web.tasks import get_redis_client
    return get_redis_client()


def _key(item, run, seg):
    return f"hnfm:metrics:{item}:{run}:{seg}"


def _load(rc, item, run, seg):
    raw = rc.get(_key(item, run, seg))
    if raw:
        try:
            return json.loads(raw)
        except Exception:
            pass
    return {"item_id": item, "run": run, "seg": seg, "stages": {}, "counts": {}}


def _save(rc, data):
    rc.set(_key(data["item_id"], data["run"], data["seg"]), json.dumps(data))


def init(item, run, seg, title=None, theme=None, fmt=None):
    """Start a metrics record for a run (called at pipeline start)."""
    try:
        rc = _redis()
        data = _load(rc, item, run, seg)
        data.update(title=title, theme=theme, format=fmt, started_ts=time.time())
        _save(rc, data)
    except Exception as e:
        logger.debug(f"metrics init failed (non-fatal): {e}")


@contextmanager
def stage(item, run, seg, name):
    """Time a pipeline stage and mark it current (for token attribution)."""
    prev = dict(_CURRENT)
    _CURRENT.update(item=item, run=run, seg=seg, stage=name)
    t0 = time.time()
    try:
        yield
    finally:
        dt = time.time() - t0
        try:
            rc = _redis()
            data = _load(rc, item, run, seg)
            s = data["stages"].setdefault(name, {})
            s["seconds"] = round(s.get("seconds", 0) + dt, 2)
            _save(rc, data)
        except Exception as e:
            logger.debug(f"metrics stage failed (non-fatal): {e}")
        _CURRENT.update(prev)


def record_seconds(item, run, seg, name, seconds):
    """Record a pre-measured stage duration (for stages timed before seg is known)."""
    try:
        rc = _redis()
        data = _load(rc, item, run, seg)
        s = data["stages"].setdefault(name, {})
        s["seconds"] = round(s.get("seconds", 0) + seconds, 2)
        _save(rc, data)
    except Exception as e:
        logger.debug(f"metrics record_seconds failed (non-fatal): {e}")


def record_tokens(prompt_tokens=0, completion_tokens=0, calls=1, stage_name=None):
    """Attribute LLM token usage to the current (or named) stage."""
    item, run, seg = _CURRENT["item"], _CURRENT["run"], _CURRENT["seg"]
    name = stage_name or _CURRENT["stage"]
    if item is None or not name:
        return
    try:
        rc = _redis()
        data = _load(rc, item, run, seg)
        s = data["stages"].setdefault(name, {})
        s["tokens_in"] = s.get("tokens_in", 0) + int(prompt_tokens or 0)
        s["tokens_out"] = s.get("tokens_out", 0) + int(completion_tokens or 0)
        s["llm_calls"] = s.get("llm_calls", 0) + calls
        _save(rc, data)
    except Exception as e:
        logger.debug(f"metrics tokens failed (non-fatal): {e}")


def count(item, run, seg, key, n=1):
    """Bump an output counter (images, ltx_clips, hyperframes, ltx_failures, …)."""
    try:
        rc = _redis()
        data = _load(rc, item, run, seg)
        data["counts"][key] = data["counts"].get(key, 0) + n
        _save(rc, data)
    except Exception as e:
        logger.debug(f"metrics count failed (non-fatal): {e}")


def finalize(item, run, seg, status="ok"):
    """Roll up totals at the end of a run."""
    try:
        rc = _redis()
        data = _load(rc, item, run, seg)
        st = data.get("stages", {})
        data["total_seconds"] = round(sum(s.get("seconds", 0) for s in st.values()), 2)
        data["total_tokens_in"] = sum(s.get("tokens_in", 0) for s in st.values())
        data["total_tokens_out"] = sum(s.get("tokens_out", 0) for s in st.values())
        data["status"] = status
        data["finished_ts"] = time.time()
        _save(rc, data)
        rc.sadd("hnfm:metrics:index", _key(item, run, seg))
    except Exception as e:
        logger.debug(f"metrics finalize failed (non-fatal): {e}")


def all_records(limit=200):
    """Every metrics record (newest first) for the dashboard."""
    rc = _redis()
    out = []
    for k in rc.smembers("hnfm:metrics:index"):
        raw = rc.get(k.decode() if isinstance(k, bytes) else k)
        if raw:
            try:
                out.append(json.loads(raw))
            except Exception:
                pass
    out.sort(key=lambda d: d.get("finished_ts") or d.get("started_ts") or 0, reverse=True)
    return out[:limit]


def get_record(item, run, seg):
    rc = _redis()
    raw = rc.get(_key(item, run, seg))
    return json.loads(raw) if raw else None
