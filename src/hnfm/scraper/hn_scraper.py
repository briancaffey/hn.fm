"""Hacker News scraper for hn.fm."""

import requests
import logging
from typing import List, Dict, Any
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
        try:
            # Get top story IDs
            response = requests.get(f"{self.base_url}/topstories.json")
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
                            'id': story.id,
                            'title': story.title,
                            'url': story.url,
                            'score': story.score,
                            'by': story.by,
                            'time': story.time,
                            'descendants': story.descendants,
                            'sticky': False  # Add sticky field for compatibility
                        }
                        stories.append(story_dict)
                except Exception as e:
                    logger.warning(f"Failed to fetch story {story_id}: {e}")
                    continue

            logger.info(f"Retrieved {len(stories)} front page articles")
            return stories

        except Exception as e:
            logger.error(f"Failed to fetch top stories: {e}")
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

            if not data or data.get('type') != 'story':
                return None

            return HNStory(
                id=data.get('id'),
                title=data.get('title', 'Unknown Title'),
                url=data.get('url', ''),
                score=data.get('score', 0),
                by=data.get('by', 'Unknown'),
                time=data.get('time', 0),
                descendants=data.get('descendants', 0)
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

        # Simple selection: highest scoring story with a URL
        valid_stories = [s for s in stories if s.url and s.score > 0]

        if not valid_stories:
            # Fallback to any story with a URL
            valid_stories = [s for s in stories if s.url]

        if not valid_stories:
            # Last resort: any story
            valid_stories = stories

        # Sort by score (descending) and return the best
        best_story = max(valid_stories, key=lambda s: s.score)

        logger.info(f"Selected article: {best_story.title}")
        logger.info(f"URL: {best_story.url}")
        logger.info(f"Score: {best_story.score}")

        return best_story
