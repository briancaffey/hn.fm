"""Content processing for hn.fm."""

import re
import logging
from typing import List, Dict, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ProcessedContent:
    """Represents processed content."""

    title: str
    cleaned_content: str
    meaningful_paragraphs: List[str]
    word_count: int
    estimated_reading_time: float


class ContentProcessor:
    """Processes and cleans scraped content."""

    def __init__(self):
        """Initialize the content processor."""
        pass

    def _clean_markdown(self, content: str) -> str:
        """Clean markdown content (alias for _clean_content)."""
        return self._clean_content(content)

    def extract_meaningful_paragraphs(self, content: str) -> List[str]:
        """Extract meaningful paragraphs from content (alias for _extract_meaningful_paragraphs)."""
        return self._extract_meaningful_paragraphs(content)

    def process_content(self, title: str, raw_content: str) -> ProcessedContent:
        """Process and clean raw content.

        Args:
            title: Article title
            raw_content: Raw scraped content

        Returns:
            ProcessedContent object
        """
        try:
            # Clean the content
            cleaned_content = self._clean_content(raw_content)

            # Extract meaningful paragraphs
            meaningful_paragraphs = self._extract_meaningful_paragraphs(cleaned_content)

            # Calculate metrics
            word_count = len(cleaned_content.split())
            estimated_reading_time = word_count / 200  # Assuming 200 words per minute

            logger.info(f"Extracted {len(meaningful_paragraphs)} meaningful paragraphs")

            return ProcessedContent(
                title=title,
                cleaned_content=cleaned_content,
                meaningful_paragraphs=meaningful_paragraphs,
                word_count=word_count,
                estimated_reading_time=estimated_reading_time,
            )

        except Exception as e:
            logger.error(f"Failed to process content: {e}")
            raise RuntimeError(f"Content processing failed: {e}")

    def _clean_content(self, content: str) -> str:
        """Clean and normalize content.

        Args:
            content: Raw content to clean

        Returns:
            Cleaned content
        """
        if not content:
            return ""

        # Remove HTML tags
        content = re.sub(r"<[^>]+>", "", content)

        # Remove markdown formatting
        content = re.sub(r"#{1,6}\s+", "", content)  # Headers
        content = re.sub(r"\*\*(.*?)\*\*", r"\1", content)  # Bold
        content = re.sub(r"\*(.*?)\*", r"\1", content)  # Italic
        content = re.sub(r"`(.*?)`", r"\1", content)  # Code
        content = re.sub(r"\[(.*?)\]\(.*?\)", r"\1", content)  # Links

        # Remove extra whitespace
        content = re.sub(r"\n\s*\n", "\n\n", content)
        content = re.sub(r" +", " ", content)

        # Remove leading/trailing whitespace
        content = content.strip()

        return content

    def _extract_meaningful_paragraphs(self, content: str) -> List[str]:
        """Extract meaningful paragraphs from content.

        Args:
            content: Cleaned content

        Returns:
            List of meaningful paragraphs
        """
        if not content:
            return []

        # Split into paragraphs
        paragraphs = content.split("\n\n")

        # Filter meaningful paragraphs
        meaningful = []
        for para in paragraphs:
            para = para.strip()
            if self._is_meaningful_paragraph(para):
                meaningful.append(para)

        # Limit to reasonable number of paragraphs
        max_paragraphs = 10
        if len(meaningful) > max_paragraphs:
            meaningful = meaningful[:max_paragraphs]

        return meaningful

    def _is_meaningful_paragraph(self, paragraph: str) -> bool:
        """Check if a paragraph is meaningful.

        Args:
            paragraph: Paragraph text

        Returns:
            True if meaningful
        """
        if not paragraph:
            return False

        # Must have minimum length
        if len(paragraph) < 20:
            return False

        # Must not be just whitespace or special characters
        if not re.search(r"[a-zA-Z]", paragraph):
            return False

        # Must not be just numbers or symbols
        if re.match(r"^[\d\s\W]+$", paragraph):
            return False

        return True
