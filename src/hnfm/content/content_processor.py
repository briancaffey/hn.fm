"""Content processor for hn.fm that cleans and structures scraped content."""

import re
from typing import Dict, Any, List
import logging

logger = logging.getLogger(__name__)


class ContentProcessor:
    """Processes and cleans scraped content for script generation."""

    def __init__(self):
        """Initialize the content processor."""
        self.cleanup_patterns = [
            # Remove image markdown
            (r'!\[.*?\]\(.*?\)', ''),
            # Remove link markdown but keep text
            (r'\[([^\]]+)\]\([^)]+\)', r'\1'),
            # Remove empty brackets and parentheses
            (r'\[\]\([^)]*\)', ''),
            (r'\[\]', ''),
            (r'\(\)', ''),
            # Remove subscription/social elements
            (r'Subscribe.*?Sign in', ''),
            (r'Share.*?Comments', ''),
            (r'Ready for more.*?Subscribe', ''),
            (r'SubscribeSign in', ''),
            (r'CommentsRestacks', ''),
            (r'TopLatestDiscussions', ''),
            # Remove excessive equals signs and horizontal rules
            (r'={10,}', ''),
            (r'^[-*_]{3,}$', ''),
            # Remove social media links and URLs
            (r'https?://[^\s]+', ''),
            # Remove date patterns
            (r'\b[A-Z][a-z]{2}\s+\d{1,2},\s+\d{4}\b', ''),
            (r'\b\d{1,2}\s+[A-Z][a-z]{2}\s+\d{4}\b', ''),
            # Remove social media elements
            (r'@[a-zA-Z0-9_]+', ''),
            (r'#\w+', ''),
            # Remove share/comment elements
            (r'Share\)', ''),
            (r'Comments\)', ''),
            (r'Discussion about this post', ''),
            # Remove code blocks
            (r'```[\s\S]*?```', ''),
            # Remove inline code
            (r'`([^`]+)`', r'\1'),
            # Remove list markers
            (r'^[-*+]\s*', ''),
            # Clean up headers (keep text, remove markdown)
            (r'^#{1,6}\s*', ''),
        ]

    def process_content(self, content: Dict[str, Any]) -> Dict[str, Any]:
        """Process scraped content for script generation.

        Args:
            content: Raw scraped content from Firecrawl

        Returns:
            Processed content ready for script generation
        """
        try:
            # Extract key information
            processed = {
                'title': content.get('metadata', {}).get('title', 'Unknown Title'),
                'url': content.get('metadata', {}).get('url', ''),
                'description': content.get('metadata', {}).get('description', ''),
                'markdown': content.get('markdown', ''),
                'cleaned_text': '',
                'meaningful_paragraphs': [],
                'word_count': 0
            }

            # Clean the markdown content
            cleaned_text = self._clean_markdown(processed['markdown'])
            processed['cleaned_text'] = cleaned_text

            # Extract meaningful paragraphs
            processed['meaningful_paragraphs'] = self._extract_meaningful_content(cleaned_text)

            # Count words
            processed['word_count'] = len(cleaned_text.split())

            logger.info(f"Processed content: {processed['word_count']} words, {len(processed['meaningful_paragraphs'])} meaningful paragraphs")
            return processed

        except Exception as e:
            logger.error(f"Error processing content: {e}")
            return {}

    def _clean_markdown(self, markdown: str) -> str:
        """Clean markdown content for better processing.

        Args:
            markdown: Raw markdown content

        Returns:
            Cleaned text content
        """
        cleaned = markdown

        # Apply cleanup patterns
        for pattern, replacement in self.cleanup_patterns:
            cleaned = re.sub(pattern, replacement, cleaned, flags=re.MULTILINE)

        # Remove excessive whitespace
        cleaned = re.sub(r'\n\s*\n\s*\n', '\n\n', cleaned)
        cleaned = re.sub(r'\s+', ' ', cleaned)
        cleaned = cleaned.strip()

        # Split into paragraphs and keep meaningful ones
        paragraphs = cleaned.split('\n\n')
        clean_paragraphs = []

        for para in paragraphs:
            para = para.strip()
            if len(para) > 50 and self._is_meaningful_content(para):
                # Clean up remaining artifacts
                para = re.sub(r'\[\s*\]', '', para)
                para = re.sub(r'\(\s*\)', '', para)
                para = re.sub(r'\s+', ' ', para)
                clean_paragraphs.append(para)

        return '\n\n'.join(clean_paragraphs)

    def _is_meaningful_content(self, text: str) -> bool:
        """Check if text contains meaningful content.

        Args:
            text: Text to check

        Returns:
            True if meaningful
        """
        # Skip obvious navigation, header, footer content
        skip_patterns = [
            r'^subscribe$', r'^sign in$', r'^log in$', r'^menu$',
            r'^advertisement$', r'^cookie', r'^privacy policy$',
            r'^share$', r'^like$', r'^comment$', r'^follow$',
            r'^read full story$', r'^see all$', r'^ready for more$',
            r'^restacks$', r'^no posts$', r'^discussions$',
        ]

        text_lower = text.lower().strip()
        for pattern in skip_patterns:
            if re.search(pattern, text_lower):
                return False

        # Skip very short or purely navigational content
        words = text.split()
        if len(words) < 5:
            return False

        # Must contain some actual content words
        content_indicators = ['learn', 'develop', 'create', 'build', 'use', 'make', 'get', 'how', 'what', 'why', 'when', 'where']
        return any(indicator in text_lower for indicator in content_indicators) or len(words) >= 15

    def _extract_meaningful_content(self, text: str) -> List[str]:
        """Extract meaningful content paragraphs.

        Args:
            text: Cleaned text content

        Returns:
            List of meaningful paragraphs
        """
        # First try splitting by existing paragraph breaks
        paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]

        # If we only get one big paragraph, try to split by headers or topics
        if len(paragraphs) == 1:
            # Split by likely topic headers (capitalized phrases that look like headers)
            header_pattern = r'\b([A-Z][a-z]+(?: [A-Z][a-z]+)*(?:, [A-Z][a-z]+(?: [A-Z][a-z]+)*)*)\b'
            parts = re.split(header_pattern, paragraphs[0])

            # Combine headers with their content
            combined_paragraphs = []
            for i in range(1, len(parts), 2):
                if i + 1 < len(parts):
                    header = parts[i]
                    content = parts[i + 1].strip()
                    if len(content) > 100:
                        combined_paragraphs.append(f"{header}. {content}")

            if combined_paragraphs:
                paragraphs = combined_paragraphs
            else:
                # If that doesn't work, split into chunks
                chunk_size = 300
                text_words = text.split()
                paragraphs = []
                for i in range(0, len(text_words), chunk_size):
                    chunk = ' '.join(text_words[i:i + chunk_size])
                    if len(chunk) > 100:
                        paragraphs.append(chunk)

        meaningful = []
        for para in paragraphs:
            if len(para) > 100 and self._is_meaningful_content(para):
                # Truncate very long paragraphs for better conversation flow
                if len(para) > 400:
                    para = para[:400] + "..."
                meaningful.append(para)

        return meaningful[:6]  # Limit to top 6 meaningful paragraphs

    def save_processed_content(self, processed_content: Dict[str, Any], filename: str) -> bool:
        """Save processed content to a file for review.

        Args:
            processed_content: Processed content dictionary
            filename: Output filename

        Returns:
            True if successful
        """
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(f"# Processed Content: {processed_content.get('title', 'Unknown')}\n\n")
                f.write(f"**Source URL:** {processed_content.get('url', 'Unknown')}\n")
                f.write(f"**Word Count:** {processed_content.get('word_count', 0)}\n")
                f.write(f"**Meaningful Paragraphs:** {len(processed_content.get('meaningful_paragraphs', []))}\n\n")

                f.write("## Meaningful Paragraphs\n\n")
                for i, para in enumerate(processed_content.get('meaningful_paragraphs', []), 1):
                    f.write(f"{i}. {para}\n\n")

                f.write("## Cleaned Text\n\n")
                f.write(processed_content.get('cleaned_text', ''))

            logger.info(f"Processed content saved to {filename}")
            return True

        except Exception as e:
            logger.error(f"Error saving processed content: {e}")
            return False