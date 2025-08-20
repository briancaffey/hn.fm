"""Hacker News scraper for hn.fm."""

import requests
import logging
from typing import List, Dict, Any, Literal
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class HNStory:
    """Represents a Hacker News story."""

    id: int
    title: str
    url: str
    score: int
    by: str
    time: int
    descendants: int


class HNScraper:
    """Scrapes Hacker News for interesting stories."""

    # Available story types
    STORY_TYPES = Literal["top", "newest", "show", "ask"]

    def __init__(self):
        """Initialize the HN scraper."""
        self.base_url = "https://hacker-news.firebaseio.com/v0"
        self.user_agent = "hn.fm/0.1.0 (briancaffey)"

    def get_front_page_articles(self, limit: int = 30) -> List[Dict[str, Any]]:
        """Get front page articles from Hacker News (alias for get_top_stories)."""
        return self.get_top_stories(limit)

    def get_top_stories(self, limit: int = 30) -> List[Dict[str, Any]]:
        """Get top stories from Hacker News.

        Args:
            limit: Maximum number of stories to fetch

        Returns:
            List of story dictionaries
        """
        return self.get_stories_by_type("top", limit)

    def get_newest_stories(self, limit: int = 30) -> List[Dict[str, Any]]:
        """Get newest stories from Hacker News.

        Args:
            limit: Maximum number of stories to fetch

        Returns:
            List of story dictionaries
        """
        return self.get_stories_by_type("newest", limit)

    def get_show_stories(self, limit: int = 30) -> List[Dict[str, Any]]:
        """Get Show HN stories from Hacker News.

        Args:
            limit: Maximum number of stories to fetch

        Returns:
            List of story dictionaries
        """
        return self.get_stories_by_type("show", limit)

    def get_ask_stories(self, limit: int = 30) -> List[Dict[str, Any]]:
        """Get Ask HN stories from Hacker News.

        Args:
            limit: Maximum number of stories to fetch

        Returns:
            List of story dictionaries
        """
        return self.get_stories_by_type("ask", limit)

    def get_stories_by_type(self, story_type: STORY_TYPES, limit: int = 30) -> List[Dict[str, Any]]:
        """Get stories by type from Hacker News.

        Args:
            story_type: Type of stories to fetch ("top", "newest", "show", "ask")
            limit: Maximum number of stories to fetch

        Returns:
            List of story dictionaries
        """
        try:
            # Map story type to API endpoint
            endpoint_map = {
                "top": "topstories",
                "newest": "newstories",
                "show": "showstories",
                "ask": "askstories"
            }

            endpoint = endpoint_map.get(story_type)
            if not endpoint:
                raise ValueError(f"Invalid story type: {story_type}. Must be one of {list(endpoint_map.keys())}")

            # Get story IDs from the appropriate endpoint
            response = requests.get(f"{self.base_url}/{endpoint}.json")
            response.raise_for_status()
            story_ids = response.json()[:limit]

            # Fetch individual story details
            stories = []
            for story_id in story_ids:
                try:
                    story = self._get_story(story_id)
                    if story:
                        # Convert to dictionary
                        story_dict = {
                            "id": story.id,
                            "title": story.title,
                            "url": story.url,
                            "score": story.score,
                            "by": story.by,
                            "time": story.time,
                            "descendants": story.descendants,
                            "sticky": False,  # Add sticky field for compatibility
                            "type": story_type,  # Add story type for reference
                        }
                        stories.append(story_dict)
                except Exception as e:
                    logger.warning(f"Failed to fetch story {story_id}: {e}")
                    continue

            logger.info(f"Retrieved {len(stories)} {story_type} stories")
            return stories

        except Exception as e:
            logger.error(f"Failed to fetch {story_type} stories: {e}")
            return []

    def _get_story(self, story_id: int) -> HNStory:
        """Get a single story by ID.

        Args:
            story_id: Hacker News story ID

        Returns:
            HNStory object or None if failed
        """
        try:
            response = requests.get(f"{self.base_url}/item/{story_id}.json")
            response.raise_for_status()
            data = response.json()

            if not data or data.get("type") != "story":
                return None

            return HNStory(
                id=data.get("id"),
                title=data.get("title", "Unknown Title"),
                url=data.get("url", ""),
                score=data.get("score", 0),
                by=data.get("by", "Unknown"),
                time=data.get("time", 0),
                descendants=data.get("descendants", 0),
            )

        except Exception as e:
            logger.warning(f"Failed to fetch story {story_id}: {e}")
            return None

    def select_best_story(self, stories: List[HNStory]) -> HNStory:
        """Select the best story based on criteria.

        Args:
            stories: List of HNStory objects

        Returns:
            Selected HNStory
        """
        if not stories:
            return None

        # Define problematic domains to avoid
        problematic_domains = [
            "biglobe.ne.jp",  # Japanese website causing Firecrawl 500 errors
            "youtube.com",    # Video content not suitable for text processing
            "youtu.be",       # YouTube short links
            "paywall.com",    # Paywall sites
            "medium.com",     # Often behind paywalls
        ]

        # Filter out stories with problematic URLs
        def is_problematic_url(url: str) -> bool:
            if not url:
                return True
            return any(domain in url.lower() for domain in problematic_domains)

        # Simple selection: highest scoring story with a valid URL
        valid_stories = [s for s in stories if s.url and s.score > 0 and not is_problematic_url(s.url)]

        if not valid_stories:
            # Fallback to any story with a valid URL
            valid_stories = [s for s in stories if s.url and not is_problematic_url(s.url)]

        if not valid_stories:
            # Last resort: any story (but still avoid problematic URLs)
            valid_stories = [s for s in stories if not is_problematic_url(s.url)]

        if not valid_stories:
            logger.warning("No valid stories found after filtering problematic URLs")
            return None

        # Sort by score (descending) and return the best
        best_story = max(valid_stories, key=lambda s: s.score)

        logger.info(f"Selected article: {best_story.title}")
        logger.info(f"URL: {best_story.url}")
        logger.info(f"Score: {best_story.score}")

        return best_story
