"""audio/levels: every voice clip lands at one loudness."""

import io
import math
import struct
import wave

import pytest

from hnfm.audio import levels


def _tone(db: float, seconds: float = 3.0, rate: int = 22050) -> bytes:
    amp = 32767 * 10 ** (db / 20)
    out = io.BytesIO()
    with wave.open(out, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(rate)
        w.writeframes(b"".join(struct.pack("<h", int(amp * math.sin(2 * math.pi * 440 * i / rate)))
                               for i in range(int(rate * seconds))))
    return out.getvalue()


@pytest.mark.skipif(levels.measure(_tone(-20)) is None, reason="ffmpeg not available")
class TestMatch:
    def test_a_quiet_and_a_loud_clip_meet_at_the_target(self):
        quiet, loud = levels.match(_tone(-30), target=-19), levels.match(_tone(-6), target=-19)
        assert abs(levels.measure(quiet)["lufs"] - levels.measure(loud)["lufs"]) < 1.0
        assert abs(levels.measure(quiet)["lufs"] - (-19)) < 1.0

    def test_the_peak_ceiling_holds(self):
        out = levels.match(_tone(-40), target=0)
        assert levels.measure(out)["peak"] <= levels.PEAK_CEILING_DB + 0.2

    def test_silence_is_left_alone(self):
        s = _tone(-90)
        assert levels.match(s) == s

    def test_off_switch(self, monkeypatch):
        monkeypatch.setenv("TTS_NORMALIZE", "false")
        s = _tone(-30)
        assert levels.match(s) is s
