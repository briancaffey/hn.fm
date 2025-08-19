"""Configuration management for hn.fm."""

import os
import yaml
from pathlib import Path
from typing import Any, Dict, Optional
import logging

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
                logger.warning(f"Config file {config_file} not found, using defaults")
                return self._get_default_config()

            with open(config_path, "r") as f:
                config = yaml.safe_load(f)

            # Replace environment variables
            config = self._replace_env_vars(config)

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
            return os.getenv(env_var, config)
        else:
            return config

    def _get_default_config(self) -> Dict[str, Any]:
        """Get default configuration."""
        return {
            "voice": {
                "default": "notebooklm",
                "available_voices": ["notebooklm", "studio_voice"],
            },
            "tts": {
                "base_url": "http://localhost:7860",
                "default_voice": "notebooklm",
                "batch_size": 2,
                "max_attempts": 3,
                "delay_between_batches": 2,
            },
            "studio_voice": {
                "enabled": True,
                "target": "localhost:8001",
                "model_type": "48k-hq",
                "streaming": False,
                "ssl_mode": None,
                "sample_rate": 48000,
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
                "firecrawl": {"base_url": "https://api.firecrawl.dev", "api_key": ""},
                "openai": {"api_key": ""},
                "hn": {"user_agent": "hn.fm/0.1.0 (briancaffey)"},
            },
            "development": {
                "debug": False,
                "log_level": "INFO",
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
