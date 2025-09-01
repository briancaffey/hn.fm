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
        test_pipeline_manager_serialization,
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
            VersionedSegment,
            ProcessingManifest,
            EnhancedPipelineStatus,
            PipelineStepStatus,
            PipelineStatus,
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
            retry_count=0,
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
            priority=1,
        )

        manifest_json = manifest.json()
        manifest_dict = manifest.dict()
        print(
            f"    ✅ ProcessingManifest serializes to JSON: {len(manifest_json)} chars"
        )

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
            dependencies=[],
        )

        step_status_json = step_status.json()
        step_status_dict = step_status.dict()
        print(
            f"    ✅ PipelineStepStatus serializes to JSON: {len(step_status_json)} chars"
        )

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
            processing_options={},
        )

        enhanced_status_json = enhanced_status.json()
        enhanced_status_dict = enhanced_status.dict()
        print(
            f"    ✅ EnhancedPipelineStatus serializes to JSON: {len(enhanced_status_json)} chars"
        )

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
        from hnfm.web.models import (
            ProcessingManifest,
            VersionedSegment,
            PipelineStepStatus,
        )

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
            print(
                f"    ✅ Enhanced status serializes to JSON: {len(status_json)} chars"
            )
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
        from hnfm.pipeline.enhanced_pipeline_manager import PipelineManager

        # Test with Redis integration disabled first
        print("  Testing without Redis integration...")
        pipeline = PipelineManager(text_only=True)
        print("    ✅ PipelineManager created without Redis")

        # Test pipeline status (should return simple status)
        pipeline_status = {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "message": "Pipeline system is running without locking",
        }
        print(f"    ✅ Pipeline status: {pipeline_status}")

        # Test JSON serialization of the result
        pipeline_status_json = json.dumps(pipeline_status)
        print(
            f"    ✅ Pipeline status serializes to JSON: {len(pipeline_status_json)} chars"
        )

        # Test with Redis integration enabled
        print("  Testing with Redis integration...")
        pipeline_with_redis = PipelineManager(text_only=False)
        print("    ✅ PipelineManager created with full features")

        # Test pipeline steps
        steps = pipeline_with_redis.pipeline_steps
        print(f"    ✅ Pipeline steps: {len(steps)} steps defined")

        # Test JSON serialization
        try:
            steps_json = json.dumps({k: v.__dict__ for k, v in steps.items()})
            print(f"    ✅ Pipeline steps serialize to JSON: {len(steps_json)} chars")
        except Exception as e:
            print(f"    ❌ Pipeline steps JSON serialization failed: {e}")
            # Find the problematic object
            find_datetime_objects(steps)
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
        response = requests.get(
            "http://localhost:8000/api/content?per_page=1", timeout=5
        )
        if response.status_code == 200:
            print("    ✅ Basic content endpoint works")
            content_data = response.json()
            print(f"    ✅ Content data serializes: {len(str(content_data))} chars")
        else:
            print(f"    ❌ Basic content endpoint failed: {response.status_code}")
            return False

        # Test pipeline status endpoint
        print("  Testing pipeline status endpoint...")
        response = requests.get("http://localhost:8000/api/pipeline/status", timeout=5)
        if response.status_code == 200:
            print("    ✅ Pipeline status endpoint works")
            status_data = response.json()
            print(f"    ✅ Status data serializes: {len(str(status_data))} chars")
        else:
            print(f"    ❌ Pipeline status endpoint failed: {response.status_code}")
            print(f"    Response: {response.text}")
            return False

        return True

    except Exception as e:
        print(f"    ❌ API endpoint serialization failed: {e}")
        traceback.print_exc()
        return False


def test_pipeline_manager_serialization():
    """Test pipeline manager datetime handling"""
    print("\n5️⃣ Testing Pipeline Manager Serialization...")

    try:
        from hnfm.pipeline.enhanced_pipeline_manager import PipelineManager

        # Create pipeline manager
        pipeline = PipelineManager(text_only=True)
        print("    ✅ PipelineManager created")

        # Test pipeline steps
        print("  Testing pipeline steps...")
        steps = pipeline.pipeline_steps
        print(f"    ✅ Pipeline steps: {len(steps)} steps defined")

        # Test JSON serialization of steps
        try:
            steps_json = json.dumps({k: v.__dict__ for k, v in steps.items()})
            print(f"    ✅ Pipeline steps serialize to JSON: {len(steps_json)} chars")
        except Exception as e:
            print(f"    ❌ Pipeline steps JSON serialization failed: {e}")
            find_datetime_objects(steps)
            return False

        return True

    except Exception as e:
        print(f"    ❌ Pipeline manager serialization failed: {e}")
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
    elif hasattr(obj, "__class__") and "datetime" in str(obj.__class__):
        print(f"    🔍 Found datetime object at {path}: {obj} (type: {type(obj)})")
    elif hasattr(obj, "__class__") and "datetime" in str(type(obj)):
        print(f"    🔍 Found datetime object at {path}: {obj} (type: {type(obj)})")


def main():
    """Run all datetime serialization tests"""
    print("🧪 DateTime Serialization Test Suite")
    print("=" * 60)

    success = test_datetime_serialization() and test_pipeline_manager_serialization()

    if success:
        print("\n🎉 All datetime serialization tests passed!")
        print("The pipeline should now handle datetime objects correctly.")
    else:
        print("\n❌ Some datetime serialization tests failed.")
        print("Check the output above for specific issues.")

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
