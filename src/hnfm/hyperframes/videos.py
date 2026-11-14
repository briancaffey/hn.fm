"""A story video, start to finish, and the record of how it was made.

    brief     what the narrated segment gives us (story.py)
    build     the whole project with plain scenes (kit.py)
    direct    Hermes chooses a treatment for each scene (author.py)
    review    the renderer checks the assembled project
    render    one MP4, narration and captions included

Each video lives in its own folder with a status file the desk reads. A
video can always be made: with no agent, or with one that fails, every
scene keeps its plain version.
"""

import json
import logging
import os
import re
import shutil
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional

from . import author, hermes, kit, music, render_client, shots, story

logger = logging.getLogger(__name__)


def root() -> str:
    d = os.path.join(os.getenv("OUTPUTS_DIR", "/app/outputs"), "hyperframes", "videos")
    os.makedirs(d, exist_ok=True)
    return d


def video_id(item_id: int, run: int, seg: int) -> str:
    return f"{int(item_id)}-{int(run)}-{int(seg)}"


_ID = re.compile(r"^\d+-\d+-\d+$")


def folder(vid: str) -> str:
    """A video's folder. Ids are item-run-seg and nothing else: this is
    what stands between a request and a path on the outputs volume."""
    if not _ID.match(str(vid)):
        raise ValueError(f"not a video id: {vid!r}")
    return os.path.join(root(), vid)


def _status_path(vid: str) -> str:
    return os.path.join(folder(vid), "status.json")


def get(vid: str) -> Optional[Dict]:
    if not _ID.match(str(vid)):
        return None
    try:
        with open(_status_path(vid)) as f:
            st = json.load(f)
    except Exception:
        return None
    st["video"] = os.path.exists(path(vid, "video.mp4"))
    st["poster"] = os.path.exists(path(vid, "poster.jpg"))
    return st


def path(vid: str, name: str) -> str:
    return os.path.join(folder(vid), os.path.basename(name))


def _save(vid: str, st: Dict) -> None:
    st["updated_at"] = datetime.now(timezone.utc).isoformat()
    tmp = _status_path(vid) + ".tmp"
    with open(tmp, "w") as f:
        json.dump(st, f, indent=1)
    os.replace(tmp, _status_path(vid))


def listing() -> List[Dict]:
    """Every video, newest first, without the per-scene detail."""
    out = []
    for name in os.listdir(root()):
        st = get(name) if _ID.match(name) else None
        if st:
            out.append({k: v for k, v in st.items() if k != "scenes"})
    return sorted(out, key=lambda s: s.get("updated_at") or "", reverse=True)


def remove(vid: str) -> bool:
    if not _ID.match(str(vid)):
        return False
    d = folder(vid)
    if not os.path.isdir(d):
        return False
    shutil.rmtree(d)
    return True


WORKING = ("building", "drawing", "directing", "rendering")
STALE_SECONDS = 45 * 60


def busy(vid: str) -> bool:
    """Is this video being asked for or made right now? A status that has
    not moved in 45 minutes belongs to a worker that died, and does not
    count."""
    st = get(vid)
    if not st or st.get("state") not in WORKING + ("queued",):
        return False
    try:
        age = (datetime.now(timezone.utc) - datetime.fromisoformat(st["updated_at"])).total_seconds()
    except (KeyError, ValueError, TypeError):
        return False
    return age < STALE_SECONDS


def queued(item_id: int, run: int, seg: int, title: str = "") -> Dict:
    """Mark a video as asked for, so the desk shows it before work starts."""
    vid = video_id(item_id, run, seg)
    os.makedirs(folder(vid), exist_ok=True)
    st = {"id": vid, "item_id": item_id, "run": run, "seg": seg, "title": title, "state": "queued",
          "step": "waiting for a worker", "asked_at": datetime.now(timezone.utc).isoformat()}
    _save(vid, st)
    return st


