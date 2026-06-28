"""ACE-Step music generation for hn.fm intro stings.

ACE-Step (inference-club `acestep`) is exposed OpenAI-style: POST
/v1/chat/completions with modalities=["audio"] returns generated music in
message.audio[0].audio_url.url as a base64 data-URI (mp3). We use it to make a
short, theme-matched instrumental intro per take, then trim+fade it to exactly
the intro length so the 4s subtitle offset stays aligned.

Music is optional (MUSIC_ENABLED) and always non-fatal — on any failure the
pipeline falls back to the static intro.wav.
"""

import os
import base64
import logging
import subprocess
import tempfile
import requests

logger = logging.getLogger(__name__)


def _base_url() -> str:
    return os.getenv("ACESTEP_BASE_URL", "http://host.docker.internal:8015").rstrip("/")


def generate_music_bed(prompt: str, out_wav: str) -> bool:
    """Generate an instrumental music piece and write it as a 48k stereo WAV.

    The full clip is kept (looped/volume-shaped by the caller into a bed under
    the whole video). Returns True on success, False on any failure.
    """
    try:
        r = requests.post(
            f"{_base_url()}/v1/chat/completions",
            headers={"content-type": "application/json"},
            json={
                "model": os.getenv("ACESTEP_MODEL", "acestep/acestep-v15-turbo"),
                "modalities": ["audio"],
                "audio": {"format": "mp3"},
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=int(os.getenv("MUSIC_TIMEOUT_SECONDS", "120")),
        )
        if r.status_code != 200:
            logger.warning(f"ACE-Step {r.status_code}: {r.text[:160]}")
            return False

        msg = r.json()["choices"][0]["message"]
        audio = msg.get("audio")
        url = None
        if isinstance(audio, list) and audio:
            url = (audio[0].get("audio_url") or {}).get("url")
        if not url or "base64," not in url:
            logger.warning("ACE-Step returned no audio data-URI")
            return False

        raw = base64.b64decode(url.split("base64,", 1)[1])
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
            f.write(raw)
            mp3_path = f.name

        # Render the full clip to WAV (48k stereo) — looping/volume handled by
        # the caller when mixing it under the narration.
        os.makedirs(os.path.dirname(out_wav), exist_ok=True)
        cmd = [
            "ffmpeg", "-y", "-i", mp3_path,
            "-ac", "2", "-ar", "48000",
            out_wav,
        ]
        res = subprocess.run(cmd, capture_output=True, text=True)
        try:
            os.unlink(mp3_path)
        except OSError:
            pass
        if res.returncode != 0 or not os.path.exists(out_wav):
            logger.warning(f"music ffmpeg failed: {res.stderr[:160]}")
            return False
        logger.info(f"🎵 Generated themed intro music: {out_wav}")
        return True
    except Exception as e:
        logger.warning(f"Music generation failed (non-fatal): {e}")
        return False
