"""Sound design: effects and voice treatments (issue #40).

Everything here is synthesised by ffmpeg from sine waves and noise, so an
effect costs no model, is the same every time, and can be read as text.
An effect is made once and kept under `fx/`; a treatment is a filter chain
applied to a voice clip while the piece is joined.

    path(name)          the effect as a WAV file, made on first use
    treatment(role)     the filter chain for a voice in that role
    EFFECTS, TREATMENTS the catalogue, for the audition page and the tests

The model never chooses an effect. Segments name theirs in the spec
(`segments.py`) and the booth places them.
"""

import logging
import os
import subprocess
from dataclasses import dataclass
from typing import Dict, Optional

logger = logging.getLogger(__name__)

RATE = 44100
# Bump when a recipe changes: the cached files are named with it.
VERSION = 1


@dataclass(frozen=True)
class Effect:
    key: str
    name: str
    what: str          # what it is for, in plain words
    source: str        # an ffmpeg lavfi source
    chain: str = ""    # filters applied to it
    seconds: float = 1.0


def _tone(expr: str, d: float) -> str:
    return f"aevalsrc='{expr}':s={RATE}:d={d}"


_E = Effect
EFFECTS: Dict[str, Effect] = {e.key: e for e in (
    _E("pips", "The pips", "Top of the hour: three short pips and a long one, before the bulletin.",
       _tone("0.5*sin(2*PI*1000*t)*(lt(mod(t,0.5),0.1)*lt(t,1.5)+gte(t,1.5)*lt(t,2.1))", 2.3),
       "afade=t=out:st=2.05:d=0.05", 2.3),
    _E("whoosh", "Whoosh", "A pass of air: into a sweeper, or between the clips of a teaser.",
       "anoisesrc=d=0.9:color=pink:amplitude=0.7:seed=7",
       "highpass=f=350,flanger=delay=4:depth=7:speed=1.4:width=80,"
       "afade=t=in:d=0.55:curve=exp,afade=t=out:st=0.58:d=0.32,volume=1.6", 0.9),
    _E("riser", "Riser", "A rising tone that says something is about to start.",
       _tone("0.22*sin(2*PI*(180*t+260*t*t))+0.12*sin(2*PI*(360*t+520*t*t))+0.10*(random(0)*2-1)*t/1.6", 1.6),
       "highpass=f=120,tremolo=f=11:d=0.35,afade=t=in:d=1.2:curve=qsin,afade=t=out:st=1.52:d=0.08", 1.6),
    _E("impact", "Impact", "A low hit with a tail: the full stop after a sweeper or a number one.",
       _tone("0.9*sin(2*PI*52*t)*exp(-4.5*t)+0.35*(random(0)*2-1)*exp(-38*t)", 1.4),
       "aecho=0.8:0.6:70|130:0.3|0.18,lowpass=f=5000,afade=t=out:st=1.0:d=0.4", 1.4),
    _E("ring", "Phone ringing", "Two rings on the line before a caller is put through.",
       _tone("0.22*(sin(2*PI*400*t)+sin(2*PI*450*t))*lt(mod(t,0.62),0.4)*lt(t,1.24)", 1.35),
       "highpass=f=300,lowpass=f=3200", 1.35),
    _E("pickup", "Pick-up", "The click of a line being opened.",
       _tone("0.6*(random(0)*2-1)*exp(-90*t)+0.012*(random(1)*2-1)", 0.3),
       "highpass=f=400,lowpass=f=3400", 0.3),
    _E("hangup", "Hang-up", "A click and a breath of dial tone as the caller goes.",
       _tone("0.5*(random(0)*2-1)*exp(-90*t)+0.10*(sin(2*PI*350*t)+sin(2*PI*440*t))*gte(t,0.08)", 0.5),
       "highpass=f=300,lowpass=f=3200,afade=t=out:st=0.4:d=0.1", 0.5),
    _E("static", "Static", "A burst between stations: into a correspondent's line.",
       "anoisesrc=d=0.45:color=white:amplitude=0.5:seed=3",
       "bandpass=f=2200:width_type=h:w=1800,acrusher=bits=6:mix=0.5,tremolo=f=23:d=0.7,"
       "afade=t=in:d=0.04,afade=t=out:st=0.33:d=0.12", 0.45),
    _E("teletype", "Teletype", "A wire machine: news is coming in.",
       _tone("0.5*(random(0)*2-1)*lt(mod(t,0.083),0.011)", 1.3),
       "highpass=f=1400,lowpass=f=7000,afade=t=out:st=1.1:d=0.2", 1.3),
    _E("blip", "Blip", "A two-note marker between the entries of a list.",
       _tone("0.3*sin(2*PI*880*t)*lt(t,0.07)+0.3*sin(2*PI*1320*t)*gte(t,0.09)*lt(t,0.2)", 0.3),
       "afade=t=out:st=0.17:d=0.05", 0.3),
    _E("tick", "Tick", "One soft tick: the beat between the lines of a bulletin.",
       _tone("0.5*sin(2*PI*1800*t)*exp(-70*t)", 0.18), "", 0.18),
    _E("roll", "Roll", "A short drum roll into the last entry of a countdown.",
       _tone("0.5*(random(0)*2-1)*lt(mod(t,0.047),0.02)*(0.25+0.75*t/1.2)", 1.2),
       "bandpass=f=1800:width_type=h:w=2400,afade=t=out:st=1.15:d=0.05", 1.2),
)}

