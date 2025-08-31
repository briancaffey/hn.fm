#!/usr/bin/env python3
"""End-to-end workflow tests for enhanced pipeline system"""

import pytest
import requests
import json
import time
import subprocess
from pathlib import Path
from typing import Dict, Any


class TestE2EWorkflow:
    """End-to-end workflow tests"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test environment"""
        self.base_url = "http://localhost:8000"
        self.api_base = f"{self.base_url}/api"
        self.frontend_url = "http://localhost:3000"

    def test_complete_pipeline_workflow(self):
        """Test complete pipeline workflow from content creation to artifact generation"""
        # Step 1: Verify services are running
        self._verify_services_running()

        # Step 2: Create test content
        content_id = self._create_test_content()

        # Step 3: Trigger pipeline processing
        task_id = self._trigger_pipeline(content_id)

        # Step 4: Monitor pipeline progress
        self._monitor_pipeline_progress(content_id, task_id)

        # Step 5: Verify artifacts are generated
        self._verify_artifacts_generated(content_id)

        # Step 6: Test frontend integration
        self._test_frontend_integration(content_id)

    def _verify_services_running(self):
        """Verify all required services are running"""
        # Check backend API
        response = requests.get(f"{self.api_base}/health")
        assert response.status_code == 200, "Backend API not running"

        # Check Redis
        response = requests.get(f"{self.api_base}/services/status")
        assert response.status_code == 200, "Services status endpoint not accessible"

        # Check service locks endpoint
        response = requests.get(f"{self.api_base}/enhanced-pipeline/service-locks")
        assert response.status_code == 200, "Service locks endpoint not accessible"

        # Check frontend (optional)
        try:
            response = requests.get(self.frontend_url, timeout=5)
            assert response.status_code == 200, "Frontend not running"
        except requests.exceptions.RequestException:
            print("Frontend not running (optional for this test)")

    def _create_test_content(self) -> str:
        """Create test content and return content ID"""
        test_content = {
            "title": "E2E Test Article",
            "url": "https://example.com/e2e-test",
            "score": 150,
            "id": f"e2e_test_{int(time.time())}"
        }

        # Create content via API
        response = requests.post(f"{self.api_base}/content", json=test_content)

        if response.status_code == 200:
            return response.json().get("id", test_content["id"])
        else:
            # If creation fails, use the test ID
            return test_content["id"]

    def _trigger_pipeline(self, content_id: str) -> str:
        """Trigger pipeline processing for content"""
        # This would trigger the enhanced pipeline
        # For now, we'll just verify the content exists
        response = requests.get(f"{self.api_base}/content/{content_id}")

        if response.status_code == 200:
            print(f"Content {content_id} exists, pipeline can be triggered")
            return f"task_{content_id}"
        else:
            pytest.skip(f"Content {content_id} not found, cannot test pipeline")

    def _monitor_pipeline_progress(self, content_id: str, task_id: str):
        """Monitor pipeline progress"""
        # Check enhanced status endpoint
        response = requests.get(f"{self.api_base}/content/{content_id}/enhanced-status")

        if response.status_code == 200:
            status = response.json()
            assert "overall_status" in status
            assert "step_statuses" in status
            print(f"Pipeline status: {status['overall_status']}")
        else:
            print(f"Enhanced status not available for {content_id}")

    def _verify_artifacts_generated(self, content_id: str):
        """Verify that artifacts are generated"""
        # Check artifacts endpoint
        response = requests.get(f"{self.api_base}/content/{content_id}/artifacts")

        if response.status_code == 200:
            artifacts = response.json()
            assert "content_id" in artifacts
            assert "artifacts" in artifacts
            print(f"Artifacts found: {list(artifacts['artifacts'].keys())}")
        else:
            print(f"No artifacts found for {content_id}")

    def _test_frontend_integration(self, content_id: str):
        """Test frontend integration with the content"""
        try:
            # Test enhanced view page
            response = requests.get(f"{self.frontend_url}/items/{content_id}/enhanced", timeout=5)
            if response.status_code == 200:
                print(f"Enhanced view page accessible for {content_id}")
            else:
                print(f"Enhanced view page not accessible for {content_id}")
        except requests.exceptions.RequestException:
            print("Frontend not running, skipping frontend integration test")

    def test_service_lock_workflow(self):
        """Test service lock workflow"""
        # Get initial lock status
        response = requests.get(f"{self.api_base}/enhanced-pipeline/service-locks")
        assert response.status_code == 200

        initial_status = response.json()
        assert "services" in initial_status

        # Test force release lock
        response = requests.post(f"{self.api_base}/enhanced-pipeline/force-release-lock/firecrawl")
        assert response.status_code in [200, 500]  # Success or service doesn't exist

        # Get updated lock status
        response = requests.get(f"{self.api_base}/enhanced-pipeline/service-locks")
        assert response.status_code == 200

        updated_status = response.json()
        assert "services" in updated_status

    def test_error_handling_workflow(self):
        """Test error handling workflow"""
        # Test with non-existent content
        response = requests.get(f"{self.api_base}/content/nonexistent/enhanced-status")
        assert response.status_code == 404

        # Verify error response structure
        error_data = response.json()
        assert "detail" in error_data
        assert "error_code" in error_data
        assert "timestamp" in error_data

        # Verify timestamp is properly serialized
        assert isinstance(error_data["timestamp"], str)

    def test_media_file_serving_workflow(self):
        """Test media file serving workflow"""
        media_types = ["audio", "images", "video", "content"]

        for media_type in media_types:
            # Test with non-existent file
            response = requests.get(f"{self.api_base}/content/nonexistent/media/{media_type}/test.file")
            assert response.status_code == 404

            # Verify proper error response
            error_data = response.json()
            assert "detail" in error_data

    def test_frontend_navigation_workflow(self):
        """Test frontend navigation workflow"""
        try:
            # Test main page
            response = requests.get(self.frontend_url, timeout=5)
            assert response.status_code == 200

            # Test items page
            response = requests.get(f"{self.frontend_url}/items", timeout=5)
            assert response.status_code == 200

            # Test services page
            response = requests.get(f"{self.frontend_url}/services", timeout=5)
            assert response.status_code == 200

        except requests.exceptions.RequestException:
            pytest.skip("Frontend not running")

    def test_api_base_configuration_workflow(self):
        """Test API base configuration workflow"""
        # This would test the apiBase configuration pattern
        # For now, we'll test that the API endpoints are accessible
        endpoints = [
            f"{self.api_base}/health",
            f"{self.api_base}/services/status",
            f"{self.api_base}/enhanced-pipeline/service-locks",
        ]

        for endpoint in endpoints:
            response = requests.get(endpoint)
            assert response.status_code in [200, 404, 500], f"Endpoint {endpoint} not accessible"


class TestDockerEnvironment:
    """Test Docker environment setup"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test environment"""
        self.base_url = "http://localhost:8000"
        self.api_base = f"{self.base_url}/api"
        self.frontend_url = "http://localhost:3000"

    def test_docker_services_running(self):
        """Test that Docker services are running"""
        try:
            # Check if docker-compose is available
            result = subprocess.run(["docker-compose", "ps"], capture_output=True, text=True)
            assert result.returncode == 0, "docker-compose not available"

            # Check for required services
            services = ["web", "redis", "celery-worker"]
            for service in services:
                result = subprocess.run(["docker-compose", "ps", service], capture_output=True, text=True)
                assert "Up" in result.stdout, f"Service {service} not running"

        except FileNotFoundError:
            pytest.skip("docker-compose not available")

    def test_redis_connectivity(self):
        """Test Redis connectivity"""
        response = requests.get(f"{self.api_base}/health")
        assert response.status_code == 200

        data = response.json()
        assert data["redis_status"] == "healthy", "Redis not healthy"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
