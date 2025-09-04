"""Content enrichment functions for generating additional metadata from article content."""

import json
import re
import logging
from typing import List, Dict, Any
from ..content.llm_service import LLMService

logger = logging.getLogger(__name__)


def generate_short_description(summary: str) -> str:
    """Generate a short 1-2 sentence description from the article summary.

    Args:
        summary: The full article summary

    Returns:
        str: Short description (1-2 sentences)
    """
    system_prompt = """You are a content summarizer. Your task is to create a concise, engaging short description from an article summary.

Reasoning: low

Guidelines:
- Create exactly 1-2 sentences
- Be specific and factual
- Focus on the main point or key insight
- Use clear, accessible language
- Avoid jargon unless necessary"""

    prompt_template = """Create a short 1-2 sentence description from this article summary:

{summary}

Short description:"""

    try:
        llm_service = LLMService()
        full_prompt = f"{system_prompt}\n\n{prompt_template.format(summary=summary)}"
        result = llm_service.generate_content(full_prompt)

        if not result:
            raise RuntimeError("LLM returned empty short description")

        # Clean up the result
        result = result.strip()
        if result.startswith('"') and result.endswith('"'):
            result = result[1:-1]

        return result

    except Exception as e:
        logger.error(f"Failed to generate short description: {e}")
        raise RuntimeError(f"Failed to generate short description: {e}")


def generate_tags(summary: str) -> List[str]:
    """Generate lowercase alphanumeric tags from the article summary.

    Args:
        summary: The full article summary

    Returns:
        List[str]: List of 2-6 lowercase alphanumeric tags
    """
    system_prompt = """You are a content tagger. Your task is to generate relevant tags from an article summary.

Reasoning: low

Guidelines:
- Generate 2-6 tags
- Each tag should be a single word or acronym
- Use only lowercase letters and numbers (no punctuation, spaces, or special characters)
- Tags should be relevant to the content
- Avoid generic tags like "article" or "content"
- Return ONLY a JSON array of strings, no other text"""

    prompt_template = """Generate 2-6 relevant tags for this article summary. Return only a JSON array of lowercase alphanumeric strings:

{summary}

Tags (JSON array):"""

    try:
        llm_service = LLMService()
        full_prompt = f"{system_prompt}\n\n{prompt_template.format(summary=summary)}"
        result = llm_service.generate_content(full_prompt)

        if not result:
            raise RuntimeError("LLM returned empty tags")

        # Clean up the result
        result = result.strip()

        # Try to parse as JSON
        try:
            tags = json.loads(result)
        except json.JSONDecodeError:
            # If not valid JSON, try to extract array from text
            match = re.search(r"\[(.*?)\]", result)
            if match:
                array_content = match.group(1)
                # Split by comma and clean up
                tags = [tag.strip().strip("\"'") for tag in array_content.split(",")]
            else:
                raise ValueError("Could not parse tags as JSON array")

        # Validate and clean tags
        validated_tags = []
        for tag in tags:
            if isinstance(tag, str):
                # Remove any non-alphanumeric characters and convert to lowercase
                clean_tag = re.sub(r"[^a-zA-Z0-9]", "", tag).lower()
                if clean_tag and len(clean_tag) > 0:
                    validated_tags.append(clean_tag)

        # Ensure we have 2-6 tags
        if len(validated_tags) < 2:
            raise ValueError(f"Too few tags generated: {len(validated_tags)}")
        if len(validated_tags) > 6:
            validated_tags = validated_tags[:6]

        return validated_tags

    except Exception as e:
        logger.error(f"Failed to generate tags: {e}")
        raise RuntimeError(f"Failed to generate tags: {e}")


def generate_emoji(summary: str) -> List[str]:
    """Generate exactly 4 emoji characters that describe the article content.

    Args:
        summary: The full article summary

    Returns:
        List[str]: List of exactly 4 emoji characters
    """
    system_prompt = """You are an emoji selector. Your task is to choose exactly 4 emoji characters that best represent the content of an article.

Reasoning: medium

Guidelines:
- Select exactly 4 emoji characters
- Choose emoji that represent the main themes, topics, or emotions of the content
- Use standard Unicode emoji characters
- Avoid repetitive or similar emoji
- Consider the tone and subject matter
- Return ONLY the 4 emoji characters separated by spaces, no other text"""

    prompt_template = """Select exactly 4 emoji characters that best represent this article summary:

{summary}

Emoji (4 characters, space-separated):"""

    try:
        llm_service = LLMService()
        full_prompt = f"{system_prompt}\n\n{prompt_template.format(summary=summary)}"
        result = llm_service.generate_content(full_prompt)

        if not result:
            raise RuntimeError("LLM returned empty emoji")

        # Clean up the result
        result = result.strip()

        # Split by spaces and clean up
        emoji_list = [emoji.strip() for emoji in result.split() if emoji.strip()]

        # Validate that we have exactly 4 emoji
        if len(emoji_list) != 4:
            raise ValueError(f"Expected exactly 4 emoji, got {len(emoji_list)}")

        # Basic validation that they look like emoji (contain at least one emoji character)
        for emoji in emoji_list:
            if not any(ord(char) > 127 for char in emoji):  # Basic emoji detection
                logger.warning(f"Emoji '{emoji}' may not be a valid emoji character")

        return emoji_list

    except Exception as e:
        logger.error(f"Failed to generate emoji: {e}")
        raise RuntimeError(f"Failed to generate emoji: {e}")


def generate_haiku(content_clean: str) -> str:
    """Generate a haiku that describes the article content.

    Args:
        content_clean: The cleaned article content

    Returns:
        str: A haiku describing the article
    """
    system_prompt = """You are a haiku poet. Your task is to write a haiku that captures the essence of an article.

Reasoning: high

Guidelines:
- Follow traditional haiku structure: 5-7-5 syllables
- Capture the main theme or emotional essence of the content
- Use vivid, concrete imagery
- Avoid abstract concepts
- Make it meaningful and evocative
- Return only the haiku, no additional text or explanation"""

    prompt_template = """Write a haiku that captures the essence of this article content:

{content}

Haiku:"""

    try:
        llm_service = LLMService()
        full_prompt = (
            f"{system_prompt}\n\n{prompt_template.format(content=content_clean)}"
        )
        result = llm_service.generate_content(full_prompt)

        if not result:
            raise RuntimeError("LLM returned empty haiku")

        # Clean up the result
        result = result.strip()

        # Remove any quotes if present
        if result.startswith('"') and result.endswith('"'):
            result = result[1:-1]
        elif result.startswith("'") and result.endswith("'"):
            result = result[1:-1]

        return result

    except Exception as e:
        logger.error(f"Failed to generate haiku: {e}")
        raise RuntimeError(f"Failed to generate haiku: {e}")
