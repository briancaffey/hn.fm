"""Configuration management for hn.fm."""

import os
from typing import Optional
from dotenv import load_dotenv

load_dotenv()


class Config:
    """Configuration class for hn.fm."""

    def __init__(self):
        """Initialize configuration from environment variables."""
        self.firecrawl_api_key = os.getenv("FIRECRAWL_API_KEY")
        self.openai_api_key = os.getenv("OPENAI_API_KEY")
        self.hn_user_agent = os.getenv("HN_USER_AGENT", "hn.fm/0.1.0")
        self.debug = os.getenv("DEBUG", "false").lower() == "true"
        self.log_level = os.getenv("LOG_LEVEL", "INFO")

    def validate(self) -> bool:
        """Validate required configuration.

        Returns:
            True if configuration is valid
        """
        if not self.firecrawl_api_key:
            print("Warning: FIRECRAWL_API_KEY not set")
            return False
        return True
