"""LLM service for hn.fm."""

import os
import logging
from typing import Optional
import openai

logger = logging.getLogger(__name__)


class LLMService:
    """Service for interacting with language models."""

    def __init__(self, base_url: str = None, model: str = None):
        """Initialize the LLM service.

        Args:
            base_url: Base URL for local LLM service (e.g., http://192.168.5.96:1234)
            model: Model name to use (e.g., "gpt-oss")
        """
        self.base_url = base_url or os.getenv("LLM_BASE_URL")
        self.model = model or os.getenv("LLM_MODEL", "gpt-oss")
        self.api_key = os.getenv("OPENAI_API_KEY")

        # Determine if we should use local LLM
        self.use_local = bool(self.base_url)

        if self.use_local:
            try:
                # Configure OpenAI client to use local endpoint
                # Local LLM services typically use /v1/chat/completions or /completions
                if not self.base_url.endswith('/v1'):
                    if self.base_url.endswith('/'):
                        api_url = self.base_url + 'v1'
                    else:
                        api_url = self.base_url + '/v1'
                else:
                    api_url = self.base_url

                self.client = openai.OpenAI(
                    api_key="not-needed",  # Local models typically don't require API keys
                    base_url=api_url,
                )
                logger.info(
                    f"Local LLM client initialized successfully for {api_url}"
                )
            except Exception as e:
                logger.error(f"Failed to initialize local LLM client: {e}")
                self.client = None
        elif self.api_key:
            try:
                self.client = openai.OpenAI(api_key=self.api_key)
                logger.info("OpenAI client initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize OpenAI client: {e}")
                self.client = None
        else:
            logger.warning(
                "No LLM configuration found, using fallback script generation"
            )
            self.client = None

    def generate_content(self, prompt: str) -> Optional[str]:
        """Generate content using the LLM.

        Args:
            prompt: Prompt for content generation

        Returns:
            Generated content or None if failed
        """
        if not self.client:
            return self._generate_fallback_content(prompt)

        try:
            # Use the configured model (local or OpenAI)
            model_name = self.model if self.use_local else "gpt-4"

            response = self.client.chat.completions.create(
                model=model_name,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a helpful AI assistant that generates high-quality content based on user requests.",
                    },
                    {"role": "user", "content": prompt},
                ],
                max_tokens=2000,
                temperature=0.7,
            )

            # Check if response is valid and has the expected structure
            if not response or not hasattr(response, 'choices') or not response.choices:
                # Check if this is an error response
                if hasattr(response, 'error') and response.error:
                    logger.error(f"🚨 CRITICAL: Local LLM API error: {response.error}")
                    print(f"   🚨 CRITICAL: Local LLM API error: {response.error}")
                    print(f"   💡 This suggests the local LLM doesn't support the /chat/completions endpoint")
                    print(f"   💡 You may need to use a different API endpoint or service")
                else:
                    logger.error(f"🚨 CRITICAL: Invalid response structure from {model_name} - no choices array")
                    print(f"   🚨 LLM FAILED: {model_name} returned invalid response structure")
                return self._generate_fallback_content(prompt)

            if not response.choices[0] or not hasattr(response.choices[0], 'message'):
                logger.error(f"🚨 CRITICAL: Invalid response choices structure from {model_name} - no message object")
                print(f"   🚨 LLM FAILED: {model_name} returned invalid choices structure")
                return self._generate_fallback_content(prompt)

            if not response.choices[0].message or not hasattr(response.choices[0].message, 'content'):
                logger.error(f"🚨 CRITICAL: Invalid message structure from {model_name} - no content field")
                print(f"   🚨 LLM FAILED: {model_name} returned invalid message structure")
                return self._generate_fallback_content(prompt)

            content = response.choices[0].message.content
            if not content:
                logger.error(f"🚨 CRITICAL: Empty content received from {model_name}")
                print(f"   🚨 LLM FAILED: {model_name} returned empty content")
                return self._generate_fallback_content(prompt)

            provider = "Local LLM" if self.use_local else "OpenAI"
            # Show preview of generated content
            content_preview = content[:50] + "..." if len(content) > 50 else content
            logger.debug(f"✅ Generated content with {provider}: {content_preview}")
            return content

        except Exception as e:
            provider = "local LLM" if self.use_local else "openai"
            logger.error(f"Error generating script with {provider}: {e}")
            return self._generate_fallback_content(prompt)

    def _generate_fallback_content(self, prompt: str) -> str:
        """Generate fallback content when LLM is not available.

        Args:
            prompt: Original prompt (for context)

        Returns:
            Fallback content
        """
        logger.warning("⚠️  FALLBACK: Using fallback script generation due to LLM failure")
        print(f"   ⚠️  FALLBACK: LLM failed, using emergency fallback script")
        print(f"   💡 Tip: Set OPENAI_API_KEY to use OpenAI as fallback when local LLM fails")

        # Extract title from prompt if possible
        title = "Article"
        if "Article Title:" in prompt:
            title_line = [
                line for line in prompt.split("\n") if line.startswith("Article Title:")
            ]
            if title_line:
                title = title_line[0].replace("Article Title:", "").strip()

        # Generate a simple fallback script
        fallback_script = "[S1] This is a fallback, error generating script"

        return fallback_script
