"""System health checker for hn.fm pipeline."""

import requests
import logging
import time
from typing import Dict, List, Tuple
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class ServiceStatus:
    """Represents the status of a service."""

    name: str
    url: str
    status: str  # "online", "offline", "error"
    response_time: float
    error_message: str = None
    details: Dict = None


class SystemChecker:
    """Checks the health of all required services."""

    def __init__(self):
        """Initialize the system checker."""
        self.timeout = 10  # seconds

    def check_all_services(self) -> Tuple[bool, List[ServiceStatus]]:
        """Check all required services.

        Returns:
            Tuple of (all_healthy, list_of_service_statuses)
        """
        services = [
            ("Local LLM", self._check_local_llm),
            ("Firecrawl", self._check_firecrawl),
            ("Gradio TTS", self._check_gradio_tts),
            ("Studio Voice", self._check_studio_voice),
            ("ASR Service", self._check_asr_service),
            ("Image Generation", self._check_image_generation),
        ]

        results = []
        all_healthy = True

        for service_name, check_func in services:
            try:
                status = check_func()
                results.append(status)
                if status.status != "online":
                    all_healthy = False
            except Exception as e:
                logger.error(f"Error checking {service_name}: {e}")
                status = ServiceStatus(
                    name=service_name,
                    url="unknown",
                    status="error",
                    response_time=0.0,
                    error_message=str(e)
                )
                results.append(status)
                all_healthy = False

        return all_healthy, results

    def _check_local_llm(self) -> ServiceStatus:
        """Check local LLM service."""
        from ..utils.config import config_manager

        base_url = config_manager.get("llm.base_url")
        if not base_url:
            return ServiceStatus(
                name="Local LLM",
                url="not configured",
                status="offline",
                response_time=0.0,
                error_message="LLM base URL not configured"
            )

        try:
            start_time = time.time()
            response = requests.get(f"{base_url}/v1/models", timeout=self.timeout)
            response_time = time.time() - start_time

            if response.status_code == 200:
                models = response.json().get("data", [])
                return ServiceStatus(
                    name="Local LLM",
                    url=base_url,
                    status="online",
                    response_time=response_time,
                    details={"models": len(models)}
                )
            else:
                return ServiceStatus(
                    name="Local LLM",
                    url=base_url,
                    status="offline",
                    response_time=response_time,
                    error_message=f"HTTP {response.status_code}"
                )

        except requests.exceptions.RequestException as e:
            return ServiceStatus(
                name="Local LLM",
                url=base_url,
                status="offline",
                response_time=0.0,
                error_message=str(e)
            )

    def _check_firecrawl(self) -> ServiceStatus:
        """Check Firecrawl service."""
        from ..utils.config import config_manager

        base_url = config_manager.get("apis.firecrawl.base_url")
        if not base_url:
            return ServiceStatus(
                name="Firecrawl",
                url="not configured",
                status="offline",
                response_time=0.0,
                error_message="Firecrawl base URL not configured"
            )

        try:
            start_time = time.time()
            # Try a simple GET request to the root endpoint
            response = requests.get(base_url, timeout=self.timeout)
            response_time = time.time() - start_time

            if response.status_code == 200:
                return ServiceStatus(
                    name="Firecrawl",
                    url=base_url,
                    status="online",
                    response_time=response_time,
                    details={"response": response.text[:100] + "..." if len(response.text) > 100 else response.text}
                )
            else:
                return ServiceStatus(
                    name="Firecrawl",
                    url=base_url,
                    status="offline",
                    response_time=response_time,
                    error_message=f"HTTP {response.status_code}"
                )

        except requests.exceptions.RequestException as e:
            return ServiceStatus(
                name="Firecrawl",
                url=base_url,
                status="offline",
                response_time=0.0,
                error_message=str(e)
            )

    def _check_gradio_tts(self) -> ServiceStatus:
        """Check Gradio TTS service."""
        from ..utils.config import config_manager

        base_url = config_manager.get("tts.base_url")
        if not base_url:
            return ServiceStatus(
                name="Gradio TTS",
                url="not configured",
                status="offline",
                response_time=0.0,
                error_message="TTS base URL not configured"
            )

        try:
            start_time = time.time()
            # Try to access the Gradio interface
            response = requests.get(base_url, timeout=self.timeout)
            response_time = time.time() - start_time

            if response.status_code == 200:
                return ServiceStatus(
                    name="Gradio TTS",
                    url=base_url,
                    status="online",
                    response_time=response_time,
                    details={"response": "Gradio interface accessible"}
                )
            else:
                return ServiceStatus(
                    name="Gradio TTS",
                    url=base_url,
                    status="offline",
                    response_time=response_time,
                    error_message=f"HTTP {response.status_code}"
                )

        except requests.exceptions.RequestException as e:
            return ServiceStatus(
                name="Gradio TTS",
                url=base_url,
                status="offline",
                response_time=0.0,
                error_message=str(e)
            )

    def _check_studio_voice(self) -> ServiceStatus:
        """Check Studio Voice service."""
        from ..utils.config import config_manager

        # Get the HTTP health endpoint URL from config
        health_url = config_manager.get("studio_voice.http_health_url")
        if not health_url:
            # Fallback to environment variable
            import os
            health_url = os.getenv("STUDIO_VOICE_HTTP_HEALTH_URL")

        if not health_url:
            return ServiceStatus(
                name="Studio Voice",
                url="not configured",
                status="offline",
                response_time=0.0,
                error_message="Studio Voice HTTP health URL not configured"
            )

        try:
            start_time = time.time()
            response = requests.get(health_url, timeout=self.timeout)
            response_time = time.time() - start_time

            if response.status_code == 200:
                return ServiceStatus(
                    name="Studio Voice",
                    url=health_url,
                    status="online",
                    response_time=response_time,
                    details={"health_endpoint": health_url, "response": response.text[:100] + "..." if len(response.text) > 100 else response.text}
                )
            else:
                return ServiceStatus(
                    name="Studio Voice",
                    url=health_url,
                    status="offline",
                    response_time=response_time,
                    error_message=f"HTTP {response.status_code}"
                )

        except requests.exceptions.RequestException as e:
            return ServiceStatus(
                name="Studio Voice",
                url=health_url,
                status="offline",
                response_time=0.0,
                error_message=str(e)
            )

    def _check_asr_service(self) -> ServiceStatus:
        """Check ASR service (WhisperX)."""
        from ..utils.config import config_manager

        base_url = config_manager.get("asr.base_url")
        if not base_url:
            return ServiceStatus(
                name="ASR Service",
                url="not configured",
                status="offline",
                response_time=0.0,
                error_message="ASR base URL not configured"
            )

        try:
            start_time = time.time()
            response = requests.get(f"{base_url}/health", timeout=self.timeout)
            response_time = time.time() - start_time

            if response.status_code == 200:
                return ServiceStatus(
                    name="ASR Service",
                    url=base_url,
                    status="online",
                    response_time=response_time,
                    details={"health_endpoint": f"{base_url}/health", "response": response.text[:100] + "..." if len(response.text) > 100 else response.text}
                )
            else:
                return ServiceStatus(
                    name="ASR Service",
                    url=base_url,
                    status="offline",
                    response_time=response_time,
                    error_message=f"HTTP {response.status_code}"
                )

        except requests.exceptions.RequestException as e:
            return ServiceStatus(
                name="ASR Service",
                url=base_url,
                status="offline",
                response_time=0.0,
                error_message=str(e)
            )

    def _check_image_generation(self) -> ServiceStatus:
        """Check Image Generation service (Flux NIM)."""
        from ..utils.config import config_manager

        base_url = config_manager.get("image_generation.base_url")
        if not base_url:
            return ServiceStatus(
                name="Image Generation",
                url="not configured",
                status="offline",
                response_time=0.0,
                error_message="Image generation base URL not configured"
            )

        try:
            start_time = time.time()
            # Use the health endpoint that the ImageGenerationService expects
            response = requests.get(f"{base_url}/v1/health/ready", timeout=self.timeout)
            response_time = time.time() - start_time

            if response.status_code == 200:
                return ServiceStatus(
                    name="Image Generation",
                    url=base_url,
                    status="online",
                    response_time=response_time,
                    details={"health_endpoint": f"{base_url}/v1/health/ready", "response": response.text[:100] + "..." if len(response.text) > 100 else response.text}
                )
            else:
                return ServiceStatus(
                    name="Image Generation",
                    url=base_url,
                    status="offline",
                    response_time=response_time,
                    error_message=f"HTTP {response.status_code}"
                )

        except requests.exceptions.RequestException as e:
            return ServiceStatus(
                name="Image Generation",
                url=base_url,
                status="offline",
                response_time=0.0,
                error_message=str(e)
            )
