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
                self.client = openai.OpenAI(
                    api_key="not-needed",  # Local models typically don't require API keys
                    base_url=self.base_url
                )
                logger.info(f"Local LLM client initialized successfully for {self.base_url}")
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
            logger.warning("No LLM configuration found, using fallback script generation")
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
                    {"role": "system", "content": "You are a helpful AI assistant that generates high-quality content based on user requests."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=2000,
                temperature=0.7
            )



            content = response.choices[0].message.content
            provider = "Local LLM" if self.use_local else "OpenAI"
            logger.info(f"Successfully generated content with {provider}")
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
        logger.info("Using fallback script generation")

        # Extract title from prompt if possible
        title = "Article"
        if "Article Title:" in prompt:
            title_line = [line for line in prompt.split('\n') if line.startswith('Article Title:')]
            if title_line:
                title = title_line[0].replace('Article Title:', '').strip()

        # Generate a simple fallback script
        fallback_script = f"""[S1] Welcome to today's episode where we discuss {title}.

[S2] This is an interesting article that caught our attention on Hacker News.

[S1] Let me share the key points with you.

[S2] The article discusses important developments in technology and innovation.

[S1] It's fascinating how this connects to broader trends in the industry.

[S2] We hope you found this discussion valuable. Thanks for listening!"""

        return fallback_script
