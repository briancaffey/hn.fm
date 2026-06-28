"""LTX-2 image-to-video for hn.fm.

We do NOT render a clip per frame. Instead, for a few key narration sections we
generate ONE short LTX clip (image-to-video, ~2-4s) and then **stretch** it to
the section's spoken duration by slowing playback (setpts) and motion-compensated
frame interpolation (ffmpeg minterpolate) — smooth slow cinematic motion for cheap.

The motion prompt is built from the section's original image prompt + a camera
directive. LTX endpoint: POST /generate (JSON: prompt, image=base64, num_frames,
fps, width, height, ...) -> video/mp4 bytes.
"""

import os
import base64
import logging
import subprocess
import requests

logger = logging.getLogger(__name__)

MOTION_DIRECTIVES = [
    "slow cinematic push-in with subtle parallax and gentle ambient motion",
    "slow dolly drift across the scene, soft atmospheric movement",
    "gentle slow zoom-out revealing more of the scene, drifting particles",
    "subtle handheld sway, living atmosphere, faint motion in the background",
    "smooth crane-up reveal, calm drifting motion",
]

# LTX native clip is capped short; the stretch fills the rest of the section.
MAX_NATIVE_SECONDS = float(os.getenv("LTX_MAX_NATIVE_SECONDS", "4.0"))
LTX_FPS = int(os.getenv("LTX_FPS", "24"))
OUT_FPS = int(os.getenv("LTX_OUT_FPS", "24"))
LTX_STEPS = int(os.getenv("LTX_STEPS", "20"))
# Interpolation mode for the stretch: "blend" (fast, soft) or "mci"
# (motion-compensated, smoother but very CPU-heavy on long stretches).
INTERP_MODE = os.getenv("LTX_INTERP_MODE", "blend")


def _base_url() -> str:
    return os.getenv("LTX_BASE_URL", "http://host.docker.internal:8023").rstrip("/")


def motion_prompt(image_prompt: str, idx: int = 0) -> str:
    """Build an LTX motion prompt from the still's image prompt + a camera move."""
    directive = MOTION_DIRECTIVES[idx % len(MOTION_DIRECTIVES)]
    base = (image_prompt or "").strip()
    return f"{base}. Camera: {directive}. Coherent, photoreal motion, no morphing."


def _round_frames(n: int) -> int:
    """LTX likes (8k+1) frame counts; clamp to a sane range."""
    n = max(25, min(121, int(n)))
    return ((n - 1) // 8) * 8 + 1


def generate_clip(prompt: str, image_path: str, out_path: str, width: int, height: int,
                  native_seconds: float) -> bool:
    """Generate a short LTX image-to-video clip (mp4) from `image_path`."""
    try:
        b64 = base64.b64encode(open(image_path, "rb").read()).decode()
        n_frames = _round_frames(round(min(native_seconds, MAX_NATIVE_SECONDS) * LTX_FPS))
        payload = {
            "prompt": prompt,
            "image": b64,
            "image_strength": 1.0,
            "num_frames": n_frames,
            "fps": LTX_FPS,
            "width": width,
            "height": height,
            "num_inference_steps": LTX_STEPS,
        }
        r = requests.post(
            f"{_base_url()}/generate",
            json=payload,
            timeout=int(os.getenv("LTX_TIMEOUT_SECONDS", "600")),
        )
        if r.status_code != 200 or not r.content:
            logger.warning(f"LTX {r.status_code}: {r.text[:160]}")
            return False
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        with open(out_path, "wb") as f:
            f.write(r.content)
        return True
    except Exception as e:
        logger.warning(f"LTX generate failed (non-fatal): {e}")
        return False


def stretch_clip(in_path: str, out_path: str, target_seconds: float, width: int, height: int) -> bool:
    """Slow `in_path` to `target_seconds` with motion interpolation; pad to WxH."""
    try:
        dur = float(
            subprocess.run(
                ["ffprobe", "-v", "error", "-show_entries", "format=duration",
                 "-of", "csv=p=0", in_path],
                capture_output=True, text=True,
            ).stdout.strip() or 0
        )
        if dur <= 0:
            return False
        factor = max(1.0, target_seconds / dur)
        if INTERP_MODE == "mci":
            interp = f"minterpolate=fps={OUT_FPS}:mi_mode=mci:mc_mode=aobmc:me_mode=bidir"
        else:
            interp = f"minterpolate=fps={OUT_FPS}:mi_mode=blend"
        vf = (
            f"setpts={factor:.4f}*PTS,{interp},"
            f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
            f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:black"
        )
        cmd = [
            "ffmpeg", "-y", "-i", in_path, "-vf", vf,
            "-t", f"{target_seconds:.3f}", "-an",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "medium", "-crf", "22",
            out_path,
        ]
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode != 0 or not os.path.exists(out_path):
            logger.warning(f"LTX stretch ffmpeg failed: {res.stderr[:160]}")
            return False
        return True
    except Exception as e:
        logger.warning(f"LTX stretch failed (non-fatal): {e}")
        return False


def make_motion_clip(image_path: str, image_prompt: str, out_path: str,
                     target_seconds: float, width: int, height: int, idx: int = 0) -> bool:
    """High-level: generate a short LTX clip from the still, then stretch to fit."""
    raw = out_path.replace(".mp4", "_raw.mp4")
    if not generate_clip(motion_prompt(image_prompt, idx), image_path, raw,
                         width, height, target_seconds):
        return False
    ok = stretch_clip(raw, out_path, target_seconds, width, height)
    try:
        os.remove(raw)
    except OSError:
        pass
    return ok
