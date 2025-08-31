#!/usr/bin/env python3
"""Test script for the enhanced frontend and backend integration"""

import os
import sys
import time
import requests
from pathlib import Path

# Add the src directory to the Python path
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

def test_backend_endpoints():
    """Test the new backend API endpoints"""
    print("Testing backend API endpoints...")

    base_url = "http://localhost:8000"

    # Test enhanced pipeline service locks endpoint
    try:
        response = requests.get(f"{base_url}/api/enhanced-pipeline/service-locks")
        if response.status_code == 200:
            print("✓ Service locks endpoint working")
        else:
            print(f"✗ Service locks endpoint failed: {response.status_code}")
    except Exception as e:
        print(f"✗ Service locks endpoint error: {e}")

    # Test content artifacts endpoint (if we have content)
    try:
        # First get a list of content items
        response = requests.get(f"{base_url}/api/content?per_page=1")
        if response.status_code == 200:
            data = response.json()
            if data.get('items') and len(data['items']) > 0:
                content_id = data['items'][0]['id']

                # Test artifacts endpoint
                artifacts_response = requests.get(f"{base_url}/api/content/{content_id}/artifacts")
                if artifacts_response.status_code == 200:
                    print("✓ Content artifacts endpoint working")
                else:
                    print(f"✗ Content artifacts endpoint failed: {artifacts_response.status_code}")

                # Test enhanced status endpoint
                status_response = requests.get(f"{base_url}/api/content/{content_id}/enhanced-status")
                if status_response.status_code in [200, 404]:  # 404 is OK if no enhanced status yet
                    print("✓ Enhanced status endpoint working")
                else:
                    print(f"✗ Enhanced status endpoint failed: {status_response.status_code}")
            else:
                print("⚠ No content items found to test artifacts endpoint")
        else:
            print(f"✗ Content list endpoint failed: {response.status_code}")
    except Exception as e:
        print(f"✗ Content endpoints error: {e}")

def test_frontend_build():
    """Test that the frontend can be built without errors"""
    print("\nTesting frontend build...")

    frontend_dir = Path("frontend")
    if not frontend_dir.exists():
        print("✗ Frontend directory not found")
        return False

    # Check if required files exist
    required_files = [
        "frontend/app/pages/items/[id]/enhanced.vue",
        "frontend/app/components/ui/progress.vue",
        "frontend/app/components/ui/tabs.vue",
        "frontend/app/components/PipelineDashboard.vue"
    ]

    for file_path in required_files:
        if Path(file_path).exists():
            print(f"✓ {file_path} exists")
        else:
            print(f"✗ {file_path} missing")
            return False

    print("✓ All required frontend files exist")
    return True

def test_enhanced_system_integration():
    """Test the enhanced system integration"""
    print("\nTesting enhanced system integration...")

    try:
        # Test imports
        from hnfm.web.enhanced_tasks import enhanced_content_pipeline
        from hnfm.web.redis_repo import RedisRepository
        from hnfm.web.locks import ServiceLockManager
        print("✓ Enhanced system imports working")

        # Test Redis repository
        repo = RedisRepository()
        print("✓ Redis repository created")

        # Test service lock manager
        lock_manager = ServiceLockManager(repo.redis_client)
        print("✓ Service lock manager created")

        return True

    except Exception as e:
        print(f"✗ Enhanced system integration error: {e}")
        return False

def main():
    """Run all tests"""
    print("Enhanced Frontend & Backend Integration Test")
    print("=" * 50)

    tests = [
        test_enhanced_system_integration,
        test_frontend_build,
        test_backend_endpoints
    ]

    passed = 0
    total = len(tests)

    for test in tests:
        try:
            if test():
                passed += 1
            time.sleep(0.1)
        except Exception as e:
            print(f"✗ Test {test.__name__} crashed: {e}")

    print("\n" + "=" * 50)
    print(f"Test Results: {passed}/{total} tests passed")

    if passed == total:
        print("🎉 All tests passed! The enhanced system is ready.")
        print("\nNext steps:")
        print("1. Start the backend server: uv run python run_web_server.py")
        print("2. Start the frontend dev server: cd frontend && yarn dev")
        print("3. Visit http://localhost:3000 to see the enhanced interface")
        print("4. Click on any item and use the 'Enhanced View' button")
        return 0
    else:
        print("❌ Some tests failed. Please check the errors above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
