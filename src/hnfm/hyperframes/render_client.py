"""Client for the HyperFrames render sidecar.

The sidecar shares the `outputs` volume at the same path, so we pass absolute
paths that resolve identically on both sides. Reached over the compose network
(service `hyperframes`), which maps cleanly to a k3s Service later.
"""

import os
import logging
import requests

logger = logging.getLogger(__name__)


def render_project(project_dir: str, output_path: str, fmt: str = "mp4",
                   fps: int = 30, quality: str = "standard") -> bool:
    """Render a HyperFrames project dir to `output_path`. Non-fatal on failure."""
    base = os.getenv("HYPERFRAMES_BASE_URL", "http://hyperframes:8088").rstrip("/")
    try:
        r = requests.post(
            f"{base}/render",
            json={"project": project_dir, "output": output_path,
                  "format": fmt, "fps": fps, "quality": quality},
            timeout=int(os.getenv("HYPERFRAMES_TIMEOUT_SECONDS", "600")),
        )
        d = {}
        try:
            d = r.json()
        except Exception:
            pass
        if r.status_code == 200 and d.get("ok") and os.path.exists(output_path):
            return True
        logger.warning(f"hyperframes render failed: {str(d)[:400] or r.status_code}")
        return False
    except Exception as e:
        logger.warning(f"hyperframes render error (non-fatal): {e}")
        return False


def _post(path: str, body: dict, timeout: int) -> dict:
    base = os.getenv("HYPERFRAMES_BASE_URL", "http://hyperframes:8088").rstrip("/")
    try:
        r = requests.post(f"{base}{path}", json=body, timeout=timeout)
        return r.json()
    except Exception as e:
        return {"ok": False, "error": str(e)[:300]}


def render(project_dir: str, output_path: str, fps: int = 24, quality: str = "standard",
           timeout: int = 1500) -> dict:
    """Render and say how it went: {ok, seconds, log}."""
    d = _post("/render", {"project": project_dir, "output": output_path, "format": "mp4",
                          "fps": fps, "quality": quality, "timeout": timeout}, timeout + 60)
    d["ok"] = bool(d.get("ok")) and os.path.exists(output_path)
    return d


def check(project_dir: str, lint_only: bool = False) -> dict:
    """The renderer's own review of a project: {ok, report} where report has
    lint, runtime, layout, motion, contrast and craft findings."""
    return _post("/check", {"project": project_dir, "lintOnly": lint_only}, 660)


def frames(project_dir: str, at: list, out_dir: str) -> dict:
    """PNG stills at the given seconds, plus a contact sheet."""
    return _post("/frames", {"project": project_dir, "at": at, "output": out_dir}, 660)


def health() -> bool:
    base = os.getenv("HYPERFRAMES_BASE_URL", "http://hyperframes:8088").rstrip("/")
    try:
        return requests.get(f"{base}/health", timeout=5).status_code == 200
    except Exception:
        return False
