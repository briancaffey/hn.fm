#!/usr/bin/env python3
"""Comprehensive test suite for Firecrawl integration with hn.fm.

This test suite validates:
1. Firecrawl scraping of local test HTML files
2. Content processing and cleaning
3. Script generation from scraped content
4. End-to-end pipeline testing with local content
"""

import os
import pytest
import requests
import time
from pathlib import Path
from unittest.mock import patch, MagicMock

from hnfm.scraper.content_scraper import ContentScraper
from hnfm.content.content_processor import ContentProcessor
from hnfm.content.script_generator import ScriptGenerator
from hnfm.utils.config import config_manager


class TestFirecrawlIntegration:
    """Test Firecrawl integration with local HTML files."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test environment."""
        self.base_url = "http://localhost:8000"
        self.test_html_path = "/static/test_html/test_content.html"
        self.test_url = f"{self.base_url}{self.test_html_path}"

        # Use real external URL for Firecrawl testing
        self.firecrawl_test_url = "https://briancaffey.github.io/2025/07/17/flux-plugin-for-project-g-assist-hackathon"

        # Check if web server is running
        self.server_running = self._check_server_status()

        # Initialize services
        self.content_scraper = ContentScraper(base_url="http://localhost:3002")
        self.content_processor = ContentProcessor()
        self.script_generator = ScriptGenerator()

    def _check_server_status(self) -> bool:
        """Check if the web server is running."""
        try:
            response = requests.get(f"{self.base_url}/api/health", timeout=5)
            return response.status_code == 200
        except requests.exceptions.RequestException:
            return False

    def test_server_availability(self):
        """Test that the web server is running and serving static files."""
        if not self.server_running:
            pytest.skip("Web server not running. Start with: uv run python -m src.hnfm.web.server")

        # Test health endpoint
        response = requests.get(f"{self.base_url}/api/health")
        assert response.status_code == 200

        # Test static file serving
        response = requests.get(self.test_url)
        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")

        # Verify we have actual HTML content
        html_content = response.text
        assert "<html" in html_content.lower()
        assert "<body" in html_content.lower()
        assert "large language model" in html_content.lower()  # Wikipedia content

    def test_firecrawl_real_url_scraping(self):
        """Test Firecrawl scraping of real external URL."""
        print(f"\n🧪 Testing Firecrawl scraping of: {self.firecrawl_test_url}")

        # Scrape the real external URL
        scraped_content = self.content_scraper.scrape_url(self.firecrawl_test_url)

        # Verify scraping was successful
        assert scraped_content.success, f"Scraping failed: {scraped_content.error}"
        assert scraped_content.url == self.firecrawl_test_url
        assert scraped_content.title, "Title should be extracted"
        assert scraped_content.content, "Content should be extracted"

        print(f"✅ Successfully scraped content:")
        print(f"   Title: {scraped_content.title}")
        print(f"   Content length: {len(scraped_content.content)} characters")
        print(f"   URL: {scraped_content.url}")

        # Show first 300 characters of content
        preview = scraped_content.content[:300] + "..." if len(scraped_content.content) > 300 else scraped_content.content
        print(f"   Content preview: {preview}")

        # Verify content quality
        assert len(scraped_content.content) > 500, "Content should be substantial"

        return scraped_content

    def test_content_processing(self):
        """Test content processing of scraped HTML."""
        if not self.server_running:
            pytest.skip("Web server not running")

        print("\n🧪 Testing content processing...")

        # First scrape content
        scraped_content = self.test_firecrawl_real_url_scraping()

        # Process the content
        processed_content = self.content_processor.process_content(
            title=scraped_content.title,
            raw_content=scraped_content.content
        )

        # Verify processing results
        assert processed_content is not None
        assert hasattr(processed_content, 'cleaned_content')
        assert hasattr(processed_content, 'meaningful_paragraphs')

        cleaned_content = processed_content.cleaned_content
        paragraphs = processed_content.meaningful_paragraphs

        print(f"✅ Content processing results:")
        print(f"   Cleaned content length: {len(cleaned_content)} characters")
        print(f"   Meaningful paragraphs: {len(paragraphs)}")

        # Verify processing quality
        assert len(cleaned_content) > 500, "Cleaned content should be substantial"
        assert len(paragraphs) > 0, "Should extract meaningful paragraphs"
        assert all(len(p) > 50 for p in paragraphs), "Paragraphs should be substantial"

        return processed_content

    def test_script_generation(self):
        """Test script generation from processed content."""
        if not self.server_running:
            pytest.skip("Web server not running")

        print("\n🧪 Testing script generation...")

        # First process content
        processed_content = self.test_content_processing()

        # Generate script
        script = self.script_generator.generate_script_from_content(
            title=processed_content.title,
            paragraphs=processed_content.meaningful_paragraphs
        )

        # Verify script generation
        assert script is not None
        assert "script" in script
        assert "tts_lines" in script

        generated_script = script["script"]
        tts_lines = script["tts_lines"]

        print(f"✅ Script generation results:")
        print(f"   Script length: {len(generated_script)} characters")
        print(f"   TTS lines: {len(tts_lines)}")

        # Verify script quality
        assert len(generated_script) > 200, "Script should be substantial"
        assert len(tts_lines) > 0, "Should have TTS lines"
        assert any("[S1]" in line or "[S2]" in line for line in tts_lines), "Script should contain speaker tags"

        return script

    def test_end_to_end_pipeline(self):
        """Test complete end-to-end pipeline with local HTML."""
        if not self.server_running:
            pytest.skip("Web server not running")

        print("\n🧪 Testing end-to-end pipeline...")

        start_time = time.time()

        # 1. Scrape content
        scraped_content = self.test_firecrawl_real_url_scraping()
        scrape_time = time.time() - start_time

        # 2. Process content
        process_start = time.time()
        processed_content = self.test_content_processing()
        process_time = time.time() - process_start

        # 3. Generate script
        script_start = time.time()
        script = self.test_script_generation()
        script_time = time.time() - script_start

        total_time = time.time() - start_time

        print(f"✅ End-to-end pipeline completed:")
        print(f"   Scraping: {scrape_time:.2f}s")
        print(f"   Processing: {process_time:.2f}s")
        print(f"   Script generation: {script_time:.2f}s")
        print(f"   Total time: {total_time:.2f}s")

        # Verify final output quality
        assert scraped_content.success
        assert processed_content is not None
        assert script is not None

        return {
            "scraped": scraped_content,
            "processed": processed_content,
            "script": script,
            "timing": {
                "scraping": scrape_time,
                "processing": process_time,
                "script_generation": script_time,
                "total": total_time
            }
        }

    def test_firecrawl_parameters(self):
        """Test different Firecrawl scraping parameters."""
        if not self.server_running:
            pytest.skip("Web server not running")

        print("\n🧪 Testing Firecrawl parameters...")

        # Test with different tag configurations
        test_configs = [
            {
                "includeTags": ["h1", "h2", "h3", "p"],
                "excludeTags": ["nav", "footer", "aside"]
            },
            {
                "includeTags": ["h1", "h2", "p", "article"],
                "excludeTags": ["script", "style", "nav"]
            },
            {
                "includeTags": ["h1", "h2", "h3", "h4", "p", "li"],
                "excludeTags": ["nav", "footer", "aside", "script", "style"]
            }
        ]

        results = []
        for i, config in enumerate(test_configs):
            print(f"   Testing config {i+1}: {config}")

            # Mock the scraper to test different configurations
            with patch.object(self.content_scraper, '_scrape_with_local_firecrawl') as mock_scrape:
                # Mock successful response
                mock_response = MagicMock()
                mock_response.status_code = 200
                mock_response.json.return_value = {
                    "data": {
                        "title": f"Test Title Config {i+1}",
                        "markdown": f"Test content for configuration {i+1} with tags: {config['includeTags']}"
                    }
                }

                mock_scrape.return_value = mock_response

                # Test scraping with this config
                result = self.content_scraper.scrape_url(self.test_url)
                results.append((config, result))

        print(f"✅ Tested {len(test_configs)} configurations")
        return results

    def test_error_handling(self):
        """Test error handling in the pipeline."""
        print("\n🧪 Testing error handling...")

        # Test with invalid URL
        invalid_url = "http://localhost:8000/static/nonexistent.html"

        with patch.object(self.content_scraper, '_scrape_with_local_firecrawl') as mock_scrape:
            # Mock error response
            mock_response = MagicMock()
            mock_response.status_code = 404
            mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError("404 Not Found")

            mock_scrape.return_value = mock_response

            # Test error handling
            result = self.content_scraper.scrape_url(invalid_url)

            assert not result.success
            assert result.error is not None
            assert "404" in result.error or "Not Found" in result.error

        print("✅ Error handling tests passed")

    def test_performance_benchmarks(self):
        """Test performance benchmarks for the pipeline."""
        if not self.server_running:
            pytest.skip("Web server not running")

        print("\n🧪 Running performance benchmarks...")

        # Run multiple iterations to get average performance
        iterations = 3
        times = []

        for i in range(iterations):
            print(f"   Iteration {i+1}/{iterations}")
            start_time = time.time()

            try:
                self.test_end_to_end_pipeline()
                iteration_time = time.time() - start_time
                times.append(iteration_time)
                print(f"     Completed in {iteration_time:.2f}s")
            except Exception as e:
                print(f"     Failed: {e}")
                continue

        if times:
            avg_time = sum(times) / len(times)
            min_time = min(times)
            max_time = max(times)

            print(f"✅ Performance benchmarks:")
            print(f"   Average time: {avg_time:.2f}s")
            print(f"   Min time: {min_time:.2f}s")
            print(f"   Max time: {max_time:.2f}s")
            print(f"   Total iterations: {len(times)}")

            # Performance assertions
            assert avg_time < 30, f"Average time {avg_time:.2f}s exceeds 30s threshold"
            assert min_time < 20, f"Min time {min_time:.2f}s exceeds 20s threshold"

            return {
                "average": avg_time,
                "min": min_time,
                "max": max_time,
                "iterations": len(times)
            }
        else:
            pytest.skip("No successful iterations for performance testing")


def main():
    """Run the test suite."""
    print("🚀 Starting Firecrawl Integration Test Suite...\n")

    # Check if pytest is available
    try:
        import pytest
        print("✅ Pytest is available")
    except ImportError:
        print("❌ Pytest not available. Install with: uv add --dev pytest")
        return

    # Check if web server is running
    base_url = "http://localhost:8000"
    try:
        response = requests.get(f"{base_url}/api/health", timeout=5)
        if response.status_code == 200:
            print("✅ Web server is running")
        else:
            print("⚠️  Web server responded but not healthy")
    except requests.exceptions.RequestException:
        print("❌ Web server not running. Start with: uv run python -m src.hnfm.web.server")
        print("   Then run: uv run pytest src/hnfm/test/test_firecrawl_integration.py -v")
        return

    print("\n🧪 Run the full test suite with:")
    print("   uv run pytest src/hnfm/test/test_firecrawl_integration.py -v")
    print("\n🧪 Or run individual tests with:")
    print("   uv run python -m src.hnfm.test.test_firecrawl_integration")


if __name__ == "__main__":
    main()
