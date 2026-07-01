"""Step recorder — the pipeline audit trail (plans/02-audit-trail.md).

Every unit of work records a pipeline_steps row with the exact inputs it used
(prompt, params, text) and the outputs it produced. Inputs are the replay
payload: the rerun API re-executes a step from them, optionally overridden.

Like metrics.py, recording is deliberately non-fatal and uses a module-global
"current step" for LLM token attribution — fine under the single-worker model.
"""

import logging
import time
from contextlib import contextmanager
from datetime import datetime
from typing import List, Optional

from sqlalchemy import select, update

from .engine import db_session
from .orm import PipelineStepRow

logger = logging.getLogger(__name__)

_CURRENT = {"step_id": None}

# Inputs/outputs are replay payloads, not archives — cap giant strings (full
# article bodies live on the run row already).
_MAX_STR = 4000


def _bounded(value):
    if isinstance(value, str) and len(value) > _MAX_STR:
        return value[:_MAX_STR] + f"… [truncated, {len(value)} chars total]"
    if isinstance(value, dict):
        return {k: _bounded(v) for k, v in value.items()}
    if isinstance(value, list):
        if len(value) > 200:
            return [_bounded(v) for v in value[:200]] + [
                f"… [truncated, {len(value)} items total]"
            ]
        return [_bounded(v) for v in value]
    return value


class StepHandle:
    """Mutable outputs collector for the step being executed."""

    def __init__(self, step_id: Optional[int]):
        self.step_id = step_id
        self.outputs = {}
        self._soft_error = None

    def set(self, **kwargs) -> None:
        self.outputs.update(kwargs)

    def soft_fail(self, message: str) -> None:
        """Mark the step failed without raising (for non-fatal pipeline units
        like an LTX clip that didn't come out)."""
        self._soft_error = message


@contextmanager
def step(item_id: int, run: int, seg: Optional[int], stage: str, step_key: str, inputs: dict = None):
    """Record one unit of pipeline work. Recording failures never propagate;
    exceptions from the wrapped work do (after being recorded)."""
    row_id = None
    try:
        with db_session() as s:
            row = PipelineStepRow(
                item_id=item_id,
                run=run,
                seg=seg,
                stage=stage,
                step_key=step_key,
                status="running",
                started_at=datetime.utcnow(),
                inputs=_bounded(inputs or {}),
            )
            s.add(row)
            s.flush()
            row_id = row.id
    except Exception as e:
        logger.debug(f"step begin failed (non-fatal): {e}")

    handle = StepHandle(row_id)
    prev = _CURRENT["step_id"]
    _CURRENT["step_id"] = row_id
    t0 = time.time()
    try:
        yield handle
        _finish(row_id, "error" if handle._soft_error else "ok",
                time.time() - t0, handle.outputs, handle._soft_error)
    except Exception as e:
        _finish(row_id, "error", time.time() - t0, handle.outputs, str(e))
        raise
    finally:
        _CURRENT["step_id"] = prev


def _finish(row_id, status, seconds, outputs, error=None):
    if row_id is None:
        return
    try:
        with db_session() as s:
            row = s.get(PipelineStepRow, row_id)
            if row is None:
                return
            row.status = status
            row.finished_at = datetime.utcnow()
            row.seconds = round(seconds, 3)
            row.outputs = _bounded(outputs or {})
            row.error = error
            if status == "ok":
                # Latest-wins: older attempts at the same unit become history.
                # "running" is included so rows orphaned by a worker crash
                # don't show as perpetually running once a retry lands.
                s.execute(
                    update(PipelineStepRow)
                    .where(
                        PipelineStepRow.item_id == row.item_id,
                        PipelineStepRow.run == row.run,
                        (PipelineStepRow.seg.is_(None) if row.seg is None
                         else PipelineStepRow.seg == row.seg),
                        PipelineStepRow.step_key == row.step_key,
                        PipelineStepRow.id < row.id,
                        PipelineStepRow.status.in_(["ok", "stale", "error", "running"]),
                    )
                    .values(status="superseded")
                    .execution_options(synchronize_session=False)
                )
    except Exception as e:
        logger.debug(f"step finish failed (non-fatal): {e}")


def record_llm(model: str = None, tokens_in: int = 0, tokens_out: int = 0) -> None:
    """Attribute an LLM call to the currently executing step (non-fatal)."""
    row_id = _CURRENT["step_id"]
    if row_id is None:
        return
    try:
        with db_session() as s:
            row = s.get(PipelineStepRow, row_id)
            if row is None:
                return
            if model:
                row.model = model
            row.tokens_in = (row.tokens_in or 0) + int(tokens_in or 0)
            row.tokens_out = (row.tokens_out or 0) + int(tokens_out or 0)
            row.llm_calls = (row.llm_calls or 0) + 1
    except Exception as e:
        logger.debug(f"step llm record failed (non-fatal): {e}")


# ---------------------------------------------------------------------------
# Queries
# ---------------------------------------------------------------------------