# How a voice sounds, by where it is speaking from. Each is a chain of
# ffmpeg filters applied to a mono clip already at the station's rate.
TREATMENTS: Dict[str, dict] = {
    "studio": {
        "name": "Studio",
        "what": "A host at the desk: rumble out, a little presence, gentle compression.",
        "chain": "highpass=f=75,equalizer=f=220:t=q:w=1:g=-1.5,equalizer=f=3600:t=q:w=1.2:g=2,"
                 "acompressor=threshold=0.12:ratio=3:attack=8:release=140:makeup=1.4",
    },
    "big": {
        "name": "Big voice",
        "what": "The station's imaging voice: a touch lower, squeezed hard, with a short room behind it.",
        "chain": f"asetrate={RATE}*0.94,aresample={RATE},atempo=1.0638,"
                 "highpass=f=60,equalizer=f=140:t=q:w=1:g=4,equalizer=f=4200:t=q:w=1:g=3,"
                 "acompressor=threshold=0.05:ratio=8:attack=3:release=90:makeup=2.2,"
                 "aecho=0.85:0.7:55|95:0.22|0.12",
    },
    "phone": {
        "name": "Phone line",
        "what": "A caller: the band a telephone carries, squashed, a little dirty.",
        "chain": "highpass=f=320,lowpass=f=3300,"
                 "acompressor=threshold=0.08:ratio=6:attack=5:release=80:makeup=2,"
                 "acrusher=bits=9:mix=0.25,volume=0.9",
    },
    "field": {
        "name": "Field line",
        "what": "A correspondent away from the studio: narrower than the desk, wider than a phone.",
        "chain": "highpass=f=180,lowpass=f=5200,equalizer=f=1800:t=q:w=1:g=3,"
                 "acompressor=threshold=0.09:ratio=5:attack=5:release=100:makeup=1.8,"
                 "aecho=0.9:0.5:28:0.12",
    },
    "fineprint": {
        "name": "Fine print",
        "what": "The end of an advert, read a third faster and a little quieter.",
        "chain": "atempo=1.32,highpass=f=120,volume=0.85",
    },
    "tape": {
        "name": "Archive tape",
        "what": "Something played back from an old recording.",
        "chain": "highpass=f=450,lowpass=f=2700,vibrato=f=3.5:d=0.12,"
                 "acompressor=threshold=0.1:ratio=4:attack=5:release=80:makeup=1.6",
    },
}


def treatment(role: Optional[str]) -> str:
    """The filter chain for a role; an unknown role gets the studio."""
    return (TREATMENTS.get(role or "studio") or TREATMENTS["studio"])["chain"]


def effect_command(e: Effect, dst: str) -> list:
    """The ffmpeg command that makes an effect (pure: a test can read it)."""
    cmd = ["ffmpeg", "-nostdin", "-y", "-v", "error", "-f", "lavfi", "-i", e.source]
    chain = ",".join(x for x in (e.chain, f"aresample={RATE}", "aformat=channel_layouts=mono") if x)
    return cmd + ["-af", chain, "-t", str(e.seconds), dst]


def fx_dir() -> str:
    from . import radio_root

    d = os.path.join(radio_root(), "fx")
    os.makedirs(d, exist_ok=True)
    return d


def path(key: str) -> Optional[str]:
    """The effect as a WAV, made on first use. None for an unknown name or
    if ffmpeg could not make it: a missing effect is left out, never fatal."""
    e = EFFECTS.get(key)
    if not e:
        return None
    dst = os.path.join(fx_dir(), f"{key}.v{VERSION}.wav")
    if os.path.exists(dst) and os.path.getsize(dst) > 500:
        return dst
    tmp = dst + ".tmp.wav"
    res = subprocess.run(effect_command(e, tmp), capture_output=True, text=True)
    if res.returncode != 0 or not os.path.exists(tmp) or os.path.getsize(tmp) < 500:
        logger.warning(f"radio fx: could not make {key}: {res.stderr[-200:]}")
        return None
    os.replace(tmp, dst)
    return dst


def catalogue() -> dict:
    """Everything the station can do to sound, for the audition page."""
    return {
        "effects": [{"key": e.key, "name": e.name, "what": e.what, "seconds": e.seconds} for e in EFFECTS.values()],
        "treatments": [{"key": k, "name": t["name"], "what": t["what"]} for k, t in TREATMENTS.items()],
    }
