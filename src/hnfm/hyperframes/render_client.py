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


def health() -> bool:
    base = os.getenv("HYPERFRAMES_BASE_URL", "http://hyperframes:8088").rstrip("/")
    try:
        return requests.get(f"{base}/health", timeout=5).status_code == 200
    except Exception:
        return False
