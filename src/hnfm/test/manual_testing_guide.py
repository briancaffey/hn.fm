#!/usr/bin/env python3
"""Manual testing guide for enhanced pipeline system"""

import requests
import json
import time
from pathlib import Path
from typing import Dict, Any


class ManualTestingGuide:
    """Manual testing guide with step-by-step instructions"""

    def __init__(self):
        self.base_url = "http://localhost:8000"
        self.api_base = f"{self.base_url}/api"
        self.frontend_url = "http://localhost:3000"

    def run_backend_tests(self):
        """Run backend API tests manually"""
        print("🔧 Backend API Testing")
        print("=" * 50)

        # Test 1: Health check
        print("\n1️⃣ Testing Health Check...")
        response = requests.get(f"{self.api_base}/health")
        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"   Redis Status: {data.get('redis_status')}")
            print(f"   Timestamp: {data.get('timestamp')}")
        else:
            print("   ❌ Health check failed")

        # Test 2: Pipeline status
        print("\n2️⃣ Testing Pipeline Status...")
        response = requests.get(f"{self.api_base}/pipeline/status")
        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"   Status: {data.get('status')}")
            print(f"   Timestamp: {data.get('timestamp')}")
            print(f"   Message: {data.get('message')}")
        else:
            print("   ❌ Pipeline status failed")

        # Test 3: Services status
        print("\n3️⃣ Testing Services Status...")
        response = requests.get(f"{self.api_base}/services/status")
        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"   All Healthy: {data.get('all_healthy')}")
            services = data.get("services", [])
            print(f"   Service Count: {len(services)}")
        else:
            print("   ❌ Services status failed")

    def run_frontend_tests(self):
        """Run frontend tests manually"""
        print("\n🎨 Frontend Testing")
        print("=" * 50)

        # Test 1: Frontend server
        print("\n1️⃣ Testing Frontend Server...")
        try:
            response = requests.get(self.frontend_url, timeout=5)
            print(f"   Status: {response.status_code}")
            if response.status_code == 200:
                print("   ✅ Frontend server is running")
            else:
                print("   ❌ Frontend server returned error")
        except requests.exceptions.RequestException:
            print("   ❌ Frontend server not accessible")

        # Test 2: Content list page
        print("\n2️⃣ Testing Content List Page...")
        try:
            response = requests.get(f"{self.frontend_url}/items", timeout=5)
            print(f"   Status: {response.status_code}")
            if response.status_code == 200:
                print("   ✅ Content list page accessible")
            else:
                print("   ❌ Content list page error")
        except requests.exceptions.RequestException:
            print("   ❌ Content list page not accessible")

        # Test 3: Enhanced view page
        print("\n3️⃣ Testing Enhanced View Page...")
        try:
            response = requests.get(
                f"{self.frontend_url}/items/test/enhanced", timeout=5
            )
            print(f"   Status: {response.status_code}")
            if response.status_code == 200:
                print("   ✅ Enhanced view page accessible")
            else:
                print("   ❌ Enhanced view page error")
        except requests.exceptions.RequestException:
            print("   ❌ Enhanced view page not accessible")

    def run_integration_tests(self):
        """Run integration tests manually"""
        print("\n🔗 Integration Testing")
        print("=" * 50)

        # Test 1: Error response serialization
        print("\n1️⃣ Testing Error Response Serialization...")
        response = requests.get(f"{self.api_base}/nonexistent-endpoint")
        print(f"   Status: {response.status_code}")
        if response.status_code == 404:
            try:
                error_data = response.json()
                print(f"   Error Detail: {error_data.get('detail')}")
                print(f"   Error Code: {error_data.get('error_code')}")
                print(f"   Timestamp: {error_data.get('timestamp')}")

                # Verify timestamp is ISO string
                if isinstance(error_data.get("timestamp"), str):
                    print("   ✅ Timestamp is properly serialized")
                else:
                    print("   ❌ Timestamp serialization failed")
            except json.JSONDecodeError:
                print("   ❌ Error response is not valid JSON")

        # Test 2: Content artifacts endpoint
        print("\n2️⃣ Testing Content Artifacts Endpoint...")
        response = requests.get(f"{self.api_base}/content/nonexistent/artifacts")
        print(f"   Status: {response.status_code}")
        if response.status_code == 404:
            print("   ✅ Properly handles non-existent content")

        # Test 3: Enhanced status endpoint
        print("\n3️⃣ Testing Enhanced Status Endpoint...")
        response = requests.get(f"{self.api_base}/content/nonexistent/enhanced-status")
        print(f"   Status: {response.status_code}")
        if response.status_code == 404:
            print("   ✅ Properly handles non-existent content")

    def run_workflow_tests(self):
        """Run workflow tests manually"""
        print("\n🔄 Workflow Testing")
        print("=" * 50)

        # Test 1: Pipeline status workflow
        print("\n1️⃣ Testing Pipeline Status Workflow...")

        # Get pipeline status
        response = requests.get(f"{self.api_base}/pipeline/status")
        if response.status_code == 200:
            data = response.json()
            print("   ✅ Pipeline status retrieved")
            print(f"   Status: {data.get('status')}")
            print(f"   Message: {data.get('message')}")

        # Test 2: Media file serving
        print("\n2️⃣ Testing Media File Serving...")
        media_types = ["audio", "images", "video", "content"]

        for media_type in media_types:
            response = requests.get(
                f"{self.api_base}/content/nonexistent/media/{media_type}/test.file"
            )
            print(f"   {media_type.capitalize()}: {response.status_code}")
            if response.status_code == 404:
                print(f"     ✅ Properly handles non-existent {media_type}")

    def check_file_structure(self):
        """Check that all required files exist"""
        print("\n📁 File Structure Check")
        print("=" * 50)

        required_files = [
            "frontend/app/pages/items/[id]/enhanced.vue",
            "frontend/app/components/PipelineDashboard.vue",
            "frontend/app/components/ui/progress.vue",
            "frontend/app/components/ui/tabs.vue",
            "frontend/app/components/ui/tabs-list.vue",
            "frontend/app/components/ui/tabs-trigger.vue",
            "frontend/app/components/ui/tabs-content.vue",
            "src/hnfm/pipeline/enhanced_pipeline_manager.py",
            "src/hnfm/pipeline/enhanced_pipeline_manager.py",
            "src/hnfm/web/redis_repo.py",
            "src/hnfm/web/custom_types.py",
        ]

        for file_path in required_files:
            path = Path(file_path)
            if path.exists():
                print(f"   ✅ {file_path}")
            else:
                print(f"   ❌ {file_path} (missing)")

    def run_all_tests(self):
        """Run all manual tests"""
        print("🧪 Manual Testing Guide for Enhanced Pipeline System")
        print("=" * 60)

        self.check_file_structure()
        self.run_backend_tests()
        self.run_frontend_tests()
        self.run_integration_tests()
        self.run_workflow_tests()

        print("\n🎉 Manual testing completed!")
        print("\n📋 Next Steps:")
        print("   1. Start the frontend: cd frontend && yarn dev")
        print("   2. Open http://localhost:3000 in your browser")
        print("   3. Navigate to /items to see the content list")
        print("   4. Click the enhanced view button on any item")
        print("   5. Check the pipeline dashboard on the main page")


def main():
    """Main function to run manual tests"""
    guide = ManualTestingGuide()
    guide.run_all_tests()


if __name__ == "__main__":
    main()
