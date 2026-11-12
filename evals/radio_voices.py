#!/usr/bin/env python3
"""What each voice and mood of the speech model does (issue #41).

Says one line in every voice asked for, and for each take reports its
length, median pitch, pitch spread, level and how much the level moves,
then has the speech recogniser transcribe it and scores the transcript
against the line. This is how the station knows that calm is slower and
not merely quieter, that a mood exists for one host and not another, and
that a voice from another language can be understood in English.

Usage:
    python evals/radio_voices.py                 every English voice and mood
    python evals/radio_voices.py VOICE [VOICE…]  the voices named, by full id

Reads the speech and recognition services; writes the takes to
outputs/evals/voices/.
"""

import io
import json
import os
import sys
import wave

import numpy as np
import requests

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from hnfm.audio.tts_api_service import TtsApiService  # noqa: E402
from hnfm.radio import qa  # noqa: E402

LINE = "I cannot believe they shipped it on a Friday. Nobody asked for this, and now the whole build is on fire."


def stats(wav: bytes) -> dict:
    w = wave.open(io.BytesIO(wav))
    sr = w.getframerate()
    x = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(float) / 32768
    if w.getnchannels() > 1:
        x = x.reshape(-1, w.getnchannels()).mean(1)
    n = int(sr * 0.04)
    f0, rms = [], []
    for i in range(0, len(x) - n, n // 2):
        fr = x[i:i + n]
        e = np.sqrt((fr ** 2).mean())
        rms.append(e)
        if e < 0.02:
            continue
        fr = fr - fr.mean()
        ac = np.correlate(fr, fr, "full")[n - 1:]
        lo, hi = sr // 400, sr // 70
        k = lo + int(np.argmax(ac[lo:hi]))
        if ac[k] > 0.4 * ac[0]:
            f0.append(sr / k)
    f0 = np.array(f0 or [0.0])
    rms = np.array(rms)
    return {"seconds": round(len(x) / sr, 2), "pitch_hz": int(np.median(f0)), "pitch_spread": int(f0.std()),
            "level_db": round(20 * np.log10(np.sqrt((x ** 2).mean()) + 1e-9), 1),
            "movement": round(float(rms.std() / (rms.mean() + 1e-9)), 2)}


def main() -> None:
    base = os.environ["TTS_BASE_URL"].rstrip("/")
    listed = requests.get(base + "/v1/audio/list_voices", timeout=10).json()
    every = sorted({v for x in listed.values() for v in (x.get("voices") or [])})
    voices = sys.argv[1:] or [v for v in every if ".EN-US." in v]
    out = os.path.join(os.getenv("OUTPUTS_DIR", "outputs"), "evals", "voices")
    os.makedirs(out, exist_ok=True)
    svc = TtsApiService(backend="magpie")
    for v in voices:
        wav = svc._magpie_one(LINE, v)
        if not wav:
            print(v, "no audio")
            continue
        with open(os.path.join(out, v.replace("Magpie-Multilingual.", "") + ".wav"), "wb") as f:
            f.write(wav)
        heard = qa.transcribe(wav)
        row = {**stats(wav), "match": round(qa.match(LINE, heard), 2) if heard else None}
        print(f"{v.replace('Magpie-Multilingual.', ''):22s} {json.dumps(row)}", flush=True)


if __name__ == "__main__":
    main()
