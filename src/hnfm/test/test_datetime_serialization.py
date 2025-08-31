#!/usr/bin/env python3
"""Comprehensive test for datetime serialization throughout the pipeline"""

import sys
import json
import traceback
from pathlib import Path
from datetime import datetime
from typing import Any, Dict

# Add the src directory to the Python path
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

def test_datetime_serialization():
    """Test datetime serialization at each step of the pipeline"""
    print("🔍 Testing DateTime Serialization End-to-End")
    print("=" * 60)

    tests = [
        test_models_serialization,
        test_redis_repository_serialization,
        test_enhanced_pipeline_manager_serialization,
        test_api_endpoint_serialization,
        test_lock_manager_serialization
    ]

    passed = 0
    total = len(tests)

    for test in tests:
        try:
            if test():
                passed += 1
                print(f"✅ {test.__name__} passed")
            else:
                print(f"❌ {test.__name__} failed")
        except Exception as e:
            print(f"💥 {test.__name__} crashed: {e}")
            traceback.print_exc()

    print(f"\n📊 Results: {passed}/{total} tests passed")
    return passed == total

def test_models_serialization():
    """Test that all Pydantic models can serialize datetime fields"""
    print("\n1️⃣ Testing Pydantic Models Serialization...")

    try:
        from hnfm.web.models import (
            VersionedSegment, ProcessingManifest, EnhancedPipelineStatus,
            PipelineStepStatus, ServiceLockStatus
        )

        # Test VersionedSegment
        print("  Testing VersionedSegment...")
        segment = VersionedSegment(
            segment_id="test-segment-123",
            content_id="test-content-123",
            step_name="test_step",
            version=1,
            status="processing",
            created_at=datetime.now(),
            completed_at=None,
            artifacts={},
            metadata={},
            error=None,
            processing_time=None,
            retry_count=0
        )

        # Test JSON serialization
        segment_json = segment.json()
        segment_dict = segment.dict()
        print(f"    ✅ VersionedSegment serializes to JSON: {len(segment_json)} chars")

        # Test ProcessingManifest
        print("  Testing ProcessingManifest...")
        manifest = ProcessingManifest(
            content_id="test-content-123",
            current_step="test_step",
            completed_steps=[],
            segments={},
            last_updated=datetime.now(),
            processing_options={},
            pipeline_version="1.0",
            estimated_completion=None,
            priority=1
        )

        manifest_json = manifest.json()
        manifest_dict = manifest.dict()
        print(f"    ✅ ProcessingManifest serializes to JSON: {len(manifest_json)} chars")

        # Test PipelineStepStatus
        print("  Testing PipelineStepStatus...")
        step_status = PipelineStepStatus(
            step_name="test_step",
            status="processing",
            segment_id="test-segment-123",
            start_time=datetime.now(),
            end_time=None,
            error=None,
            progress=50.0,
            dependencies=[]
        )

        step_status_json = step_status.json()
        step_status_dict = step_status.dict()
        print(f"    ✅ PipelineStepStatus serializes to JSON: {len(step_status_json)} chars")

        # Test EnhancedPipelineStatus
        print("  Testing EnhancedPipelineStatus...")
        enhanced_status = EnhancedPipelineStatus(
            content_id="test-content-123",
            overall_status="processing",
            current_step="test_step",
            step_statuses=[step_status],
            completed_steps=[],
            failed_steps=[],
            total_steps=1,
            progress_percentage=50.0,
            estimated_completion=None,
            last_updated=datetime.now(),
            processing_options={}
        )

        enhanced_status_json = enhanced_status.json()
        enhanced_status_dict = enhanced_status.dict()
        print(f"    ✅ EnhancedPipelineStatus serializes to JSON: {len(enhanced_status_json)} chars")

        return True

    except Exception as e:
        print(f"    ❌ Models serialization failed: {e}")
        traceback.print_exc()
        return False

def test_redis_repository_serialization():
    """Test Redis repository datetime handling"""
    print("\n2️⃣ Testing Redis Repository Serialization...")

    try:
        from hnfm.web.redis_repo import RedisRepository
        from hnfm.web.models import ProcessingManifest, VersionedSegment, PipelineStepStatus

        repo = RedisRepository()
        print("    ✅ RedisRepository created")

        # Test manifest creation and retrieval
        print("  Testing manifest creation...")
        manifest = repo.get_or_create_manifest("test-content-123", {"priority": "high"})
        print(f"    ✅ Manifest created: {manifest.content_id}")

        # Test manifest serialization
        manifest_json = manifest.json()
        manifest_dict = manifest.dict()
        print(f"    ✅ Manifest serializes to JSON: {len(manifest_json)} chars")

        # Test segment creation
        print("  Testing segment creation...")
        segment = repo.create_segment("test-content-123", "test_step")
        print(f"    ✅ Segment created: {segment.segment_id}")

        # Test segment serialization
        segment_json = segment.json()
        segment_dict = segment.dict()
        print(f"    ✅ Segment serializes to JSON: {len(segment_json)} chars")

        # Test enhanced pipeline status creation
        print("  Testing enhanced pipeline status...")
        status = repo.get_enhanced_pipeline_status("test-content-123")
        if status:
            status_json = status.json()
            status_dict = status.dict()
            print(f"    ✅ Enhanced status serializes to JSON: {len(status_json)} chars")
        else:
            print("    ⚠️ No enhanced status available (expected for new content)")

        return True

    except Exception as e:
        print(f"    ❌ Redis repository serialization failed: {e}")
        traceback.print_exc()
        return False

