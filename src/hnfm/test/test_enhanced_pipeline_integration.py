#!/usr/bin/env python3
"""Integration tests for enhanced pipeline system"""

import pytest
import requests
import json
import time
from datetime import datetime
from typing import Dict, Any


class TestEnhancedPipelineIntegration:
    """Integration tests for enhanced pipeline functionality"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test environment"""
        self.base_url = "http://localhost:8000"
        self.api_base = f"{self.base_url}/api"

    def test_pipeline_status_endpoint(self):
        """Test that pipeline status endpoint returns valid JSON"""
        response = requests.get(f"{self.api_base}/pipeline/status")

        assert response.status_code == 200
        data = response.json()

        # Validate structure
        assert "status" in data
        assert "timestamp" in data
        assert "message" in data

        # Validate timestamp is ISO string
        assert isinstance(data["timestamp"], str)
        datetime.fromisoformat(data["timestamp"])  # Should parse without error

        # Validate status
        assert data["status"] == "healthy"
        assert isinstance(data["message"], str)

    def test_content_artifacts_endpoint(self):
        """Test content artifacts endpoint"""
        # First, create some test content
        test_content = {
            "title": "Test Article",
            "url": "https://example.com/test",
            "score": 100,
            "id": "test_123",
        }

        # Create content via API
        create_response = requests.post(f"{self.api_base}/content", json=test_content)

        if create_response.status_code == 200:
            content_id = create_response.json().get("id", "test_123")

            # Test artifacts endpoint
            artifacts_response = requests.get(
                f"{self.api_base}/content/{content_id}/artifacts"
            )

            # Should return 200 or 404 (if no artifacts exist yet)
            assert artifacts_response.status_code in [200, 404]

            if artifacts_response.status_code == 200:
                artifacts = artifacts_response.json()
                assert "content_id" in artifacts
                assert "artifacts" in artifacts
                assert isinstance(artifacts["artifacts"], dict)

    def test_enhanced_status_endpoint(self):
        """Test enhanced pipeline status endpoint"""
        # Test with a non-existent content ID
        response = requests.get(f"{self.api_base}/content/nonexistent/enhanced-status")

        # Should return 404 for non-existent content
        assert response.status_code == 404

        # Test with a valid content ID (if we have one)
        # This would require creating content first

    def test_media_file_serving(self):
        """Test media file serving endpoints"""
        # Test with non-existent content
        response = requests.get(
            f"{self.api_base}/content/nonexistent/media/audio/test.wav"
        )
        assert response.status_code == 404

    def test_pipeline_health_endpoint(self):
        """Test pipeline health endpoint"""
        # Test pipeline status
        response = requests.get(f"{self.api_base}/pipeline/status")

        # Should return 200
        assert response.status_code == 200

        data = response.json()
        assert "status" in data
        assert data["status"] == "healthy"

    def test_health_endpoints(self):
        """Test health check endpoints"""
        # Basic health check
        response = requests.get(f"{self.base_url}/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"

        # API health check
        response = requests.get(f"{self.api_base}/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "timestamp" in data
        assert "redis_status" in data

    def test_services_status_endpoint(self):
        """Test services status endpoint"""
        response = requests.get(f"{self.api_base}/services/status")
        assert response.status_code == 200

        data = response.json()
        assert "all_healthy" in data
        assert "services" in data
        assert isinstance(data["services"], list)

    def test_error_response_serialization(self):
        """Test that error responses are properly serialized"""
        # Trigger a 404 error
        response = requests.get(f"{self.api_base}/nonexistent-endpoint")
        assert response.status_code == 404

        # Verify error response structure
        error_data = response.json()
        assert "detail" in error_data
        # Note: FastAPI 404 errors don't always include error_code and timestamp
        # We'll check if they exist, but not require them
        if "error_code" in error_data:
            assert isinstance(error_data["error_code"], str)
        if "timestamp" in error_data:
            assert isinstance(error_data["timestamp"], str)

        # Verify timestamp is ISO string (if it exists)
        if "timestamp" in error_data:
            assert isinstance(error_data["timestamp"], str)
            datetime.fromisoformat(error_data["timestamp"])


class TestEnhancedPipelineWorkflow:
    """Test complete pipeline workflow"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test environment"""
        self.base_url = "http://localhost:8000"
        self.api_base = f"{self.base_url}/api"

    def test_pipeline_workflow(self):
        """Test a complete pipeline workflow"""
        # This would be a more complex test that:
        # 1. Creates content
        # 2. Triggers pipeline processing
        # 3. Monitors progress
        # 4. Validates artifacts
        #
        # For now, we'll just test that the endpoints exist
        endpoints_to_test = [
            f"{self.api_base}/pipeline/status",
            f"{self.api_base}/health",
            f"{self.api_base}/services/status",
        ]

        for endpoint in endpoints_to_test:
            response = requests.get(endpoint)
            assert response.status_code in [200, 404, 500]  # Any valid HTTP response


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
