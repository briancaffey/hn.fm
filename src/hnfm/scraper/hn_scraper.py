"""Hacker News scraper for hn.fm."""

import requests
from typing import List, Dict, Any
import logging

logger = logging.getLogger(__name__)


class HNScraper:
    """Scrapes content from Hacker News."""

    def __init__(self, user_agent: str = "hn.fm/0.1.0"):
        """Initialize the HN scraper.

        Args:
            user_agent: User agent string for requests
        """
        self.user_agent = user_agent
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": user_agent})

    def get_top_stories(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get top stories from Hacker News.

        Args:
            limit: Maximum number of stories to return

        Returns:
            List of story dictionaries
        """
        try:
            # Get top story IDs
            response = self.session.get(
                "https://hacker-news.firebaseio.com/v0/topstories.json"
            )
            response.raise_for_status()
            story_ids = response.json()[:limit]

            stories = []
            for story_id in story_ids:
                story = self.get_story(story_id)
                if story:
                    stories.append(story)

            return stories

        except Exception as e:
            logger.error(f"Error fetching top stories: {e}")
            return []

    def get_story(self, story_id: int) -> Dict[str, Any]:
        """Get a specific story by ID.

        Args:
            story_id: Hacker News story ID

        Returns:
            Story dictionary or None if error
        """
        try:
            url = f"https://hacker-news.firebaseio.com/v0/item/{story_id}.json"
            response = self.session.get(url)
            response.raise_for_status()
            return response.json()

        except Exception as e:
            logger.error(f"Error fetching story {story_id}: {e}")
            return None

    def get_story_urls(self, limit: int = 10) -> List[str]:
        """Get URLs from top stories.

        Args:
            limit: Maximum number of URLs to return

        Returns:
            List of URLs
        """
        stories = self.get_top_stories(limit)
        urls = []

        for story in stories:
            if story.get("url"):
                urls.append(story["url"])

        return urls
