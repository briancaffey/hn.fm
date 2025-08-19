"""Content scraper for hn.fm using Firecrawl."""

import requests
import json
import os
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


class ContentScraper:
    """Scrapes content from URLs using Firecrawl."""

    def __init__(self, api_key: str, base_url: Optional[str] = None):
        """Initialize the content scraper.

        Args:
            api_key: Firecrawl API key
            base_url: Firecrawl API base URL (defaults to env var or cloud URL)
        """
        self.api_key = api_key
        self.base_url = base_url or os.getenv(
            "FIRECRAWL_BASE_URL", "https://api.firecrawl.dev"
        )
        self.session = requests.Session()
        self.session.headers.update(
            {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        )

    def scrape_url(self, url: str) -> Optional[Dict[str, Any]]:
        """Scrape content from a URL.

        Args:
            url: URL to scrape

        Returns:
            Scraped content dictionary or None if error
        """
        try:
            payload = {
                "url": url,
                "pageOptions": {
                    "onlyMainContent": True,
                    "includeHtml": False,
                    "includeMarkdown": True,
                },
            }

            response = self.session.post(f"{self.base_url}/v0/scrape", json=payload)
            response.raise_for_status()

            result = response.json()

            # Check if the request was successful
            if result.get("success") and result.get("data"):
                return result["data"]
            else:
                logger.error(f"Firecrawl request failed: {result}")
                return None

        except Exception as e:
            logger.error(f"Error scraping URL {url}: {e}")
            return None

    def save_markdown(self, content: Dict[str, Any], filename: str) -> bool:
        """Save scraped markdown content to a file.

        Args:
            content: Scraped content dictionary
            filename: Output filename

        Returns:
            True if successful, False otherwise
        """
        try:
            markdown_content = content.get("markdown", "")
            if not markdown_content:
                logger.warning("No markdown content found")
                return False

            with open(filename, "w", encoding="utf-8") as f:
                f.write(markdown_content)

            logger.info(f"Markdown saved to {filename}")
            return True

        except Exception as e:
            logger.error(f"Error saving markdown to {filename}: {e}")
            return False
