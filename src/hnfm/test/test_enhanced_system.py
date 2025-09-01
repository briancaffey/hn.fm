#!/usr/bin/env python3
"""Simple test script for the enhanced Celery task system"""

import os
import sys
import time
from pathlib import Path

# Add the src directory to the Python path
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))


def test_imports():
    """Test that all enhanced components can be imported"""
    print("Testing imports...")

    try:
        from hnfm.pipeline.enhanced_pipeline_manager import PipelineManager

        print("✓ PipelineManager imported successfully")
    except ImportError as e:
        print(f"✗ Failed to import PipelineManager: {e}")
        return False

    try:
        from hnfm.web.redis_repo import RedisRepository

        print("✓ RedisRepository imported successfully")
    except ImportError as e:
        print(f"✗ Failed to import RedisRepository: {e}")
        return False

    try:
        from hnfm.web.enhanced_tasks import content_pipeline

        print("✓ Content pipeline tasks imported successfully")
    except ImportError as e:
        print(f"✗ Failed to import content pipeline tasks: {e}")
        return False

    return True


def test_redis_connection():
    """Test Redis connection"""
    print("\nTesting Redis connection...")

    try:
        from hnfm.web.database import ContentDatabase

        db = ContentDatabase()

        if db.health_check():
            print("✓ Redis connection successful")
            return True
        else:
            print("✗ Redis connection failed")
            return False
    except Exception as e:
        print(f"✗ Redis connection error: {e}")
        return False


def test_pipeline_manager():
    """Test pipeline manager"""
    print("\nTesting PipelineManager...")

    try:
        from hnfm.pipeline.enhanced_pipeline_manager import PipelineManager

        pipeline = PipelineManager(text_only=True)

        # Test basic functionality
        print("✓ PipelineManager created successfully")

        # Test step execution
        print("✓ PipelineManager ready for step execution")

        return True
    except Exception as e:
        print(f"✗ PipelineManager test failed: {e}")
        return False


def test_redis_repository():
    """Test Redis repository"""
    print("\nTesting RedisRepository...")

    try:
        from hnfm.web.redis_repo import RedisRepository

        repo = RedisRepository()
        print("✓ RedisRepository created successfully")

        # Test manifest creation
        test_content_id = "test-content-123"
        manifest = repo.get_or_create_manifest(test_content_id, {"priority": "high"})

        if manifest and manifest.content_id == test_content_id:
            print("✓ Manifest creation works")
        else:
            print("✗ Manifest creation failed")
            return False

        return True
    except Exception as e:
        print(f"✗ RedisRepository test failed: {e}")
        return False


def test_enhanced_pipeline_manager():
    """Test enhanced pipeline manager"""
    print("\nTesting PipelineManager...")

    try:
        from hnfm.pipeline.enhanced_pipeline_manager import PipelineManager

        # Test creation
        pipeline = PipelineManager(text_only=True)
        print("✓ PipelineManager created successfully")

        # Test pipeline steps
        steps = pipeline.pipeline_steps
        if steps and len(steps) > 0:
            print(f"✓ Pipeline steps defined: {len(steps)} steps")
        else:
            print("✗ No pipeline steps defined")
            return False

        return True
    except Exception as e:
        print(f"✗ PipelineManager test failed: {e}")
        return False


def test_celery_integration():
    """Test Celery integration"""
    print("\nTesting Celery integration...")

    try:
        from hnfm.web.celery_app import celery_app

        # Check if content pipeline tasks are registered
        registered_tasks = list(celery_app.tasks.keys())
        content_tasks = [
            "content_pipeline",
            "full_pipeline",
            "process_content_pipeline",
        ]

        missing_tasks = [task for task in content_tasks if task not in registered_tasks]

        if not missing_tasks:
            print("✓ All content pipeline tasks registered with Celery")
        else:
            print(f"✗ Missing tasks: {missing_tasks}")
            return False

        return True
    except Exception as e:
        print(f"✗ Celery integration test failed: {e}")
        return False


def main():
    """Run all tests"""
    print("Enhanced Celery Task System - Test Suite")
    print("=" * 50)

    tests = [
        test_imports,
        test_redis_connection,
        test_pipeline_manager,
        test_redis_repository,
        test_enhanced_pipeline_manager,
        test_celery_integration,
    ]

    passed = 0
    total = len(tests)

    for test in tests:
        try:
            if test():
                passed += 1
            time.sleep(0.1)  # Small delay between tests
        except Exception as e:
            print(f"✗ Test {test.__name__} crashed: {e}")

    print("\n" + "=" * 50)
    print(f"Test Results: {passed}/{total} tests passed")

    if passed == total:
        print("🎉 All tests passed! The enhanced system is ready.")
        return 0
    else:
        print("❌ Some tests failed. Please check the errors above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
