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
        from .llm_schemas import Tags

        llm_service = LLMService()
        full_prompt = f"{system_prompt}\n\n{prompt_template.format(summary=summary)}"
        # Schema-enforced rather than parsed out of prose. The old path asked
        # for "a JSON array", then tried json.loads, then a regex for brackets,
        # then a comma split — and still failed on real output with "Could not
        # parse tags as JSON array", falling back to the default silently.
        result = llm_service.generate_structured(full_prompt, Tags)

        validated_tags = []
        for tag in result.tags:
            clean_tag = re.sub(r"[^a-zA-Z0-9]", "", str(tag)).lower()
            if clean_tag:
                validated_tags.append(clean_tag)

        # The schema constrains the count, but stripping punctuation can still
        # empty a tag, so the floor is re-checked here.
        if len(validated_tags) < 2:
            raise ValueError(f"Too few usable tags: {len(validated_tags)}")
        return validated_tags[:6]

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

        # Keep only things that look like emoji, then pad/truncate to exactly 4.
        # The LLM occasionally returns the wrong count — that must NOT fail the
        # whole pipeline over cosmetic metadata.
        _defaults = ["📰", "✨", "🔥", "💡", "🚀", "🤖"]
        emoji_list = [
            e.strip() for e in result.split()
            if e.strip() and any(ord(c) > 127 for c in e)
        ]
        for d in _defaults:
            if len(emoji_list) >= 4:
                break
            if d not in emoji_list:
                emoji_list.append(d)
        return emoji_list[:4]

    except Exception as e:
        logger.warning(f"emoji generation fell back to defaults (non-fatal): {e}")
        return ["📰", "✨", "🔥", "💡"]


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
