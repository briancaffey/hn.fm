"""Content scraper for hn.fm."""

import requests
import logging
from typing import Dict, Any, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ScrapedContent:
    """Represents scraped content from a URL."""
    title: str
    content: str
    url: str
    success: bool
    error: Optional[str] = None


class ContentScraper:
    """Scrapes content from URLs using Firecrawl."""

    def __init__(self, api_key: str = None, base_url: str = "https://api.firecrawl.dev"):
        """Initialize the content scraper.

        Args:
            api_key: Firecrawl API key
            base_url: Firecrawl API base URL
        """
        self.api_key = api_key
        self.base_url = base_url.rstrip('/')

        # Fallback to local Firecrawl instance if no API key
        if not self.api_key:
            self.base_url = "http://localhost:3002"

    def extract_content(self, url: str) -> Dict[str, Any]:
        """Extract content from URL (alias for scrape_url)."""
        scraped = self.scrape_url(url)
        if scraped.success:
            return {
                'title': scraped.title,
                'content': scraped.content,
                'url': scraped.url
            }
        else:
            return {
                'title': 'Error',
                'content': '',
                'url': url
            }

    def scrape_url(self, url: str) -> ScrapedContent:
        """Scrape content from a URL.

        Args:
            url: URL to scrape

        Returns:
            ScrapedContent object
        """
        try:
            logger.info(f"Extracting content from: {url}")

            if self.api_key:
                # Use Firecrawl API
                return self._scrape_with_firecrawl_api(url)
            else:
                # Use local Firecrawl instance
                return self._scrape_with_local_firecrawl(url)

        except Exception as e:
            logger.error(f"Failed to scrape {url}: {e}")
            return ScrapedContent(
                title="Error",
                content="",
                url=url,
                success=False,
                error=str(e)
            )

    def _scrape_with_firecrawl_api(self, url: str) -> ScrapedContent:
        """Scrape using Firecrawl API."""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        data = {
            "url": url,
            "includeTags": ["h1", "h2", "h3", "p", "article"],
            "excludeTags": ["nav", "footer", "aside", "script", "style"]
        }

        response = requests.post(
            f"{self.base_url}/v0/scrape",
            headers=headers,
            json=data,
            timeout=30
        )

        if response.status_code != 200:
            raise RuntimeError(f"Firecrawl API error: {response.status_code}")

        result = response.json()

        return ScrapedContent(
            title=result.get('data', {}).get('title', 'Unknown Title'),
            content=result.get('data', {}).get('markdown', ''),
            url=url,
            success=True
        )

    def _scrape_with_local_firecrawl(self, url: str) -> ScrapedContent:
        """Scrape using local Firecrawl instance."""
        data = {
            "url": url,
            "includeTags": ["h1", "h2", "h3", "p", "article"],
            "excludeTags": ["nav", "footer", "aside", "script", "style"]
        }

        response = requests.post(
            f"{self.base_url}/v0/scrape",
            json=data,
            timeout=30
        )

        if response.status_code != 200:
            raise RuntimeError(f"Local Firecrawl error: {response.status_code}")

        result = response.json()

        return ScrapedContent(
            title=result.get('data', {}).get('title', 'Unknown Title'),
            content=result.get('data', {}).get('markdown', ''),
            url=url,
            success=True
        )
