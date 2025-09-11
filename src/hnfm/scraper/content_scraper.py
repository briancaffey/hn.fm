"""Content scraper for hn.fm."""

import requests
import logging
import urllib.parse
from typing import Dict, Any, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


def get_wayback_url(url: str) -> Optional[str]:
    """Get the closest Wayback Machine URL for a given URL.

    Args:
        url: Original URL to find archived version for

    Returns:
        Wayback Machine URL if available, None otherwise
    """
    try:
        logger.info(f"Looking up Wayback Machine archive for: {url}")

        response = requests.get(
            "https://archive.org/wayback/available",
            params={"url": url},
            timeout=10
        )

        if response.status_code != 200:
            logger.warning(f"Wayback Machine API returned {response.status_code}")
            return None

        data = response.json()
        closest = data.get("archived_snapshots", {}).get("closest")

        if closest and closest.get("available"):
            wayback_url = closest["url"]
            timestamp = closest["timestamp"]
            logger.info(f"Found Wayback Machine snapshot from {timestamp}: {wayback_url}")
            return wayback_url
        else:
            logger.info(f"No Wayback Machine snapshot found for {url}")
            return None

    except Exception as e:
        logger.error(f"Failed to lookup Wayback Machine URL for {url}: {e}")
        return None


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

    def __init__(self, api_key: str = None, base_url: str = None):
        """Initialize the content scraper.

        Args:
            api_key: Firecrawl API key (not used for local instance)
            base_url: Local Firecrawl base URL (defaults to FIRECRAWL_BASE_URL env var)
        """
        import os

        self.api_key = api_key  # Keep for compatibility but not used
        self.base_url = (
            base_url or os.getenv("FIRECRAWL_BASE_URL", "http://localhost:3002")
        ).rstrip("/")

        # Always use local Firecrawl
        self.is_local_firecrawl = True

    def extract_content(self, url: str) -> Dict[str, Any]:
        """Extract content from URL (alias for scrape_url)."""
        scraped = self.scrape_url(url)
        if scraped.success:
            return {
                "title": scraped.title,
                "content": scraped.content,
                "url": scraped.url,
            }
        else:
            return {"title": "Error", "content": "", "url": url}

    def scrape_url(self, url: str) -> ScrapedContent:
        """Scrape content from a URL with Wayback Machine fallback.

        Args:
            url: URL to scrape

        Returns:
            ScrapedContent object
        """
        try:
            logger.info(f"Extracting content from: {url}")

            # Try scraping the original URL first
            return self._scrape_with_local_firecrawl(url)

        except Exception as e:
            logger.warning(f"Failed to scrape original URL {url}: {e}")

            # Try Wayback Machine as fallback
            wayback_url = get_wayback_url(url)
            if wayback_url:
                try:
                    logger.info(f"Attempting to scrape Wayback Machine URL: {wayback_url}")
                    return self._scrape_with_local_firecrawl(wayback_url)
                except Exception as wayback_error:
                    logger.error(f"Failed to scrape Wayback Machine URL {wayback_url}: {wayback_error}")
                    return ScrapedContent(
                        title="Error",
                        content="",
                        url=url,
                        success=False,
                        error=f"Original failed: {e}. Wayback failed: {wayback_error}"
                    )
            else:
                logger.error(f"No Wayback Machine archive available for {url}")
                return ScrapedContent(
                    title="Error",
                    content="",
                    url=url,
                    success=False,
                    error=f"Scraping failed and no Wayback Machine archive available: {e}"
                )

    def _scrape_with_local_firecrawl(self, url: str) -> ScrapedContent:
        """Scrape using local Firecrawl instance."""
        data = {
            "url": url,
            "includeTags": ["h1", "h2", "h3", "p", "article"],
            "excludeTags": ["nav", "footer", "aside", "script", "style"],
        }

        response = requests.post(f"{self.base_url}/v0/scrape", json=data, timeout=30)

        if response.status_code != 200:
            raise RuntimeError(f"Local Firecrawl error: {response.status_code}")

        result = response.json()

        return ScrapedContent(
            title=result.get("data", {}).get("title", "Unknown Title"),
            content=result.get("data", {}).get("markdown", ""),
            url=url,
            success=True,
        )