def make(item_id: int, run: int, seg: int, direct: bool = True) -> Dict:
    """Make (or remake) the video for one narrated segment."""
    vid = video_id(item_id, run, seg)
    started = time.time()
    st = get(vid) or {"id": vid, "item_id": item_id, "run": run, "seg": seg}
    # The same job delivered twice would have two workers rewriting one
    # project under each other. The second one leaves.
    if st.get("state") in WORKING and busy(vid):
        logger.info(f"story video {vid}: already being made; leaving it alone")
        return {**st, "state": "busy"}
    st.update(state="building", step="reading the narration", error=None, scenes=[])
    os.makedirs(folder(vid), exist_ok=True)
    _save(vid, st)

    def fail(why: str) -> Dict:
        st.update(state="failed", step=why, error=why, seconds=round(time.time() - started, 1))
        _save(vid, st)
        logger.warning(f"story video {vid}: {why}")
        return st

    brief = story.brief(item_id, run, seg)
    if not brief:
        return fail("this segment has no narration to build on")
    project = os.path.join(folder(vid), "project")
    shutil.rmtree(project, ignore_errors=True)

    # Pictures and music come before the build: the kit lays the pictures
    # into every shot. Both are asked of the agent and made on the home lab.
    if direct and hermes.configured():
        def say(step):
            st.update(state="drawing", step=step)
            _save(vid, st)
        try:
            st["plan"] = shots.plan(brief, say)
            _save(vid, st)
            st["pictures"] = shots.draw(brief, folder(vid), say)
        except Exception as e:
            logger.exception("shot plan")
            st["pictures"] = {"error": str(e)[:200]}
        say("scoring the music")
        st["music"] = music.make(brief, folder(vid))
    try:
        brief = kit.build(brief, project)
    except Exception as e:
        return fail(f"the project could not be built: {str(e)[:160]}")
    st.update(title=brief["title"], length=brief["seconds"], theme=brief["theme"], total=len(brief["scenes"]),
              domain=brief.get("domain"))

    directed, tokens, records = 0, 0, []
    use_agent = direct and hermes.configured()
    st["author"] = "hermes" if use_agent else "none"
    if direct and not use_agent:
        st["note"] = "no agent is configured: every scene is the plain version"
    if use_agent:
        before, previous, misses = [], None, 0
        for sc in brief["scenes"]:
            st.update(state="directing", step=f"scene {sc['n']} of {len(brief['scenes'])}")
            _save(vid, st)
            rec = author.direct_scene(project, brief, sc, before, previous, job=vid)
            records.append(rec)
            tokens += rec.get("tokens") or 0
            st["scenes"] = records
            if rec["accepted"]:
                directed += 1
                misses = 0
                before.append(f"scene {sc['n']}: {rec['looks_like']}")
                previous = rec["treatment"]
            else:
                misses += 1
                previous = None
                # An agent that is away fails every scene the same way;
                # stop asking after three in a row and keep what there is.
                if misses >= 3 and any(r.get("problem") for r in rec["rounds"]):
                    st["note"] = "the agent stopped answering; the remaining scenes are plain"
                    break
    st.update(directed=directed, plain=len(brief["scenes"]) - directed, tokens=tokens)

    # The sign-off credits whoever did the work.
    credit = (f"Scenes directed by Hermes ({directed} of {len(brief['scenes'])}) · built with HyperFrames"
              if directed else "Built with HyperFrames")
    kit._write(project, "compositions/outro.html", kit.outro(brief, credit))

    st.update(state="rendering", step="the renderer is reviewing the project")
    _save(vid, st)
    checked = render_client.check(project)
    st["review"] = _summary(checked.get("report") or {})

    st["step"] = "rendering"
    _save(vid, st)
    out = path(vid, "video.mp4")
    tmp = out.replace(".mp4", ".part.mp4")
    got = render_client.render(project, tmp, fps=kit.FPS)
    if not got.get("ok"):
        return fail(f"the render failed: {str(got.get('error') or got.get('log') or '')[-300:]}")
    os.replace(tmp, out)
    st["render_seconds"] = got.get("seconds")
    st["bytes"] = os.path.getsize(out)

    _stills(vid, project, brief)
    st.update(state="done", step="made", seconds=round(time.time() - started, 1),
              made_at=datetime.now(timezone.utc).isoformat())
    _save(vid, st)
    logger.info(f"story video {vid}: made in {st['seconds']}s, {directed}/{len(brief['scenes'])} scenes directed")
    return st


def _summary(report: Dict) -> Dict:
    out = {}
    for part, section in report.items():
        if isinstance(section, dict) and "errorCount" in section:
            out[part] = {"errors": section.get("errorCount", 0), "warnings": section.get("warningCount", 0)}
    return out


def _stills(vid: str, project: str, brief: Dict) -> None:
    """A poster and a sheet of one frame per scene, for the desk."""
    try:
        from PIL import Image

        frames = os.path.join(folder(vid), "frames")
        shutil.rmtree(frames, ignore_errors=True)
        at = [1.6] + [round(brief["lead"] + sc["start"] + sc["seconds"] * 0.8, 2) for sc in brief["scenes"]]
        render_client.frames(project, at, frames)
        shots = sorted(f for f in os.listdir(frames) if f.startswith("frame-") and f.endswith(".png"))
        if not shots:
            return
        Image.open(os.path.join(frames, shots[0])).convert("RGB").save(path(vid, "poster.jpg"), "JPEG", quality=86)
        tiles = [Image.open(os.path.join(frames, s)).convert("RGB").resize((426, 240)) for s in shots[1:]]
        if tiles:
            cols = 4
            rows = (len(tiles) + cols - 1) // cols
            sheet = Image.new("RGB", (cols * 426, rows * 240), (16, 16, 16))
            for i, t in enumerate(tiles):
                sheet.paste(t, ((i % cols) * 426, (i // cols) * 240))
            sheet.save(path(vid, "sheet.jpg"), "JPEG", quality=84)
        shutil.rmtree(frames, ignore_errors=True)
    except Exception as e:
        logger.warning(f"story video {vid}: no stills ({e})")
