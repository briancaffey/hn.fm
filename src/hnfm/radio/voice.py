"""A line, spoken by one of the station's hosts (plans/20).

Hosts are presets over the two engines the pipeline already runs: NVIDIA
Magpie voices, and Dia with a cloned sample. Magpie voices come in moods —
Neutral, Calm, Sad, Angry — served as sub-voices ("…Mia.Calm"). Calm is
the station's house mood: it is what radio sounds like at night. The
producer may ask for another; anything the server does not have falls
back to the base voice.
"""

import logging
import os
import tempfile
from typing import Dict, List, Optional

from .library import mix_under, to_mp3

logger = logging.getLogger(__name__)

# name -> (engine, base voice, how it sounds — the producer reads the description)
HOSTS = {
    "mia":   ("magpie", "Magpie-Multilingual.EN-US.Mia",   "warm, quick, the morning host"),
    "jason": ("magpie", "Magpie-Multilingual.EN-US.Jason", "low, unhurried, the evening host"),
    "sofia": ("magpie", "Magpie-Multilingual.EN-US.Sofia", "bright, precise, reads the time and the news"),
    "leo":   ("magpie", "Magpie-Multilingual.EN-US.Leo",   "dry, amused, the one for the odd story"),
    "aria":  ("magpie", "Magpie-Multilingual.EN-US.Aria",  "clear, even, good for the quick items"),
    "ray":   ("magpie", "Magpie-Multilingual.EN-US.Ray",   "deep and slow, the late-night voice"),
    "dia":   ("dia",    os.getenv("RADIO_DIA_VOICE", "notebooklm"), "the cloned house voice, conversational"),
}
DEFAULT_HOST = "mia"
DEFAULT_MOOD = os.getenv("RADIO_DEFAULT_MOOD", "calm")
MOODS = ("calm", "neutral", "sad", "angry")

_VOICES: Optional[List[str]] = None


def available_voices() -> List[str]:
    """The Magpie server's own list, fetched once per process."""
    global _VOICES
    if _VOICES is not None:
        return _VOICES
    try:
        import requests
        from ..utils.config import config_manager

        base = (os.getenv("TTS_BASE_URL") or config_manager.get("tts.base_url", "")).rstrip("/")
        r = requests.get(f"{base}/v1/audio/list_voices", timeout=8).json()
        _VOICES = sorted({v for vs in r.values() for v in (vs.get("voices") or [])})
    except Exception as e:
        logger.debug(f"radio voices: list unavailable ({e})")
        _VOICES = []
    return _VOICES


def voice_name(host: str, mood: Optional[str] = None) -> str:
    engine, base, _ = HOSTS.get(host) or HOSTS[DEFAULT_HOST]
    if engine != "magpie":
        return base
    mood = (mood or DEFAULT_MOOD or "").strip().lower()
    if mood and mood != "default":
        candidate = f"{base}.{mood.capitalize()}"
        voices = available_voices()
        if not voices or candidate in voices:
            return candidate
    return base


def host_listing() -> str:
    return "\n".join(f"- {k}: {desc}" for k, (_e, _v, desc) in HOSTS.items()) + \
        "\nMoods (Magpie hosts): calm (the house sound), neutral, sad. Use calm unless the line needs otherwise."


def say(text: str, host: str, out_mp3: str, mood: Optional[str] = None,
        bed: Optional[str] = None, bed_db: float = -17.0) -> Optional[str]:
    """Speak `text` as `host` into `out_mp3`, optionally over a quiet bed.
    None on any failure."""
    from ..audio.tts_api_service import TtsApiService

    engine, _base, _ = HOSTS.get(host) or HOSTS[DEFAULT_HOST]
    text = " ".join((text or "").split())
    if not text:
        return None
    try:
        svc = TtsApiService(backend=engine)
        if engine == "magpie":
            wav = svc._magpie_one(text, voice_name(host, mood))
            if not wav and mood:
                wav = svc._magpie_one(text, voice_name(host, "default"))
        else:
            wav = svc._synthesize_dia(f"[S1] {text}", HOSTS["dia"][1], 7)
    except Exception as e:
        logger.warning(f"radio voice ({host}) failed: {e}")
        return None
    if not wav:
        return None
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        f.write(wav)
        tmp = f.name
    try:
        if bed and os.path.exists(bed):
            ok = mix_under(tmp, bed, out_mp3, bed_db=bed_db)
        else:
            ok = to_mp3(tmp, out_mp3)
    finally:
        try:
            os.unlink(tmp)
        except OSError:
            pass
    return out_mp3 if ok else None
