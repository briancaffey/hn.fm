"""A line, spoken by one of the station's hosts (plans/20).

Hosts are presets over the two engines the pipeline already runs: NVIDIA
Magpie voices, and Dia with a cloned sample. The producer picks a host by
name; this module turns that into an engine, a voice, and an MP3 at the
station's loudness.
"""

import logging
import os
import tempfile
from typing import Optional

from .library import to_mp3

logger = logging.getLogger(__name__)

# name -> (engine, voice, how it sounds — the producer reads the description)
HOSTS = {
    "mia":   ("magpie", "Magpie-Multilingual.EN-US.Mia",   "warm, quick, the morning host"),
    "jason": ("magpie", "Magpie-Multilingual.EN-US.Jason", "low, unhurried, the evening host"),
    "sofia": ("magpie", "Magpie-Multilingual.EN-US.Sofia", "bright, precise, reads the time and the news"),
    "leo":   ("magpie", "Magpie-Multilingual.EN-US.Leo",   "dry, amused, the one for the odd story"),
    "dia":   ("dia",    os.getenv("RADIO_DIA_VOICE", "notebooklm"), "the cloned house voice, conversational"),
}
DEFAULT_HOST = "mia"


def host_listing() -> str:
    return "\n".join(f"- {k}: {desc}" for k, (_e, _v, desc) in HOSTS.items())


def say(text: str, host: str, out_mp3: str) -> Optional[str]:
    """Speak `text` as `host` into `out_mp3`. None on any failure."""
    from ..audio.tts_api_service import TtsApiService

    engine, voice, _ = HOSTS.get(host) or HOSTS[DEFAULT_HOST]
    text = " ".join((text or "").split())
    if not text:
        return None
    try:
        svc = TtsApiService(backend=engine)
        if engine == "magpie":
            wav = svc._magpie_one(text, voice)
        else:
            wav = svc._synthesize_dia(f"[S1] {text}", voice, 7)
    except Exception as e:
        logger.warning(f"radio voice ({host}) failed: {e}")
        return None
    if not wav:
        return None
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        f.write(wav)
        tmp = f.name
    ok = to_mp3(tmp, out_mp3)
    try:
        os.unlink(tmp)
    except OSError:
        pass
    return out_mp3 if ok else None
