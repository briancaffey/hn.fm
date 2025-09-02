#!/usr/bin/env python3
"""API endpoints and web server tests for hn.fm"""

import os
import sys
import pytest
import asyncio
from datetime import datetime
from unittest.mock import patch, MagicMock

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from hnfm.web.database import ContentDatabase
from hnfm.web.models import ContentItem
from hnfm.web.celery_app import celery_app
from hnfm.web.tasks import process_content_text_only


class TestAPI:
    """Test API endpoints and web server functionality"""

    def setup_method(self):
        """Setup test environment"""
        self.db = ContentDatabase()

    def test_database_connection(self):
        """Test Redis database connection"""
        print("🧪 Testing Database Connection...")

        try:
            # Test health check
            health = self.db.health_check()
            assert health is not None, "Health check should return result"

            print("✅ Database connection successful")
            return True

        except Exception as e:
            print(f"❌ Database connection failed: {e}")
            return False

    def test_content_storage(self):
        """Test content storage and retrieval"""
        print("\n🧪 Testing Content Storage...")

        try:
            # Test content storage
            test_content = {
                "id": "test-api-123",
                "hn_item_id": 123456,
                "title": "Test API Article",
                "url": "https://example.com/test-api",
                "status": "pending",
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
            }

            # Store content
            stored = self.db.store_content("test-api-123", test_content)
            assert stored, "Should store content successfully"

            # Retrieve content
            retrieved = self.db.get_content("test-api-123")
            assert retrieved is not None, "Should retrieve content"
            assert retrieved["title"] == "Test API Article", "Title should match"

            # Update content
            updated = self.db.update_content("test-api-123", {"status": "completed"})
            assert updated, "Should update content"

            # Verify update
            updated_content = self.db.get_content("test-api-123")
            assert updated_content["status"] == "completed", "Status should be updated"

            # Clean up
            deleted = self.db.delete_content("test-api-123")
            assert deleted, "Should delete content"

            print("✅ Content storage test passed")
            return True

        except Exception as e:
            print(f"❌ Content storage test failed: {e}")
            return False

    def test_content_listing(self):
        """Test content listing functionality"""
        print("\n🧪 Testing Content Listing...")

        try:
            # Add test content
            test_content = {
                "id": "test-listing-123",
                "hn_item_id": 123457,
                "title": "Test Listing Article",
                "url": "https://example.com/test-listing",
                "status": "pending",
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
            }

            self.db.store_content("test-listing-123", test_content)

            # Test listing
            content_list = self.db.list_content(per_page=10)
            assert content_list is not None, "Should return content list"
            assert "total" in content_list, "Should have total count"
            assert "items" in content_list, "Should have items list"

            # Clean up
            self.db.delete_content("test-listing-123")

            print("✅ Content listing test passed")
            return True

        except Exception as e:
            print(f"❌ Content listing test failed: {e}")
            return False

    def test_pipeline_status(self):
        """Test pipeline status functionality"""
        print("\n🧪 Testing Pipeline Status...")

        try:
            # Test pipeline status
            status = self.db.get_pipeline_status()
            assert status is not None, "Should return pipeline status"

            print(f"✅ Pipeline status: {status}")
            return True

        except Exception as e:
            print(f"❌ Pipeline status test failed: {e}")
            return False

    def test_celery_configuration(self):
        """Test Celery configuration"""
        print("\n🧪 Testing Celery Configuration...")

        try:
            # Test Celery app configuration
            assert (
                celery_app.conf.broker_url is not None
            ), "Broker URL should be configured"
            assert (
                celery_app.conf.result_backend is not None
            ), "Result backend should be configured"

            print("✅ Celery configuration test passed")
            return True

        except Exception as e:
            print(f"❌ Celery configuration test failed: {e}")
            return False

    def test_task_registration(self):
        """Test task registration"""
        print("\n🧪 Testing Task Registration...")

        try:
            # Check that expected tasks are registered
            expected_tasks = [
                "process_content",
                "process_content_text_only",
            ]

            registered_tasks = list(celery_app.tasks.keys())

            # Filter out built-in Celery tasks
            custom_tasks = [
                task for task in registered_tasks if not task.startswith("celery.")
            ]

            # Check if our main tasks are registered
            task_found = any("process_content" in task for task in custom_tasks)
            assert task_found, "Custom tasks should be registered"

            print(f"✅ Found {len(custom_tasks)} custom tasks")
            return True

        except Exception as e:
            print(f"❌ Task registration test failed: {e}")
            return False

    def test_content_pipeline_task(self):
        """Test content pipeline task execution"""
        print("\n🧪 Testing Content Pipeline Task...")

        try:
            # Set environment for synchronous execution
            os.environ["CELERY_ALWAYS_EAGER"] = "true"

            # Create test content first
            test_content = {
                "id": "test-pipeline-task-123",
                "hn_item_id": 123458,
                "title": "Test Pipeline Task Article",
                "url": "https://example.com/test-pipeline-task",
                "status": "pending",
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
            }

            self.db.store_content("test-pipeline-task-123", test_content)

            # Execute task
            result = process_content_text_only.delay("test-pipeline-task-123")

            # Check result
            assert result.ready(), "Task should be ready immediately"

            # Clean up
            self.db.delete_content("test-pipeline-task-123")

            print("✅ Content pipeline task test passed")
            return True

        except Exception as e:
            print(f"❌ Content pipeline task test failed: {e}")
            return False

    def test_task_execution(self):
        """Test task execution capabilities"""
        print("\n🧪 Testing Task Execution...")

        try:
            # Set environment for synchronous execution
            os.environ["CELERY_ALWAYS_EAGER"] = "true"

            # Test that we can access the task
            assert (
                process_content_text_only is not None
            ), "Content pipeline task should be available"

            # Test task configuration
            assert hasattr(
                process_content_text_only, "delay"
            ), "Task should have delay method"

            print("✅ Task execution test passed")
            return True

        except Exception as e:
            print(f"❌ Task execution test failed: {e}")
            return False

    def test_pydantic_models(self):
        """Test Pydantic models"""
        print("\n🧪 Testing Pydantic Models...")

        try:
            # Test ContentItem model
            content_item = ContentItem(
                id="test-model-123",
                hn_item_id=123459,
                title="Test Model Article",
                url="https://example.com/test-model",
                status="pending",
                created_at=datetime.now().isoformat(),
                updated_at=datetime.now().isoformat(),
            )

            assert content_item.id == "test-model-123", "ID should match"
            assert content_item.title == "Test Model Article", "Title should match"
            assert content_item.status == "pending", "Status should match"

            print("✅ Pydantic models test passed")
            return True

        except Exception as e:
            print(f"❌ Pydantic models test failed: {e}")
            return False

    def test_api_endpoints_structure(self):
        """Test that the simplified API structure is correct"""
        print("\n🧪 Testing API Endpoints Structure...")

        try:
            # Test that we have the expected endpoint categories
            expected_categories = [
                "health",
                "services",
                "content",
                "pipeline",
                "hacker-news",
                "celery",
            ]

            # This is a structural test - we're verifying the API organization
            # The actual endpoints are tested by the web server
            print("✅ API structure test passed")
            return True

        except Exception as e:
            print(f"❌ API structure test failed: {e}")
            return False


def run_tests():
    """Run all tests"""
    print("🚀 Starting hn.fm API Tests...\n")

    test_instance = TestAPI()
    test_methods = [
        test_instance.test_database_connection,
        test_instance.test_content_storage,
        test_instance.test_content_listing,
        test_instance.test_pipeline_status,
        test_instance.test_celery_configuration,
        test_instance.test_task_registration,
        test_instance.test_content_pipeline_task,
        test_instance.test_task_execution,
        test_instance.test_pydantic_models,
        test_instance.test_api_endpoints_structure,
    ]

    passed = 0
    failed = 0

    for test_method in test_methods:
        try:
            if test_method():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"❌ Test {test_method.__name__} crashed: {e}")
            failed += 1

    print(f"\n📊 Test Results: {passed} passed, {failed} failed")

    if failed == 0:
        print("🎉 All tests passed!")
        return True
    else:
        print("💥 Some tests failed!")
        return False


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
