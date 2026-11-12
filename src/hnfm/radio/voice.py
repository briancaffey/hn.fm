"""A line, spoken by one of the station's voices.

Six hosts and a pool of callers, all NVIDIA Magpie voices. Hosts come in
moods the server lists as sub-voices ("…Mia.Calm"); a mood the server
does not have falls back to the plain voice. Every spoken line is kept on
disk under a name made from the voice and the words, so nothing is
synthesised twice.
"""

import logging
import os
from typing import List, Optional

from .copy import speakable

logger = logging.getLogger(__name__)

# name -> (engine, base voice, how it sounds)
HOSTS = {
    "mia":   ("magpie", "Magpie-Multilingual.EN-US.Mia",   "warm, quick, easily delighted"),
    "jason": ("magpie", "Magpie-Multilingual.EN-US.Jason", "low, unhurried, understated"),
    "sofia": ("magpie", "Magpie-Multilingual.EN-US.Sofia", "exact and brisk, a newsreader"),
    "leo":   ("magpie", "Magpie-Multilingual.EN-US.Leo",   "deadpan; gets the dry line"),
    "aria":  ("magpie", "Magpie-Multilingual.EN-US.Aria",  "clear and even; explains how things work"),
    "ray":   ("magpie", "Magpie-Multilingual.EN-US.Ray",   "deep and slow; in no hurry"),
}
# Callers are the voices no host uses, so a caller never sounds like the
# person they are talking to. Which caller gets which voice turns with the
# piece, so line one is not the same person all day.
CALLER_VOICES = (
    "Magpie-Multilingual.EN-US.Diego", "Magpie-Multilingual.EN-US.Isabela",
    "Magpie-Multilingual.EN-US.Pascal", "Magpie-Multilingual.EN-US.Louise",
)
DEFAULT_HOST = "mia"
# "default" is the voice as the server gives it: the most natural one, and
# the station's house sound. The old house mood was Calm, which made every
# host sound sedated; calm is now a choice the writer makes for one line.
DEFAULT_MOOD = os.getenv("RADIO_DEFAULT_MOOD", "default")
MOODS = ("default", "calm", "neutral", "sad", "angry")

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


def is_caller(speaker: str) -> bool:
    return (speaker or "").startswith("caller")


def voice_name(host: str, mood: Optional[str] = None, seed: int = 0) -> str:
    if is_caller(host):
        n = int("".join(c for c in host if c.isdigit()) or 1)
        return CALLER_VOICES[(n - 1 + seed) % len(CALLER_VOICES)]
    engine, base, _ = HOSTS.get(host) or HOSTS[DEFAULT_HOST]
    mood = (mood or DEFAULT_MOOD or "").strip().lower()
    if mood and mood != "default":
        candidate = f"{base}.{mood.capitalize()}"
        voices = available_voices()
        if not voices or candidate in voices:
            return candidate
    return base


def cache_path(voice: str, text: str) -> str:
    """Where a spoken line lives: named by what was said and who said it,
    so the same line in the same voice is synthesised once (issue #33)."""
    import hashlib

    from . import radio_root

    h = hashlib.sha1(f"{voice}\n{text}".encode("utf-8")).hexdigest()
    d = os.path.join(radio_root(), "cache", "voice", h[:2])
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, f"{h}.wav")


def speak(text: str, speaker: str, mood: Optional[str] = None, seed: int = 0,
          fresh: bool = False) -> Optional[bytes]:
    """`text` in `speaker`'s voice, as WAV bytes, from the cache when this
    exact line has been said before. `fresh` skips the cache (a retry
    after a failed round trip must not get the same bad take back)."""
    from ..audio.tts_api_service import TtsApiService

    text = speakable(" ".join((text or "").split()))
    if not text:
        return None
    voice = voice_name(speaker, mood, seed)
    path = cache_path(voice, text)
    if not fresh and os.path.exists(path) and os.path.getsize(path) > 1000:
        with open(path, "rb") as f:
            return f.read()
    try:
        svc = TtsApiService(backend="magpie")
        wav = svc._magpie_one(text, voice)
        if not wav and voice != voice_name(speaker, "default", seed):
            wav = svc._magpie_one(text, voice_name(speaker, "default", seed))
    except Exception as e:
        logger.warning(f"radio voice ({speaker}) failed: {e}")
        return None
    if wav:
        tmp = path + ".tmp"
        with open(tmp, "wb") as f:
            f.write(wav)
        os.replace(tmp, path)
    return wav


def host_listing() -> str:
    return "\n".join(f"- {k}: {desc}" for k, (_e, _v, desc) in HOSTS.items())


def say(text: str, host: str, out_mp3: str, mood: Optional[str] = None,
        bed: Optional[str] = None) -> Optional[str]:
    """One line by one host straight to an MP3, optionally over a bed: the
    station IDs and the time check. Pieces go through the booth."""
    import tempfile

    from . import mix

    wav = speak(text, host, mood)
    if not wav:
        return None
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        f.write(wav)
        tmp = f.name
    try:
        ok = mix.over_bed(tmp, bed, out_mp3) if bed and os.path.exists(bed) else mix.plain(tmp, out_mp3)
    finally:
        try:
            os.unlink(tmp)
        except OSError:
            pass
    return out_mp3 if ok else None