def test_enhanced_pipeline_manager_serialization():
    """Test enhanced pipeline manager datetime handling"""
    print("\n3️⃣ Testing Enhanced Pipeline Manager Serialization...")

    try:
        from hnfm.pipeline.enhanced_pipeline_manager import EnhancedPipelineManager

        # Test with Redis integration disabled first
        print("  Testing without Redis integration...")
        pipeline = EnhancedPipelineManager(redis_integration=False)
        print("    ✅ EnhancedPipelineManager created without Redis")

        # Test service lock status (should return error dict)
        lock_status = pipeline.get_service_lock_status()
        print(f"    ✅ Service lock status: {lock_status}")

        # Test JSON serialization of the result
        lock_status_json = json.dumps(lock_status)
        print(f"    ✅ Lock status serializes to JSON: {len(lock_status_json)} chars")

        # Test with Redis integration enabled
        print("  Testing with Redis integration...")
        pipeline_with_redis = EnhancedPipelineManager(redis_integration=True)
        print("    ✅ EnhancedPipelineManager created with Redis")

        # Test service lock status
        lock_status_with_redis = pipeline_with_redis.get_service_lock_status()
        print(f"    ✅ Service lock status with Redis: {lock_status_with_redis}")

        # Test JSON serialization
        try:
            lock_status_with_redis_json = json.dumps(lock_status_with_redis)
            print(f"    ✅ Lock status with Redis serializes to JSON: {len(lock_status_with_redis_json)} chars")
        except Exception as e:
            print(f"    ❌ Lock status with Redis JSON serialization failed: {e}")
            # Find the problematic object
            find_datetime_objects(lock_status_with_redis)
            return False

        return True

    except Exception as e:
        print(f"    ❌ Enhanced pipeline manager serialization failed: {e}")
        traceback.print_exc()
        return False

def test_api_endpoint_serialization():
    """Test API endpoint datetime serialization"""
    print("\n4️⃣ Testing API Endpoint Serialization...")

    try:
        import requests

        # Test basic content endpoint (should work)
        print("  Testing basic content endpoint...")
        response = requests.get("http://localhost:8000/api/content?per_page=1", timeout=5)
        if response.status_code == 200:
            print("    ✅ Basic content endpoint works")
            content_data = response.json()
            print(f"    ✅ Content data serializes: {len(str(content_data))} chars")
        else:
            print(f"    ❌ Basic content endpoint failed: {response.status_code}")
            return False

        # Test enhanced pipeline service locks endpoint
        print("  Testing enhanced pipeline service locks endpoint...")
        response = requests.get("http://localhost:8000/api/enhanced-pipeline/service-locks", timeout=5)
        if response.status_code == 200:
            print("    ✅ Service locks endpoint works")
            lock_data = response.json()
            print(f"    ✅ Lock data serializes: {len(str(lock_data))} chars")
        else:
            print(f"    ❌ Service locks endpoint failed: {response.status_code}")
            print(f"    Response: {response.text}")
            return False

        return True

    except Exception as e:
        print(f"    ❌ API endpoint serialization failed: {e}")
        traceback.print_exc()
        return False

def test_lock_manager_serialization():
    """Test lock manager datetime handling"""
    print("\n5️⃣ Testing Lock Manager Serialization...")

    try:
        from hnfm.web.locks import ServiceLockManager
        from hnfm.web.database import ContentDatabase

        # Create database connection
        db = ContentDatabase()
        lock_manager = ServiceLockManager(db.redis_client)
        print("    ✅ ServiceLockManager created")

        # Test lock info creation
        print("  Testing lock info creation...")
        lock_info = lock_manager.get_lock_info("test_service")
        print(f"    ✅ Lock info: {lock_info}")

        # Test JSON serialization of lock info
        if lock_info:
            try:
                lock_info_json = json.dumps(lock_info)
                print(f"    ✅ Lock info serializes to JSON: {len(lock_info_json)} chars")
            except Exception as e:
                print(f"    ❌ Lock info JSON serialization failed: {e}")
                find_datetime_objects(lock_info)
                return False
        else:
            print("    ⚠️ No lock info available (expected)")

        return True

    except Exception as e:
        print(f"    ❌ Lock manager serialization failed: {e}")
        traceback.print_exc()
        return False

def find_datetime_objects(obj: Any, path: str = "") -> None:
    """Recursively find datetime objects in a data structure"""
    if isinstance(obj, dict):
        for key, value in obj.items():
            find_datetime_objects(value, f"{path}.{key}")
    elif isinstance(obj, list):
        for i, value in enumerate(obj):
            find_datetime_objects(value, f"{path}[{i}]")
    elif hasattr(obj, '__class__') and 'datetime' in str(obj.__class__):
        print(f"    🔍 Found datetime object at {path}: {obj} (type: {type(obj)})")
    elif hasattr(obj, '__class__') and 'datetime' in str(type(obj)):
        print(f"    🔍 Found datetime object at {path}: {obj} (type: {type(obj)})")

def main():
    """Run all datetime serialization tests"""
    print("🧪 DateTime Serialization Test Suite")
    print("=" * 60)

    success = test_datetime_serialization()

    if success:
        print("\n🎉 All datetime serialization tests passed!")
        print("The pipeline should now handle datetime objects correctly.")
    else:
        print("\n❌ Some datetime serialization tests failed.")
        print("Check the output above for specific issues.")

    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())
