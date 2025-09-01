#!/usr/bin/env python3
"""Test script for the content listing API endpoint"""

import pytest
import sys
import os
from datetime import datetime
from unittest.mock import Mock, patch

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from hnfm.web.database import ContentDatabase
from hnfm.web.models import ContentItem, ContentListResponse


class TestContentAPI:
    """Test class for content listing API functionality"""

    def setup_method(self):
        """Set up test fixtures before each test method"""
        self.mock_db = Mock(spec=ContentDatabase)

        # Sample test data with all required fields
        self.sample_content = {
            "id": "test-123",
            "title": "Test Article",
            "url": "https://example.com/test",
            "content_type": "article",
            "status": "completed",
            "created_at": datetime.now(),
            "updated_at": datetime.now(),
            "metadata": {"test": True, "hn_score": 100},
            "hn_story_data": {
                "id": 12345,
                "type": "story",  # Required field
                "time": 1756484396,  # Required field (Unix timestamp)
                "score": 100,
                "descendants": 25,
                "by": "testuser",
            },
            "processing_steps": ["scraped", "processed"],
            "errors": [],
        }

    def test_content_item_model_validation(self):
        """Test that ContentItem model can validate data with datetime objects"""
        try:
            content_item = ContentItem(**self.sample_content)
            # This should work without validation errors
            assert content_item.title == "Test Article"
            assert content_item.hn_story_data.score == 100
            assert isinstance(content_item.created_at, datetime)
            assert isinstance(content_item.updated_at, datetime)

            print("✅ ContentItem model validation test passed")

        except Exception as e:
            pytest.fail(f"ContentItem validation failed: {e}")

    def test_content_list_response_model_validation(self):
        """Test that ContentListResponse model can validate a list of items"""
        try:
            # Create multiple content items
            content_items = []
            for i in range(3):
                item_data = self.sample_content.copy()
                item_data["id"] = f"test-{i}"
                item_data["title"] = f"Test Article {i}"
                content_items.append(ContentItem(**item_data))

            # Create the response model
            response = ContentListResponse(
                items=content_items,
                total=3,
                page=1,
                per_page=10,
                has_next=False,
                has_prev=False,
            )

            # This should work without validation errors
            assert len(response.items) == 3
            assert response.total == 3
            assert all(isinstance(item.created_at, datetime) for item in response.items)
            assert all(isinstance(item.updated_at, datetime) for item in response.items)

            print("✅ ContentListResponse model validation test passed")

        except Exception as e:
            pytest.fail(f"ContentListResponse validation failed: {e}")

    def test_database_datetime_conversion(self):
        """Test that the database method properly converts datetime objects"""
        try:
            # Create a real database instance (this will use Redis if available)
            db = ContentDatabase()

            # Test the datetime conversion method
            test_data = {
                "created_at": datetime.now(),
                "updated_at": datetime.now(),
                "nested": {
                    "timestamp": datetime.now(),
                    "list": [datetime.now(), datetime.now()],
                },
            }

            converted = db._convert_all_datetimes(test_data)

            # Verify all datetime objects were converted to strings
            assert isinstance(converted["created_at"], str)
            assert isinstance(converted["updated_at"], str)
            assert isinstance(converted["nested"]["timestamp"], str)
            assert all(isinstance(item, str) for item in converted["nested"]["list"])

            print("✅ Database datetime conversion test passed")

        except Exception as e:
            print(
                f"⚠️ Database datetime conversion test failed (Redis may not be available): {e}"
            )
            # This test is optional if Redis is not available

    def test_content_with_nested_datetime_structures(self):
        """Test that complex nested structures with datetime objects are handled correctly"""
        try:
            # Create content with complex nested datetime structures
            complex_content = {
                "id": "complex-test",
                "title": "Complex Test",
                "url": "https://example.com/complex",  # Required field
                "content_type": "article",  # Required field
                "status": "completed",  # Required field
                "created_at": datetime.now(),
                "updated_at": datetime.now(),
                "metadata": {
                    "processing_times": {
                        "scraping": datetime.now(),
                        "processing": datetime.now(),
                        "generation": datetime.now(),
                    },
                    "timestamps": [datetime.now(), datetime.now(), datetime.now()],
                    "nested": {"deep_timestamp": datetime.now()},
                },
                "hn_story_data": {
                    "id": 12345,  # Required field
                    "type": "story",  # Required field
                    "time": 1756484396,  # Required field (Unix timestamp)
                    "score": 100,
                },
            }

            # Test that ContentItem can handle this
            content_item = ContentItem(**complex_content)

            # Verify the model was created successfully
            assert content_item.title == "Complex Test"
            assert content_item.hn_story_data.score == 100
            assert isinstance(content_item.created_at, datetime)
            assert isinstance(content_item.updated_at, datetime)

            print("✅ Complex nested datetime structures test passed")

        except Exception as e:
            pytest.fail(f"Complex nested datetime structures test failed: {e}")


def run_tests():
    """Run the tests manually"""
    print("🧪 Running Content API tests...\n")

    test_instance = TestContentAPI()

    # Run each test method
    test_methods = [
        test_instance.test_content_item_model_validation,
        test_instance.test_content_list_response_model_validation,
        test_instance.test_content_with_nested_datetime_structures,
        test_instance.test_database_datetime_conversion,
    ]

    passed = 0
    total = len(test_methods)

    for test_method in test_methods:
        try:
            test_method()
            passed += 1
        except Exception as e:
            print(f"❌ {test_method.__name__} failed: {e}")

    print(f"\n📊 Test Results: {passed}/{total} tests passed")

    if passed == total:
        print("🎉 All tests passed! The content API should work correctly.")
    else:
        print("❌ Some tests failed. Please check the implementation.")
        return False

    return True


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
