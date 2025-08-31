"""Hacker News API service for fetching stories and data"""

import time
import logging
import requests
from typing import List, Optional, Dict, Any
from ..web.models import HNStoryData

logger = logging.getLogger(__name__)


class HackerNewsService:
    """Service for interacting with the Hacker News API"""

    BASE_URL = "https://hacker-news.firebaseio.com/v0"

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'hn.fm/1.0 (https://github.com/yourusername/hn.fm)'
        })

    def get_top_stories(self, limit: int = 100) -> List[int]:
        """
        Fetch the top stories from Hacker News

        Args:
            limit: Maximum number of story IDs to return

        Returns:
            List of story IDs (integers)
        """
        try:
            url = f"{self.BASE_URL}/topstories.json"
            response = self.session.get(url, timeout=10)
            response.raise_for_status()

            story_ids = response.json()
            if isinstance(story_ids, list):
                return story_ids[:limit]
            else:
                logger.error(f"Unexpected response format from HN API: {type(story_ids)}")
                return []

        except requests.RequestException as e:
            logger.error(f"Failed to fetch top stories: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error fetching top stories: {e}")
            return []

    def get_story(self, story_id: int) -> Optional[HNStoryData]:
        """
        Fetch a specific story by ID from Hacker News

        Args:
            story_id: The HN story ID

        Returns:
            HNStoryData object if successful, None otherwise
        """
        try:
            # Add 3 second delay as requested
            time.sleep(3)

            url = f"{self.BASE_URL}/item/{story_id}.json"
            response = self.session.get(url, timeout=10)
            response.raise_for_status()

            story_data = response.json()
            if not story_data:
                logger.warning(f"No data returned for story {story_id}")
                return None

            # Validate that this is actually a story
            if story_data.get('type') != 'story':
                logger.info(f"Item {story_id} is not a story (type: {story_data.get('type')})")
                return None

            # Convert to our model
            return HNStoryData(**story_data)

        except requests.RequestException as e:
            logger.error(f"Failed to fetch story {story_id}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error fetching story {story_id}: {e}")
            return None

    def get_stories_batch(self, story_ids: List[int]) -> List[HNStoryData]:
        """
        Fetch multiple stories in batch with delays

        Args:
            story_ids: List of story IDs to fetch

        Returns:
            List of successfully fetched HNStoryData objects
        """
        stories = []

        for story_id in story_ids:
            story = self.get_story(story_id)
            if story:
                stories.append(story)
            else:
                logger.warning(f"Failed to fetch story {story_id}")

        return stories

    def health_check(self) -> bool:
        """
        Check if the HN API is accessible

        Returns:
            True if API is accessible, False otherwise
        """
        try:
            response = self.session.get(f"{self.BASE_URL}/topstories.json", timeout=5)
            return response.status_code == 200
        except Exception:
            return False
