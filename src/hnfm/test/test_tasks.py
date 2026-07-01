"""Tests for Celery tasks (called directly against the test DB)."""

import json
import os
from unittest.mock import Mock, patch

from ..db import repo
from ..web.tasks import hn_fetch_item
from ..web.models import HNItem


class TestCeleryTask:
    """Test Celery task functionality"""

    @patch("requests.get")
    def test_hn_fetch_item_exists_short_circuits(self, mock_get):
        """Test hn_fetch_item short circuits when item already exists"""
        # Seed an existing item in the database
        repo.upsert_item(HNItem(id=7))

        # Mock requests.get to raise if called (ensure no HTTP)
        mock_get.side_effect = Exception("Should not be called")

        # Call the task directly (not via worker)
        result = hn_fetch_item(7)

        # Assertions
        assert result == {"status": "exists", "id": 7}
        mock_get.assert_not_called()

    @patch("requests.get")
    def test_hn_fetch_item_fetches_when_missing(self, mock_get, outputs_root):
        """Test hn_fetch_item fetches when item is missing"""
        # Mock the HTTP response
        mock_response = Mock()
        mock_response.json.return_value = {"id": 8, "type": "story"}
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        # Call the task directly
        result = hn_fetch_item(8)

        # Assertions
        assert result == {"status": "fetched", "id": 8}

        # Check that the item was stored in the database
        stored_item = repo.get_item(8)
        assert stored_item is not None
        assert stored_item.id == 8
        assert stored_item.type == "story"

        # Check that the item was mirrored to disk
        item_file = os.path.join(outputs_root, "hn", "item", "8", "item.json")
        assert os.path.exists(item_file)
        with open(item_file, "r", encoding="utf-8") as f:
            stored_data = json.load(f)
        assert stored_data["id"] == 8
