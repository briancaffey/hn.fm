"""Single source of truth for the AI backends hn.fm talks to.

Everything is driven by environment variables so you can repoint, enable, or
disable a service **between runs** without touching code. The health checker
(`/api/services/status`) and the pipeline both read this registry, so the
Services page always reflects what's actually wired.

To change a backend: set the env var (e.g. `TTS_BACKEND`, `IMAGE_GENERATION_BASE_URL`,
`MUSIC_ENABLED`) and restart the worker/web. The Services page updates to match.
"""

import os
from dataclasses import dataclass
from typing import List, Optional


def _bool(name: str, default: bool = False) -> bool:
    return str(os.getenv(name, str(default))).strip().lower() in ("1", "true", "yes", "on")


@dataclass
class ServiceSpec:
    name: str               # display name
    role: str               # LLM | Scrape | TTS | Image | ASR | Music | Enhance
    base_url: str           # service base
    health_path: str        # appended to base_url for the health probe
    enabled: bool = True     # disabled services show as "disabled", not "offline"
    auth_env: Optional[str] = None        # env var holding a bearer token
    expect_json_key: Optional[str] = None  # require this key in a 200 JSON body
    note: str = ""          # extra context (model name, backend, etc.)
    optional: bool = False  # if True, an offline status doesn't fail "all_healthy"


def get_service_specs() -> List[ServiceSpec]:
    """Build the live list of services from the current environment."""
    tts_backend = os.getenv("TTS_BACKEND", "magpie").lower()
    tts_health = "/v1/health/ready" if tts_backend == "magpie" else "/health"

    return [
        ServiceSpec(
            name="LLM · LiteLLM",
            role="LLM",
            base_url=os.getenv("LLM_BASE_URL", "").rstrip("/"),
            health_path="/models",
            auth_env="OPENAI_API_KEY",
            expect_json_key="data",
            note=os.getenv("LLM_MODEL", ""),
        ),
        ServiceSpec(
            name="Scrape · Firecrawl",
            role="Scrape",
            base_url=os.getenv("FIRECRAWL_BASE_URL", "").rstrip("/"),
            health_path="/health",
            optional=True,  # pipeline degrades to HN title/text if scrape is down
        ),
        ServiceSpec(
            name=f"TTS · {tts_backend.capitalize()}",
            role="TTS",
            base_url=os.getenv("TTS_BASE_URL", "").rstrip("/"),
            health_path=tts_health,
            note="voices: Mia / Jason" if tts_backend == "magpie" else "",
        ),
        ServiceSpec(
            name="Image · flux2-klein",
            role="Image",
            base_url=os.getenv("IMAGE_GENERATION_BASE_URL", "").rstrip("/"),
            health_path="/v1/health",
            note=os.getenv("IMAGE_GENERATION_BACKEND", "NIM"),
        ),
        ServiceSpec(
            name="ASR · Nemotron",
            role="ASR",
            base_url=os.getenv("ASR_BASE_URL", "").rstrip("/"),
            health_path="/healthz",
            enabled=_bool("ASR_ENABLED", True),
            optional=True,  # subtitles/QA degrade gracefully without it
            note="word timing + QA",
        ),
        ServiceSpec(
            name="Music · ACE-Step",
            role="Music",
            base_url=os.getenv("ACESTEP_BASE_URL", "").rstrip("/"),
            health_path="/health",
            enabled=_bool("MUSIC_ENABLED", False),
            optional=True,
        ),
        ServiceSpec(
            name="Audio enhance · Studio Voice",
            role="Enhance",
            base_url=(os.getenv("STUDIO_VOICE_HTTP_HEALTH_URL", "") or "").rstrip("/"),
            health_path="",
            enabled=_bool("STUDIO_VOICE_ENABLED", False),
            optional=True,
        ),
    ]
