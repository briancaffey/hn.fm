#!/usr/bin/env python3
"""Debug script for service locks endpoint"""

import sys
from pathlib import Path

# Add the src directory to the Python path
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

def test_service_locks():
    """Test the service locks functionality directly"""
    print("Testing service locks functionality...")

    try:
        from hnfm.pipeline.enhanced_pipeline_manager import EnhancedPipelineManager

        # Create enhanced pipeline manager
        print("Creating EnhancedPipelineManager...")
        pipeline = EnhancedPipelineManager(redis_integration=True)
        print("✓ EnhancedPipelineManager created")

        # Test service lock status
        print("Getting service lock status...")
        lock_status = pipeline.get_service_lock_status()
        print(f"✓ Service lock status: {lock_status}")

        # Check if there are any datetime objects
        import json
        try:
            json.dumps(lock_status)
            print("✓ JSON serialization successful")
        except Exception as e:
            print(f"✗ JSON serialization failed: {e}")

            # Find the problematic object
            def find_datetime_objects(obj, path=""):
                if isinstance(obj, dict):
                    for key, value in obj.items():
                        find_datetime_objects(value, f"{path}.{key}")
                elif isinstance(obj, list):
                    for i, value in enumerate(obj):
                        find_datetime_objects(value, f"{path}[{i}]")
                elif hasattr(obj, '__class__') and 'datetime' in str(obj.__class__):
                    print(f"Found datetime object at {path}: {obj} (type: {type(obj)})")

            find_datetime_objects(lock_status)

        return True

    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    test_service_locks()
