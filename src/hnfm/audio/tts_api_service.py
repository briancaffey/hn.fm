"""TTS API service for hn.fm — supports two backends:

- **magpie** (default): NVIDIA Magpie TTS (`magpie-tts` in the inference-club
  cluster). Single-voice-per-call, so the `[S1]/[S2]` dialogue is split by
  speaker and voiced with two distinct voices (S1=Mia, S2=Jason), then the WAV
  clips are concatenated.
- **dia**: the original Dia FastAPI service (`/generate`), which voices both
  `[S1]/[S2]` speakers from a single call using a cloned voice sample.

Select via `TTS_BACKEND` (env) or `tts.backend` (config). The rest of the
pipeline calls `generate_speech(text, voice)` and gets WAV bytes either way.
"""

import io
import os
import re
import time
import wave
import random
import logging
import requests
from pathlib import Path
from typing import List, Optional, Dict, Any, Tuple

logger = logging.getLogger(__name__)

# Magpie voice mapping for the two hn.fm hosts.
S1_VOICE = os.getenv("MAGPIE_S1_VOICE", "Magpie-Multilingual.EN-US.Mia")
S2_VOICE = os.getenv("MAGPIE_S2_VOICE", "Magpie-Multilingual.EN-US.Jason")
MAGPIE_LANGUAGE = os.getenv("MAGPIE_LANGUAGE", "en-US")
MAGPIE_SAMPLE_RATE = int(os.getenv("MAGPIE_SAMPLE_RATE", "22050"))
TURN_GAP_MS = int(os.getenv("MAGPIE_TURN_GAP_MS", "180"))


