"""LLM service for hn.fm that handles API calls to language models."""

import os
import logging
import requests
from typing import Dict, Any, Optional
from openai import OpenAI
from anthropic import Anthropic

logger = logging.getLogger(__name__)


class LLMService:
    """Service for interacting with language models."""

    def __init__(self, provider: str = "openai"):
        """Initialize the LLM service.

        Args:
            provider: LLM provider to use ("openai", "anthropic", or "local")
        """
        self.provider = provider
        self.client = self._initialize_client()
        self.base_url = os.getenv("LLM_BASE_URL", "http://localhost:8000")
        self.default_model = os.getenv("LLM_MODEL", "local-model")

    def _initialize_client(self):
        """Initialize the appropriate LLM client.

        Returns:
            Initialized client
        """
        if self.provider == "openai":
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                raise ValueError("OPENAI_API_KEY environment variable not set")
            return OpenAI(api_key=api_key)
        elif self.provider == "anthropic":
            api_key = os.getenv("ANTHROPIC_API_KEY")
            if not api_key:
                raise ValueError("ANTHROPIC_API_KEY environment variable not set")
            return Anthropic(api_key=api_key)
        elif self.provider == "local":
            # For local LLM, we don't need a client object
            return None
        else:
            raise ValueError(f"Unsupported provider: {self.provider}")

    def generate_script(self, system_prompt: str, user_prompt: str, **kwargs) -> str:
        """Generate script content using the LLM.

        Args:
            system_prompt: System prompt defining the role and style
            user_prompt: User prompt with specific content to process
            **kwargs: Additional parameters for the LLM call

        Returns:
            Generated script text
        """
        try:
            if self.provider == "openai":
                return self._call_openai(system_prompt, user_prompt, **kwargs)
            elif self.provider == "anthropic":
                return self._call_anthropic(system_prompt, user_prompt, **kwargs)
            elif self.provider == "local":
                return self._call_local_llm(system_prompt, user_prompt, **kwargs)
            else:
                raise ValueError(f"Unsupported provider: {self.provider}")
        except Exception as e:
            logger.error(f"Error generating script with {self.provider}: {e}")
            # Re-raise the exception instead of using fallback
            raise

    def _call_openai(self, system_prompt: str, user_prompt: str, **kwargs) -> str:
        """Call OpenAI API for script generation.

        Args:
            system_prompt: System prompt
            user_prompt: User prompt
            **kwargs: Additional parameters

        Returns:
            Generated script
        """
        response = self.client.chat.completions.create(
            model=kwargs.get("model", "gpt-4"),
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=kwargs.get("temperature", 0.7),
            max_tokens=kwargs.get("max_tokens", 2000),
            top_p=kwargs.get("top_p", 1.0),
            frequency_penalty=kwargs.get("frequency_penalty", 0.0),
            presence_penalty=kwargs.get("presence_penalty", 0.0)
        )
        return response.choices[0].message.content.strip()

    def _call_anthropic(self, system_prompt: str, user_prompt: str, **kwargs) -> str:
        """Call Anthropic API for script generation.

        Args:
            system_prompt: System prompt
            user_prompt: User prompt
            **kwargs: Additional parameters

        Returns:
            Generated script
        """
        response = self.client.messages.create(
            model=kwargs.get("model", "claude-3-sonnet-20240229"),
            max_tokens=kwargs.get("max_tokens", 2000),
            temperature=kwargs.get("temperature", 0.7),
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}]
        )
        return response.content[0].text.strip()

    def _call_local_llm(self, system_prompt: str, user_prompt: str, **kwargs) -> str:
        """Call local LLM service for script generation.

        Args:
            system_prompt: System prompt
            user_prompt: User prompt
            **kwargs: Additional parameters

        Returns:
            Generated script
        """
        try:
            # Prepare the request payload
            payload = {
                "model": kwargs.get("model", self.default_model),  # Model name for local LLM
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                "temperature": kwargs.get("temperature", 0.7),
                "max_tokens": kwargs.get("max_tokens", 2000),
                "stream": False
            }

            # Make request to local LLM endpoint
            response = requests.post(
                f"{self.base_url}/v1/chat/completions",
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=60
            )
            response.raise_for_status()

            result = response.json()
            if "choices" in result and len(result["choices"]) > 0:
                return result["choices"][0]["message"]["content"].strip()
            else:
                raise ValueError("Invalid response format from local LLM")

        except Exception as e:
            logger.error(f"Error calling local LLM: {e}")
            raise RuntimeError(f"Local LLM call failed: {e}")

    def test_connection(self) -> bool:
        """Test the LLM service connection.

        Returns:
            True if connection successful
        """
        try:
            test_prompt = "Generate a single line response: 'Connection test successful'"
            response = self.generate_script(
                "You are a helpful assistant.",
                test_prompt,
                max_tokens=50
            )
            return "Connection test successful" in response
        except Exception as e:
            logger.error(f"LLM connection test failed: {e}")
            return False
