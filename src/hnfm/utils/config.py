"""Configuration management for hn.fm."""

import os
import yaml
from pathlib import Path
from typing import Any, Dict, Optional
import logging

# Load environment variables from .env file
try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    # dotenv not available, continue without it
    pass

logger = logging.getLogger(__name__)


class ConfigManager:
    """Manages configuration loading and access."""

    def __init__(self, config_file: str = "config.yaml"):
        """Initialize config manager.

        Args:
            config_file: Path to configuration file
        """
        self.config_file = config_file
        self.config = self._load_config()

    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from YAML file."""
        try:
            config_path = Path(self.config_file)
            if not config_path.exists():
                logger.warning(
                    f"Config file {self.config_file} not found, using defaults"
                )
                return self._get_default_config()

            with open(config_path, "r") as f:
                config = yaml.safe_load(f)

            logger.info(f"Loaded raw config from {self.config_file}: {config}")

            # Replace environment variables
            config = self._replace_env_vars(config)
            logger.info(f"After env var replacement: {config}")

            # Merge with defaults to ensure all required keys exist
            default_config = self._get_default_config()
            logger.info(f"Default config: {default_config}")
            config = self._merge_configs(default_config, config)
            logger.info(f"After merging: {config}")

            logger.info(f"Loaded configuration from {self.config_file}")
            return config

        except Exception as e:
            logger.error(f"Failed to load config: {e}")
            return self._get_default_config()

    def _replace_env_vars(self, config: Any) -> Any:
        """Replace environment variable placeholders in config."""
        if isinstance(config, dict):
            return {k: self._replace_env_vars(v) for k, v in config.items()}
        elif isinstance(config, list):
            return [self._replace_env_vars(item) for item in config]
        elif (
            isinstance(config, str) and config.startswith("${") and config.endswith("}")
        ):
            env_var = config[2:-1]
            value = os.getenv(env_var)
            if value is not None:
                return value
            else:
                logger.warning(
                    f"Environment variable {env_var} not found, using template value"
                )
                return config
        else:
            return config

    def _merge_configs(
        self, default_config: Dict[str, Any], user_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Merge user config with default config, ensuring all required keys exist."""
        merged = default_config.copy()

        def merge_recursive(default: Any, user: Any) -> Any:
            if isinstance(default, dict) and isinstance(user, dict):
                result = default.copy()
                for key, value in user.items():
                    if key in default:
                        result[key] = merge_recursive(default[key], value)
                    else:
                        result[key] = value
                return result
            elif isinstance(default, list) and isinstance(user, list):
                return user  # Use user list if provided
            else:
                return user if user is not None else default

        return merge_recursive(default_config, user_config)

    def _get_default_config(self) -> Dict[str, Any]:
        """Get default configuration."""
        return {
            "voice": {
                "default": "notebooklm",
                "available_voices": ["notebooklm", "studio_voice"],
            },
            "tts": {
                "base_url": "${TTS_BASE_URL}",
                "default_voice": "${TTS_DEFAULT_VOICE}",
                "batch_size": 2,
                "max_attempts": "${TTS_MAX_ATTEMPTS}",
                "delay_between_batches": 2,
                "timeout_seconds": "${TTS_TIMEOUT_SECONDS}",
                "retry_delay": "${TTS_RETRY_DELAY}",
            },
            "studio_voice": {
                "enabled": True,
                "target": "${STUDIO_VOICE_TARGET}",
                "model_type": "${STUDIO_VOICE_MODEL_TYPE}",
                "http_health_url": "${STUDIO_VOICE_HTTP_HEALTH_URL}",
                "streaming": False,
                "ssl_mode": None,
                "sample_rate": 48000,
            },
            "llm": {
                "enabled": True,
                "base_url": "${LLM_BASE_URL}",
                "model": "${LLM_MODEL}",
                "provider": "${LLM_PROVIDER}",
            },
            "content": {
                "max_episode_length": 15,
                "include_comments": True,
                "quality_threshold": 0.8,
                "max_paragraphs": 10,
            },
            "pipeline": {
                "skippable_steps": [
                    "hn_scraping",
                    "firecrawl_content",
                    "content_processing",
                    "script_generation",
                    "tts_generation",
                    "audio_cleaning",
                    "audio_assembly",
                    "asr_processing",
                ],
                "cache": {
                    "enabled": True,
                    "directory": "cache",
                    "expiration_hours": 24,
                },
            },
            "output": {
                "base_directory": "outputs",
                "organize_by_story": True,
                "keep_intermediate_files": True,
                "audio_format": "wav",
                "audio_quality": "high",
            },
            "apis": {
                "firecrawl": {
                    "base_url": "${FIRECRAWL_BASE_URL}",
                    "api_key": "${FIRECRAWL_API_KEY}",
                },
                "openai": {"api_key": "${OPENAI_API_KEY}"},
                "hn": {"user_agent": "${HN_USER_AGENT}"},
            },
            "asr": {
                "base_url": "${ASR_BASE_URL}",
                "model_size": "${ASR_MODEL_SIZE}",
                "min_speakers": "${ASR_MIN_SPEAKERS}",
                "max_speakers": "${ASR_MAX_SPEAKERS}",
                "timeout_seconds": "${ASR_TIMEOUT_SECONDS}",
                "retry_delay": "${ASR_RETRY_DELAY}",
                "max_attempts": "${ASR_MAX_ATTEMPTS}",
            },
            "image_generation": {
                "base_url": "${IMAGE_GENERATION_BASE_URL}",
                "default_height": 1024,
                "default_width": 1024,
                "default_cfg_scale": 5,
                "default_mode": "base",
                "default_steps": 50,
                "default_samples": 1,
                "output_directory": "images",
                "default_style": "detailed cartoon style",
            },
            "development": {
                "debug": "${DEBUG}",
                "log_level": "${LOG_LEVEL}",
                "enable_progress_bars": True,
                "parallel_processing": False,
            },
        }

    def reload(self):
        """Reload configuration from file."""
        self.config = self._load_config()

    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value by dot-notation key.

        Args:
            key: Configuration key (e.g., "tts.base_url")
            default: Default value if key not found

        Returns:
            Configuration value
        """
        try:
            keys = key.split(".")
            value = self.config

            for k in keys:
                if isinstance(value, dict) and k in value:
                    value = value[k]
                else:
                    return default

            return value
        except Exception:
            return default

    def set(self, key: str, value: Any):
        """Set configuration value by dot-notation key.

        Args:
            key: Configuration key (e.g., "tts.base_url")
            value: Value to set
        """
        try:
            keys = key.split(".")
            config = self.config

            # Navigate to the parent of the target key
            for k in keys[:-1]:
                if k not in config:
                    config[k] = {}
                config = config[k]

            # Set the final value
            config[keys[-1]] = value

        except Exception as e:
            logger.error(f"Failed to set config key {key}: {e}")


# Global config manager instance
config_manager = ConfigManager()
