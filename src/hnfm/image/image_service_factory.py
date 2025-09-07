"""Factory for creating image generation services."""

import logging
from typing import Union

from ..utils.config import config_manager
from .invokeai_image_service import InvokeAIImageService

logger = logging.getLogger(__name__)


class ImageServiceFactory:
    """Factory for creating image generation services based on configuration."""

    @staticmethod
    def create_image_service() -> Union["ImageGenerationService", InvokeAIImageService]:
        """Create an image generation service based on configuration.

        Returns:
            Image generation service instance (NIM or InvokeAI)

        Raises:
            ValueError: If the configured backend is not supported
        """
        try:
            backend = config_manager.get("image_generation.backend", "NIM").upper()

            # Handle case where environment variable is not set
            if backend.startswith("${") and backend.endswith("}"):
                raise ValueError(
                    f"Image generation backend not configured. Please set IMAGE_GENERATION_BACKEND environment variable to either 'NIM' or 'INVOKEAI'"
                )

            logger.info(f"Creating image generation service with backend: {backend}")

            if backend == "NIM":
                from ..video.image_generator import ImageGenerationService
                return ImageGenerationService()
            elif backend == "INVOKEAI":
                return InvokeAIImageService()
            else:
                raise ValueError(
                    f"Unsupported image generation backend: {backend}. Supported backends: NIM, INVOKEAI"
                )
        except Exception as e:
            logger.error(f"Failed to create image generation service: {e}")
            raise RuntimeError(f"Failed to create image generation service: {e}")

    @staticmethod
    def get_health_check_url() -> str:
        """Get the health check URL for the configured backend.

        Returns:
            Health check URL for the configured backend
        """
        backend = config_manager.get("image_generation.backend", "NIM").upper()

        # Handle case where environment variable is not set
        if backend.startswith("${") and backend.endswith("}"):
            return None

        if backend == "NIM":
            base_url = config_manager.get("image_generation.base_url")
            return f"{base_url}/v1/health/ready" if base_url else None
        elif backend == "INVOKEAI":
            invokeai_config = config_manager.get("image_generation.invokeai", {})
            base_url = invokeai_config.get("base_url", "http://127.0.0.1:9090")
            return f"{base_url}/api/v1/queue/default/status"
        else:
            return None

    @staticmethod
    def get_service_name() -> str:
        """Get the name of the configured service.

        Returns:
            Service name for display purposes
        """
        backend = config_manager.get("image_generation.backend", "NIM").upper()

        # Handle case where environment variable is not set
        if backend.startswith("${") and backend.endswith("}"):
            return "Image Generation (Not Configured)"

        if backend == "NIM":
            return "Image Generation (NIM)"
        elif backend == "INVOKEAI":
            return "Image Generation (InvokeAI)"
        else:
            return f"Image Generation ({backend})"
