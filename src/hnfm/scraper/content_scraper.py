"""Content scraper for hn.fm."""

import requests
import logging
import urllib.parse
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


# Below this an "archive" is an archived error page, not the article. Real
# scrapes in this corpus average ~18,000 characters; the two wayback hits that
# reached triage averaged 43.
MIN_ARCHIVE_CHARS = 500

# A story submitted less recently than this may have been archived; below it,
# the Wayback lookup is a guaranteed miss. Most `newstories` items are hours
# old, and every failed scrape on one was paying for the round trip.
MIN_HOURS_FOR_ARCHIVE = 24


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
            "https://archive.org/wayback/available", params={"url": url}, timeout=10
        )

        if response.status_code != 200:
            logger.warning(f"Wayback Machine API returned {response.status_code}")
            return None

        data = response.json()
        closest = data.get("archived_snapshots", {}).get("closest")

        if closest and closest.get("available"):
            wayback_url = closest["url"]
            timestamp = closest["timestamp"]
            logger.info(
                f"Found Wayback Machine snapshot from {timestamp}: {wayback_url}"
            )
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
    # Which retrieval path produced this: firecrawl | wayback. An archived copy
    # is materially different material from a live fetch, so `producibility`
    # (plans/09) needs to distinguish them.
    source: str = "firecrawl"
    # Outbound links from the page, for context_links to pick a few worth
    # following. default_factory, not [], so ScrapedContent instances never
    # share one list.
    links: List[dict] = field(default_factory=list)


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

    def scrape_url(
        self, url: str, submitted_hours_ago: Optional[float] = None
    ) -> ScrapedContent:
        """Scrape content from a URL with Wayback Machine fallback.

        Args:
            url: URL to scrape
            submitted_hours_ago: age of the HN item, when known. A story
                submitted today has not been archived yet, so the Wayback
                lookup is a guaranteed miss and is skipped.

        Returns:
            ScrapedContent object
        """
        from . import scrape_cache

        # A URL that failed recently will fail again, and the retry costs a
        # full firecrawl timeout plus a Wayback lookup. Observed: the same
        # Twitter URL attempted twice within an hour, failing identically.
        cached = scrape_cache.recent_failure(url)
        if cached:
            logger.info(f"Skipping {url}: {cached}")
            return ScrapedContent(
                title="Error", content="", url=url, success=False,
                error=f"Skipped without retrying: {cached}",
            )

        try:
            logger.info(f"Extracting content from: {url}")

            # Try scraping the original URL first
            return self._scrape_with_local_firecrawl(url)

        except Exception as e:
            logger.warning(f"Failed to scrape original URL {url}: {e}")
            scrape_cache.record_failure(url, str(e))

            # Try Wayback Machine as fallback. Skipped for a fresh story:
            # nothing has archived a URL submitted hours ago, so the lookup is
            # a guaranteed miss that every failed scrape was paying for.
            if (
                submitted_hours_ago is not None
                and submitted_hours_ago < MIN_HOURS_FOR_ARCHIVE
            ):
                logger.info(
                    f"Skipping Wayback for {url}: submitted "
                    f"{submitted_hours_ago:.1f}h ago, too recent to be archived"
                )
                return ScrapedContent(
                    title="Error", content="", url=url, success=False,
                    error=f"Scraping failed, too recent for a Wayback archive: {e}",
                )
            wayback_url = get_wayback_url(url)
            if wayback_url:
                try:
                    logger.info(
                        f"Attempting to scrape Wayback Machine URL: {wayback_url}"
                    )
                    archived = self._scrape_with_local_firecrawl(wayback_url)
                    # An archive can "succeed" while returning the archived
                    # copy of an error page. Observed: 43 characters of an HTTP
                    # status page, recorded as source="wayback", fallback=False
                    # — so everything downstream read it as a real article.
                    # Real scrapes in this corpus average ~18,000 characters.
                    if len(archived.content or "") < MIN_ARCHIVE_CHARS:
                        raise RuntimeError(
                            f"Wayback archive has only "
                            f"{len(archived.content or '')} chars — an error "
                            f"page, not the article"
                        )
                    archived.source = "wayback"
                    return archived
                except Exception as wayback_error:
                    logger.error(
                        f"Failed to scrape Wayback Machine URL {wayback_url}: {wayback_error}"
                    )
                    return ScrapedContent(
                        title="Error",
                        content="",
                        url=url,
                        success=False,
                        error=f"Original failed: {e}. Wayback failed: {wayback_error}",
                    )
            else:
                logger.error(f"No Wayback Machine archive available for {url}")
                return ScrapedContent(
                    title="Error",
                    content="",
                    url=url,
                    success=False,
                    error=f"Scraping failed and no Wayback Machine archive available: {e}",
                )

    def _scrape_with_local_firecrawl(self, url: str) -> ScrapedContent:
        """Scrape using local Firecrawl (current v1 API)."""
        data = {
            "url": url,
            # `links` as well as markdown: context_links follows a couple of
            # high-value ones (the paper, the About page). Firecrawl collects
            # them from the whole document, so this is not affected by
            # onlyMainContent/includeTags narrowing the markdown below.
            "formats": ["markdown", "links"],
            "onlyMainContent": True,
            "includeTags": ["h1", "h2", "h3", "p", "article"],
            "excludeTags": ["nav", "footer", "aside", "script", "style"],
        }

        response = requests.post(f"{self.base_url}/v1/scrape", json=data, timeout=60)

        if response.status_code != 200:
            raise RuntimeError(f"Local Firecrawl error: {response.status_code}")

        result = response.json()
        d = result.get("data", {}) or {}
        meta = d.get("metadata", {}) or {}
        markdown = d.get("markdown", "") or ""
        if not markdown.strip():
            raise RuntimeError("Firecrawl returned empty markdown")

        # Firecrawl returns links either as bare strings or as {url, text}
        # depending on version; normalise so callers see one shape.
        raw_links = d.get("links") or []
        links = [
            {"url": ln, "text": ""} if isinstance(ln, str) else
            {"url": ln.get("url") or ln.get("href") or "", "text": ln.get("text") or ""}
            for ln in raw_links
        ]

        return ScrapedContent(
            title=meta.get("title") or meta.get("ogTitle") or "Unknown Title",
            content=markdown,
            url=url,
            success=True,
            links=[ln for ln in links if ln["url"]],
        )