def _to_dict(row: PipelineStepRow) -> dict:
    return {
        "id": row.id,
        "item_id": row.item_id,
        "run": row.run,
        "seg": row.seg,
        "stage": row.stage,
        "step_key": row.step_key,
        "status": row.status,
        "started_at": row.started_at.isoformat() if row.started_at else None,
        "finished_at": row.finished_at.isoformat() if row.finished_at else None,
        "seconds": row.seconds,
        "model": row.model,
        "tokens_in": row.tokens_in,
        "tokens_out": row.tokens_out,
        "llm_calls": row.llm_calls,
        "inputs": row.inputs,
        "outputs": row.outputs,
        "error": row.error,
        "supersedes": row.supersedes,
    }


def list_steps(item_id: int, run: int, seg: Optional[int] = None) -> List[dict]:
    """Steps for a run, in execution order. With `seg`, includes the run-scoped
    steps (seg IS NULL) that fed it."""
    with db_session() as s:
        q = select(PipelineStepRow).where(
            PipelineStepRow.item_id == item_id, PipelineStepRow.run == run
        )
        if seg is not None:
            q = q.where(
                (PipelineStepRow.seg.is_(None)) | (PipelineStepRow.seg == seg)
            )
        q = q.order_by(PipelineStepRow.id.asc())
        return [_to_dict(r) for r in s.execute(q).scalars()]


def get_step(step_id: int) -> Optional[dict]:
    with db_session() as s:
        row = s.get(PipelineStepRow, step_id)
        return _to_dict(row) if row else None


def supersede(step_id: int) -> None:
    with db_session() as s:
        row = s.get(PipelineStepRow, step_id)
        if row and row.status not in ("superseded",):
            row.status = "superseded"


def rerun_supported(step_key: str) -> bool:
    """Which step kinds the rerun API can re-execute."""
    if step_key in ("script", "audio/asr", "video/assemble", "media_plan/plan"):
        return True
    if step_key.startswith("audio/sec_"):
        return True
    if step_key.startswith("images/") and step_key.endswith("/root"):
        return True
    return False


# ---------------------------------------------------------------------------
# Staleness — a static stage-dependency map, not a graph engine
# ---------------------------------------------------------------------------

def stale_patterns_for(step_key: str) -> List[str]:
    """SQL LIKE patterns of steps invalidated by re-running `step_key`.

    Note: rerunning a section's audio re-stitches and re-ASRs within the same
    task, so those steps get fresh rows anyway — video is what truly goes
    stale from the older run.
    """
    if step_key == "script":
        return ["audio/%", "images/%", "media_plan/%", "video/%"]
    if step_key.startswith("audio/sec_"):
        return ["audio/stitch", "audio/asr", "video/%"]
    parts = step_key.split("/")
    if step_key.startswith("images/") and step_key.endswith("/root"):
        n = parts[1]
        return [f"images/{n}/frame_%", f"media_plan/clip_{n}", "video/%"]
    if step_key.startswith("images/") and "frame" in step_key:
        return ["video/%"]
    if step_key.startswith("media_plan/"):
        return ["video/%"]
    if step_key == "audio/asr":
        return ["video/%"]
    return []


def mark_stale(item_id: int, run: int, seg: Optional[int], patterns: List[str]) -> int:
    """Mark ok-steps matching any pattern as stale. Returns count."""
    if not patterns:
        return 0
    total = 0
    with db_session() as s:
        for pattern in patterns:
            q = (
                update(PipelineStepRow)
                .where(
                    PipelineStepRow.item_id == item_id,
                    PipelineStepRow.run == run,
                    PipelineStepRow.step_key.like(pattern),
                    PipelineStepRow.status == "ok",
                )
                .execution_options(synchronize_session=False)
            )
            if seg is not None:
                q = q.where(
                    (PipelineStepRow.seg.is_(None)) | (PipelineStepRow.seg == seg)
                )
            total += s.execute(q.values(status="stale")).rowcount or 0
    return total


def activity(recent_minutes: int = 10) -> dict:
    """What the pipeline is doing right now: running steps plus recently
    finished ones — feeds the sidebar activity indicator."""
    from datetime import timedelta

    cutoff = datetime.utcnow() - timedelta(minutes=recent_minutes)
    with db_session() as s:
        running = [
            _to_dict(r)
            for r in s.execute(
                select(PipelineStepRow)
                .where(PipelineStepRow.status == "running")
                .order_by(PipelineStepRow.id.desc())
                .limit(20)
            ).scalars()
        ]
        recent = [
            _to_dict(r)
            for r in s.execute(
                select(PipelineStepRow)
                .where(
                    PipelineStepRow.status.in_(["ok", "error"]),
                    PipelineStepRow.finished_at >= cutoff,
                )
                .order_by(PipelineStepRow.id.desc())
                .limit(20)
            ).scalars()
        ]
    return {"running": running, "recent": recent}


def list_stale(item_id: int, run: int, seg: Optional[int] = None) -> List[dict]:
    with db_session() as s:
        q = select(PipelineStepRow).where(
            PipelineStepRow.item_id == item_id,
            PipelineStepRow.run == run,
            PipelineStepRow.status == "stale",
        )
        if seg is not None:
            q = q.where(
                (PipelineStepRow.seg.is_(None)) | (PipelineStepRow.seg == seg)
            )
        return [_to_dict(r) for r in s.execute(q.order_by(PipelineStepRow.id)).scalars()]
