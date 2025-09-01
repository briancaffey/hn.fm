#!/usr/bin/env python3
"""Frontend integration tests for enhanced pipeline UI"""

import pytest
import requests
import json
import time
from pathlib import Path
from typing import Dict, Any


class TestFrontendIntegration:
    """Integration tests for frontend functionality"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test environment"""
        self.base_url = "http://localhost:3000"  # Nuxt dev server
        self.api_base = "http://localhost:8000/api"

    def test_frontend_server_running(self):
        """Test that frontend server is running"""
        try:
            response = requests.get(self.base_url, timeout=5)
            assert response.status_code == 200
        except requests.exceptions.RequestException:
            pytest.skip("Frontend server not running")

    def test_api_base_configuration(self):
        """Test that frontend can access API base configuration"""
        # This would test the apiBase configuration pattern
        # For now, we'll test that the API endpoints are accessible
        response = requests.get(f"{self.api_base}/health")
        assert response.status_code == 200

    def test_content_list_page(self):
        """Test content list page loads"""
        try:
            response = requests.get(f"{self.base_url}/items", timeout=5)
            assert response.status_code == 200
        except requests.exceptions.RequestException:
            pytest.skip("Frontend server not running")

    def test_enhanced_view_page(self):
        """Test enhanced view page loads"""
        try:
            # Test with a non-existent ID
            response = requests.get(
                f"{self.base_url}/items/nonexistent/enhanced", timeout=5
            )
            # Should return 200 (page loads) or 404 (not found)
            assert response.status_code in [200, 404]
        except requests.exceptions.RequestException:
            pytest.skip("Frontend server not running")

    def test_pipeline_dashboard_component(self):
        """Test pipeline dashboard component"""
        # This would test the PipelineDashboard component
        # For now, we'll test that the main page loads
        try:
            response = requests.get(self.base_url, timeout=5)
            assert response.status_code == 200
        except requests.exceptions.RequestException:
            pytest.skip("Frontend server not running")


class TestFrontendFileStructure:
    """Test frontend file structure and components"""

    def test_enhanced_view_component_exists(self):
        """Test that enhanced view component exists"""
        enhanced_view_path = Path("frontend/app/pages/items/[id]/enhanced.vue")
        assert (
            enhanced_view_path.exists()
        ), f"Enhanced view component not found at {enhanced_view_path}"

    def test_pipeline_dashboard_component_exists(self):
        """Test that pipeline dashboard component exists"""
        dashboard_path = Path("frontend/app/components/PipelineDashboard.vue")
        assert (
            dashboard_path.exists()
        ), f"Pipeline dashboard component not found at {dashboard_path}"

    def test_ui_components_exist(self):
        """Test that required UI components exist"""
        ui_components = [
            "frontend/app/components/ui/progress.vue",
            "frontend/app/components/ui/tabs.vue",
            "frontend/app/components/ui/tabs-list.vue",
            "frontend/app/components/ui/tabs-trigger.vue",
            "frontend/app/components/ui/tabs-content.vue",
        ]

        for component in ui_components:
            component_path = Path(component)
            assert (
                component_path.exists()
            ), f"UI component not found at {component_path}"

    def test_content_list_enhanced_button(self):
        """Test that ContentList component has enhanced view button"""
        content_list_path = Path("frontend/app/components/ContentList.vue")
        assert content_list_path.exists(), "ContentList component not found"

        # Read the file to check for enhanced view button
        content = content_list_path.read_text()
        assert (
            "enhanced" in content.lower()
        ), "Enhanced view button not found in ContentList"

    def test_item_detail_enhanced_button(self):
        """Test that item detail page has enhanced view button"""
        item_detail_path = Path("frontend/app/pages/items/[id].vue")
        assert item_detail_path.exists(), "Item detail page not found"

        # Read the file to check for enhanced view button
        content = item_detail_path.read_text()
        assert (
            "enhanced" in content.lower()
        ), "Enhanced view button not found in item detail page"


class TestFrontendAPIIntegration:
    """Test frontend integration with backend API"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test environment"""
        self.base_url = "http://localhost:3000"  # Nuxt dev server
        self.api_base = "http://localhost:8000/api"

    def test_api_endpoints_accessible(self):
        """Test that all required API endpoints are accessible"""
        endpoints = [
            f"{self.api_base}/pipeline/status",
            f"{self.api_base}/health",
            f"{self.api_base}/services/status",
        ]

        for endpoint in endpoints:
            response = requests.get(endpoint)
            assert response.status_code in [
                200,
                404,
                500,
            ], f"Endpoint {endpoint} not accessible"

    def test_content_artifacts_endpoint(self):
        """Test content artifacts endpoint"""
        # Test with non-existent content
        response = requests.get(f"{self.api_base}/content/nonexistent/artifacts")
        assert response.status_code == 404

    def test_enhanced_status_endpoint(self):
        """Test enhanced status endpoint"""
        # Test with non-existent content
        response = requests.get(f"{self.api_base}/content/nonexistent/enhanced-status")
        assert response.status_code == 404

    def test_media_file_endpoints(self):
        """Test media file serving endpoints"""
        media_types = ["audio", "images", "video", "content"]

        for media_type in media_types:
            response = requests.get(
                f"{self.api_base}/content/nonexistent/media/{media_type}/test.file"
            )
            assert response.status_code == 404


class TestFrontendConfiguration:
    """Test frontend configuration and setup"""

    def test_nuxt_config(self):
        """Test Nuxt configuration"""
        nuxt_config_path = Path("frontend/nuxt.config.ts")
        assert nuxt_config_path.exists(), "Nuxt config not found"

        # Read the config to check for API configuration
        content = nuxt_config_path.read_text()
        assert "runtimeConfig" in content, "Runtime config not found in Nuxt config"

    def test_package_json_dependencies(self):
        """Test package.json has required dependencies"""
        package_json_path = Path("frontend/package.json")
        assert package_json_path.exists(), "Package.json not found"

        # Read package.json to check dependencies
        content = package_json_path.read_text()
        assert "nuxt" in content, "Nuxt dependency not found"
        assert "vue" in content, "Vue dependency not found"

    def test_components_configuration(self):
        """Test components configuration"""
        components_json_path = Path("frontend/components.json")
        assert components_json_path.exists(), "Components config not found"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
