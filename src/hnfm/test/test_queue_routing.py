"""Queue routing (issue #1).

One queue and one worker slot meant a 4-second scrape sat behind a 3-hour
`full_pipeline`. Routing now lives in `celery_app.task_routes` rather than at
the ~22 `apply_async` call sites, so these tests guard the property that
matters: every task lands in the lane matching its cost, and no caller can
quietly override it.
"""

import pytest

from ..web.celery_app import (
    celery_app,
    QUEUE_DIGEST,
    QUEUE_INGEST,
    QUEUE_RENDER,
    QUEUE_TRIAGE,
)

ROUTES = celery_app.conf.task_routes

EXPECTED = {
    "hnfm.web.tasks.hn_fetch_item": QUEUE_INGEST,
    "hnfm.web.tasks.process_hn_item_run": QUEUE_INGEST,
    "hnfm.web.tasks.score_run": QUEUE_TRIAGE,
    "hnfm.web.tasks.enrich_run": QUEUE_INGEST,
    "hnfm.web.tasks.build_story_brief": QUEUE_TRIAGE,
    "hnfm.web.tasks.build_digest": QUEUE_DIGEST,
    "hnfm.web.tasks.full_pipeline": QUEUE_RENDER,
    "hnfm.web.tasks.generate_segment": QUEUE_RENDER,
    "hnfm.web.tasks.build_segment_audio": QUEUE_RENDER,
    "hnfm.web.tasks.build_segment_images": QUEUE_RENDER,
    "hnfm.web.tasks.build_segment_episode": QUEUE_RENDER,
    "hnfm.web.tasks.generate_segment_video": QUEUE_RENDER,
    "hnfm.web.tasks.rebuild_single_image": QUEUE_RENDER,
    "hnfm.web.tasks.rerun_step": QUEUE_RENDER,
}


@pytest.mark.parametrize("task_name,queue", sorted(EXPECTED.items()))
def test_task_routes_to_its_cost_class(task_name, queue):
    assert ROUTES[task_name]["queue"] == queue


def test_every_registered_task_has_a_route():
    """An unrouted task falls back to the default queue, which nothing in the
    split setup consumes — it would silently never run."""
    registered = {
        name for name in celery_app.tasks if name.startswith("hnfm.web.tasks.")
    }
    assert registered, "no hnfm tasks registered"
    assert registered - set(ROUTES) == set()


def test_ingest_and_render_are_separate_lanes():
    """The whole point: a scrape must not queue behind a video render."""
    assert (
        ROUTES["hnfm.web.tasks.process_hn_item_run"]["queue"]
        != ROUTES["hnfm.web.tasks.full_pipeline"]["queue"]
    )


def test_no_caller_overrides_the_queue():
    """Routing is centralised; an explicit `queue=` at a call site silently
    wins over task_routes and would undo the split."""
    import pathlib

    root = pathlib.Path(__file__).resolve().parents[1]
    offenders = []
    for path in (root / "web").glob("*.py"):
        if path.name == "celery_app.py":
            continue
        for i, line in enumerate(path.read_text().splitlines(), 1):
            if "queue=" in line and "apply_async" not in line.replace("queue=", ""):
                if "queue=\"hnfm" in line or "queue='hnfm" in line:
                    offenders.append(f"{path.name}:{i}")
    assert offenders == [], f"hardcoded queue= found: {offenders}"