class TtsApiService:
    """Text-to-speech service with pluggable backend (magpie | dia)."""

    def __init__(self, base_url: str = None, backend: str = None):
        from ..utils.config import config_manager

        self.backend = (
            backend
            or os.getenv("TTS_BACKEND")
            or config_manager.get("tts.backend", "magpie")
        ).lower()

        if base_url is None:
            default = "http://localhost:9000" if self.backend == "magpie" else "http://localhost:8491"
            base_url = config_manager.get("tts.base_url", default) or default
        self.base_url = base_url.rstrip("/")

        self.max_attempts = int(config_manager.get("tts.max_attempts", 3))
        timeout_val = config_manager.get("tts.timeout_seconds", 120)
        if isinstance(timeout_val, str) and timeout_val.startswith("${"):
            self.timeout_seconds = 120
        else:
            self.timeout_seconds = int(timeout_val)
        self.retry_delay = 5

        logger.info(f"🎛️  TTS backend = {self.backend} @ {self.base_url}")
        self._test_connection()

    # ---- health -----------------------------------------------------------
    def _health_url(self) -> str:
        return (
            f"{self.base_url}/v1/health/ready"
            if self.backend == "magpie"
            else f"{self.base_url}/health"
        )

    def is_healthy(self) -> bool:
        try:
            return requests.get(self._health_url(), timeout=5).status_code == 200
        except Exception as e:
            logger.debug(f"TTS health check failed: {e}")
            return False

    def _test_connection(self):
        try:
            r = requests.get(self._health_url(), timeout=10)
            if r.status_code == 200:
                logger.debug(f"✅ Connected to TTS ({self.backend})")
            else:
                logger.warning(f"TTS ({self.backend}) returned status {r.status_code}")
        except Exception as e:
            logger.warning(f"Could not connect to TTS ({self.backend}): {e}")

    def get_timeout_info(self) -> Dict[str, Any]:
        return {
            "backend": self.backend,
            "timeout_seconds": self.timeout_seconds,
            "retry_delay": self.retry_delay,
            "max_attempts": self.max_attempts,
            "base_url": self.base_url,
        }

    # ---- public API -------------------------------------------------------
    def generate_speech(self, text: str, voice: str = "notebooklm") -> Optional[bytes]:
        """Generate a single WAV (bytes) for a `[S1]/[S2]` dialogue chunk."""
        if not text or not text.strip():
            logger.warning("Empty text provided for TTS")
            return None

        logger.info(f"🗣️ TTS({self.backend}): {text[:60].strip()}")
        for attempt in range(1, self.max_attempts + 1):
            try:
                if self.backend == "dia":
                    audio = self._synthesize_dia(text, voice, random.randint(1, 100000))
                else:
                    audio = self._synthesize_magpie_dialogue(text)
                if audio:
                    logger.debug(f"✅ TTS produced {len(audio)} bytes")
                    return audio
            except Exception as e:
                logger.warning(f"TTS attempt {attempt}/{self.max_attempts} failed: {e}")
                if attempt < self.max_attempts:
                    time.sleep(self.retry_delay)
        logger.error(f"TTS failed after {self.max_attempts} attempts")
        return None

    # ---- magpie backend ---------------------------------------------------
    def _synthesize_magpie_dialogue(self, text: str) -> Optional[bytes]:
        turns = self._parse_turns(self._clean_text_for_tts(text))
        if not turns:
            return None
        clips: List[bytes] = []
        for speaker, line in turns:
            if not line.strip():
                continue
            voice = S1_VOICE if speaker == "S1" else S2_VOICE
            clip = self._magpie_one(line, voice)
            if clip:
                clips.append(clip)
        return self._concat_wavs(clips, gap_ms=TURN_GAP_MS) if clips else None

    def _magpie_one(self, text: str, voice: str) -> Optional[bytes]:
        form = {
            "text": text,
            "voice": voice,
            "language": MAGPIE_LANGUAGE,
            "encoding": "LINEAR_PCM",
            "sample_rate_hz": str(MAGPIE_SAMPLE_RATE),
        }
        r = requests.post(
            f"{self.base_url}/v1/audio/synthesize", data=form, timeout=self.timeout_seconds
        )
        if r.status_code == 200 and r.content:
            return r.content
        logger.error(f"Magpie synthesize {r.status_code}: {r.text[:200]}")
        return None

    # ---- dia backend ------------------------------------------------------
    def _synthesize_dia(self, text: str, voice: str, seed: int) -> Optional[bytes]:
        """Original Dia `/generate` path: one call voices both [S1]/[S2]."""
        cleaned = self._clean_text_for_tts(text)
        full_text = cleaned + " \n[S1]"
        voice_sample_text = self._load_voice_sample_text(voice)
        voice_sample_audio_path = self._load_voice_sample_audio(voice)

        form_data = {
            "text": full_text,
            "audio_prompt_text": voice_sample_text or "",
            "max_new_tokens": 3072,
            "cfg_scale": 3.0,
            "temperature": 1.8,
            "top_p": 0.95,
            "cfg_filter_top_k": 45,
            "speed_factor": 1.0,
            "seed": seed,
        }
        files = None
        if voice_sample_audio_path and os.path.exists(voice_sample_audio_path):
            files = {
                "audio_prompt": ("sample.wav", open(voice_sample_audio_path, "rb"), "audio/wav")
            }
        try:
            r = requests.post(
                f"{self.base_url}/generate",
                data=form_data,
                files=files,
                timeout=self.timeout_seconds,
            )
            if r.status_code == 200:
                return r.content
            logger.error(f"Dia /generate {r.status_code}: {r.text[:200]}")
            return None
        finally:
            if files:
                files["audio_prompt"][1].close()

    def _load_voice_sample_text(self, voice: str) -> Optional[str]:
        try:
            p = Path("voices") / voice / "sample.txt"
            return p.read_text(encoding="utf-8").strip() if p.exists() else None
        except Exception as e:
            logger.warning(f"voice sample text load failed: {e}")
            return None

    def _load_voice_sample_audio(self, voice: str) -> Optional[str]:
        p = Path("voices") / voice / "sample.wav"
        return str(p) if p.exists() else None

    # ---- shared helpers ---------------------------------------------------
    @staticmethod
    def _parse_turns(text: str) -> List[Tuple[str, str]]:
        if "[S1]" not in text and "[S2]" not in text:
            return [("S1", text.strip())]
        turns: List[Tuple[str, str]] = []
        parts = re.split(r"(\[S[12]\])", text)
        current, buf = "S1", ""
        for p in parts:
            if p in ("[S1]", "[S2]"):
                if buf.strip():
                    turns.append((current, buf.strip()))
                current, buf = p[1:3], ""
            else:
                buf += p
        if buf.strip():
            turns.append((current, buf.strip()))
        return turns

    @staticmethod
    def _concat_wavs(clips: List[bytes], gap_ms: int = 0) -> bytes:
        out = io.BytesIO()
        writer: Optional[wave.Wave_write] = None
        params = None
        try:
            for clip in clips:
                with wave.open(io.BytesIO(clip), "rb") as w:
                    if writer is None:
                        params = w.getparams()
                        writer = wave.open(out, "wb")
                        writer.setparams(params)
                    writer.writeframes(w.readframes(w.getnframes()))
                if gap_ms > 0 and params is not None:
                    n = int(params.framerate * gap_ms / 1000)
                    writer.writeframes(b"\x00" * n * params.sampwidth * params.nchannels)
        finally:
            if writer is not None:
                writer.close()
        return out.getvalue()

    @staticmethod
    def _clean_text_for_tts(text: str) -> str:
        cleaned = text.replace("‑", "-")
        cleaned = cleaned.replace("“", '"').replace("”", '"')
        cleaned = cleaned.replace("‘", "'").replace("’", "'")
        cleaned = cleaned.replace("–", "-").replace("—", "-").replace("…", "...")
        cleaned = cleaned.replace("*", "")
        return cleaned
