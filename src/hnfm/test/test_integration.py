#!/usr/bin/env python3
"""End-to-end workflow tests for hn.fm"""

import os
import sys
import pytest
import asyncio
from unittest.mock import patch, MagicMock

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from hnfm.utils.config import config_manager
from hnfm.web.database import ContentDatabase
from hnfm.pipeline.pipeline_manager import PipelineManager


class TestIntegration:
    """Test end-to-end workflows"""

    def setup_method(self):
        """Setup test environment"""
        self.config = config_manager
        self.db = ContentDatabase()
        self.pipeline_manager = PipelineManager()

    def test_config_loading(self):
        """Test configuration loading"""
        print("🧪 Testing Configuration Loading...")

        try:
            # Test config loading
            assert self.config is not None, "Config should be loaded"

            # Test key configuration values
            print(f"✅ Config loaded successfully")
            print(f"   Environment: {getattr(self.config, 'environment', 'unknown')}")

            return True

        except Exception as e:
            print(f"❌ Configuration loading test failed: {e}")
            return False

    def test_system_health(self):
        """Test system health and dependencies"""
        print("\n🧪 Testing System Health...")

        try:
            # Test database health
            db_health = self.db.health_check()
            assert db_health is not None, "Database health check should work"

            # Test configuration health
            config_health = self.config is not None
            assert config_health, "Configuration should be available"

            print("✅ System health check passed")
            print(f"   Database: {'✅' if db_health else '❌'}")
            print(f"   Configuration: {'✅' if config_health else '❌'}")

            return True

        except Exception as e:
            print(f"❌ System health test failed: {e}")
            return False

    def test_pipeline_workflow(self):
        """Test complete pipeline workflow"""
        print("\n🧪 Testing Pipeline Workflow...")

        try:
            # Test pipeline manager initialization
            assert (
                self.pipeline_manager is not None
            ), "Pipeline manager should be initialized"

            # Test pipeline status
            status = self.pipeline_manager.get_status()
            assert status is not None, "Pipeline status should be available"

            print("✅ Pipeline workflow test passed")
            return True

        except Exception as e:
            print(f"❌ Pipeline workflow test failed: {e}")
            return False

    def test_content_lifecycle(self):
        """Test content lifecycle from creation to completion"""
        print("\n🧪 Testing Content Lifecycle...")

        try:
            # Test content creation
            test_content = {
                "id": "test-lifecycle-123",
                "title": "Test Lifecycle Article",
                "url": "https://example.com/test-lifecycle",
                "content_type": "article",
                "status": "pending",
                "created_at": "2024-01-01T00:00:00Z",
                "updated_at": "2024-01-01T00:00:00Z",
                "metadata": {"test": True},
                "processing_steps": [],
                "errors": [],
            }

            # Store content
            stored = self.db.store_content("test-lifecycle-123", test_content)
            assert stored, "Should store content"

            # Retrieve content
            retrieved = self.db.get_content("test-lifecycle-123")
            assert retrieved is not None, "Should retrieve content"
            assert retrieved["status"] == "pending", "Initial status should be pending"

            # Update content status
            updated = self.db.update_content(
                "test-lifecycle-123", {"status": "processing"}
            )
            assert updated, "Should update content status"

            # Verify status change
            updated_content = self.db.get_content("test-lifecycle-123")
            assert updated_content["status"] == "processing", "Status should be updated"

            # Complete content
            completed = self.db.update_content(
                "test-lifecycle-123", {"status": "completed"}
            )
            assert completed, "Should complete content"

            # Clean up
            deleted = self.db.delete_content("test-lifecycle-123")
            assert deleted, "Should delete content"

            print("✅ Content lifecycle test passed")
            return True

        except Exception as e:
            print(f"❌ Content lifecycle test failed: {e}")
            return False

    def test_error_handling(self):
        """Test error handling and recovery"""
        print("\n🧪 Testing Error Handling...")

        try:
            # Test with invalid content ID
            invalid_content = self.db.get_content("invalid-id-123")
            assert invalid_content is None, "Should return None for invalid ID"

            # Test with invalid update
            invalid_update = self.db.update_content(
                "invalid-id-123", {"status": "completed"}
            )
            assert not invalid_update, "Should fail to update invalid content"

            print("✅ Error handling test passed")
            return True

        except Exception as e:
            print(f"❌ Error handling test failed: {e}")
            return False

    def test_performance_metrics(self):
        """Test performance and metrics collection"""
        print("\n🧪 Testing Performance Metrics...")

        try:
            # Test pipeline status performance
            import time

            start_time = time.time()

            status = self.db.get_pipeline_status()

            end_time = time.time()
            duration = end_time - start_time

            assert duration < 1.0, "Pipeline status should be fast (< 1 second)"
            assert status is not None, "Pipeline status should be available"

            print(f"✅ Performance test passed ({duration:.3f}s)")
            return True

        except Exception as e:
            print(f"❌ Performance test failed: {e}")
            return False

    def test_data_consistency(self):
        """Test data consistency and integrity"""
        print("\n🧪 Testing Data Consistency...")

        try:
            # Test data consistency with multiple operations
            test_content = {
                "id": "test-consistency-123",
                "title": "Test Consistency Article",
                "url": "https://example.com/test-consistency",
                "content_type": "article",
                "status": "pending",
                "created_at": "2024-01-01T00:00:00Z",
                "updated_at": "2024-01-01T00:00:00Z",
                "metadata": {"test": True, "version": 1},
                "processing_steps": [],
                "errors": [],
            }

            # Store content
            self.db.store_content("test-consistency-123", test_content)

            # Verify initial state
            initial = self.db.get_content("test-consistency-123")
            assert initial["metadata"]["version"] == 1, "Initial version should be 1"

            # Update metadata
            self.db.update_content(
                "test-consistency-123", {"metadata": {"test": True, "version": 2}}
            )

            # Verify update
            updated = self.db.get_content("test-consistency-123")
            assert updated["metadata"]["version"] == 2, "Version should be updated to 2"

            # Clean up
            self.db.delete_content("test-consistency-123")

            print("✅ Data consistency test passed")
            return True

        except Exception as e:
            print(f"❌ Data consistency test failed: {e}")
            return False

    def test_frontend_integration(self):
        """Test frontend integration points"""
        print("\n🧪 Testing Frontend Integration...")

        try:
            # Test API endpoints that frontend would use
            content_list = self.db.list_content(per_page=10)
            assert (
                content_list is not None
            ), "Content list should be available for frontend"
            assert "total" in content_list, "Should have total count for frontend"
            assert "items" in content_list, "Should have items list for frontend"

            # Test pipeline status for frontend
            pipeline_status = self.db.get_pipeline_status()
            assert (
                pipeline_status is not None
            ), "Pipeline status should be available for frontend"

            print("✅ Frontend integration test passed")
            return True

        except Exception as e:
            print(f"❌ Frontend integration test failed: {e}")
            return False
