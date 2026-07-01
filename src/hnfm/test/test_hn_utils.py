"""Tests for Hacker News utilities (Postgres-backed via the sqlite test DB)"""

import json
from unittest.mock import Mock, patch

from ..db import repo
from ..utils.hn_utils import (
    get_top_story_ids,
    get_item_json_and_store,
    exists_item,
    get_item,
    list_item_ids,
    list_items,
    count_items,
)
from ..web.models import HNItem


class TestHTTPFunctions:
    """Test HTTP (Firebase) functions"""

    @patch("requests.get")
    def test_get_top_story_ids_returns_list(self, mock_get):
        """Test get_top_story_ids returns a list of integers"""
        # Mock the response
        mock_response = Mock()
        mock_response.json.return_value = [1, 2, 3]
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        # Call the function
        result = get_top_story_ids()

        # Assertions
        assert result == [1, 2, 3]
        assert isinstance(result, list)
        assert all(isinstance(x, int) for x in result)
        mock_get.assert_called_once_with(
            "https://hacker-news.firebaseio.com/v0/topstories.json"
        )

    @patch("requests.get")
    def test_get_item_json_and_store_saves_db_and_file(self, mock_get, tmp_path):
        """Test get_item_json_and_store saves to the database and file"""
        # Mock the response
        mock_response = Mock()
        mock_response.json.return_value = {
            "id": 1,
            "type": "story",
            "time": 1000,
            "title": "T",
            "by": "u",
        }
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        # Call the function
        result = get_item_json_and_store(1, outputs_dir=str(tmp_path))

        # Assertions
        assert isinstance(result, HNItem)
        assert result.id == 1
        assert result.type == "story"
        assert result.time == 1000
        assert result.title == "T"
        assert result.by == "u"

        # Check database storage via the public helpers
        stored_item = get_item(1)
        assert stored_item is not None
        assert stored_item.id == 1
        assert stored_item.title == "T"

        # Check file storage
        item_file = tmp_path / "hn" / "item" / "1" / "item.json"
        assert item_file.exists()
        with open(item_file) as f:
            file_content = json.load(f)
            assert file_content["id"] == 1


class TestDbHelpers:
    """Test database helper functions"""

    def test_exists_and_get_item_helpers(self):
        """Test exists_item and get_item helpers"""
        # Seed the database with an item
        repo.upsert_item(HNItem(id=5))

        # Test exists_item
        assert exists_item(5) is True
        assert exists_item(999) is False

        # Test get_item
        item = get_item(5)
        assert item is not None
        assert item.id == 5

        # Test get_item with non-existent item
        assert get_item(999) is None

    def test_list_items_orders_desc_and_paginates(self):
        """Test list_items orders by ID descending and paginates correctly"""
        # Seed the database with items in random order
        for item_id in [1, 10, 3]:
            repo.upsert_item(HNItem(id=item_id))

        # Test first page (offset=0, limit=2)
        items = list_items(offset=0, limit=2)
        assert len(items) == 2
        assert items[0].id == 10  # Largest ID first
        assert items[1].id == 3

        # Test second page (offset=2, limit=2)
        items = list_items(offset=2, limit=2)
        assert len(items) == 1
        assert items[0].id == 1

        # count_items reflects the total for pagination
        assert count_items() == 3

    def test_list_item_ids_returns_all_ids(self):
        """Test list_item_ids returns all stored item IDs"""
        # Seed the database with multiple items
        for item_id in [1, 5, 10, 15]:
            repo.upsert_item(HNItem(id=item_id))

        # Get all IDs
        ids = list_item_ids()

        # Should return all IDs (order doesn't matter for this test)
        assert set(ids) == {1, 5, 10, 15}
        assert all(isinstance(x, int) for x in ids)
