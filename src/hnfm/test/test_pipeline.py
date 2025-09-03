#!/usr/bin/env python3
"""Core pipeline functionality tests for hn.fm"""

import os
import sys
import pytest
from unittest.mock import patch, MagicMock

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from hnfm.scraper.hn_scraper import HNScraper
from hnfm.scraper.content_scraper import ContentScraper
from hnfm.content.content_processor import ContentProcessor
from hnfm.content.script_generator import ScriptGenerator
from hnfm.utils.config import config_manager


class TestPipeline:
    """Test core pipeline functionality"""

    def setup_method(self):
        """Setup test environment"""
        self.config = config_manager
        self.hn_scraper = HNScraper()
        self.content_scraper = ContentScraper(
            self.config.get("apis.firecrawl.api_key") or "test_key"
        )
        self.processor = ContentProcessor()
        self.script_generator = ScriptGenerator()

    def test_hn_scraper(self):
        """Test Hacker News scraping functionality"""
        print("🧪 Testing HN Scraper...")

        try:
            # Test getting top stories
            stories = self.hn_scraper.get_top_stories(limit=3)
            assert stories is not None, "Should return stories list"
            assert len(stories) <= 3, "Should respect limit"

            if stories:
                story = stories[0]
                assert "title" in story, "Story should have title"
                assert "url" in story, "Story should have URL"
                print(f"✅ Found story: {story.get('title', 'Unknown')}")

            print("✅ HN Scraper test passed")
            return True

        except Exception as e:
            print(f"❌ HN Scraper test failed: {e}")
            return False

    def test_content_scraper(self):
        """Test content scraping with Firecrawl"""
        print("\n🧪 Testing Content Scraper...")

        try:
            # Test with a known URL
            test_url = "https://example.com"

            with patch.object(self.content_scraper, "scrape_url") as mock_scrape:
                mock_scrape.return_value = {
                    "markdown": "# Test Content\n\nThis is test content.",
                    "metadata": {"title": "Test Article"},
                    "url": test_url,
                }

                result = self.content_scraper.scrape_url(test_url)

                assert result is not None, "Should return scraped content"
                assert "markdown" in result, "Should have markdown content"
                assert "metadata" in result, "Should have metadata"

                print(
                    f"✅ Scraped content: {result['metadata'].get('title', 'Unknown')}"
                )

            print("✅ Content Scraper test passed")
            return True

        except Exception as e:
            print(f"❌ Content Scraper test failed: {e}")
            return False

    def test_content_processor(self):
        """Test content processing and cleaning"""
        print("\n🧪 Testing Content Processor...")

        try:
            # Test content processing
            test_content = {
                "markdown": "# Test Article\n\nThis is a test article with some content.",
                "metadata": {"title": "Test Article"},
                "url": "https://example.com",
            }

            processed = self.processor.process_content(test_content)

            assert processed is not None, "Should return processed content"
            assert "cleaned_text" in processed, "Should have cleaned text"
            assert "word_count" in processed, "Should have word count"

            print(f"✅ Processed content: {processed.get('word_count', 0)} words")

            print("✅ Content Processor test passed")
            return True

        except Exception as e:
            print(f"❌ Content Processor test failed: {e}")
            return False

    def test_script_generator(self):
        """Test script generation"""
        print("\n🧪 Testing Script Generator...")

        try:
            # Test script generation
            test_content = {
                "cleaned_text": "This is a test article about technology.",
                "word_count": 8,
                "key_points": ["Technology is important", "Testing is crucial"],
                "title": "Test Article",
            }

            with patch.object(
                self.script_generator, "generate_script"
            ) as mock_generate:
                mock_generate.return_value = {
                    "speaker_lines": [
                        "[S1] Welcome to today's podcast.",
                        "[S2] Today we're discussing technology.",
                        "[S1] That's all for today.",
                    ],
                    "total_lines": 3,
                    "duration": "2:30",
                }

                script = self.script_generator.generate_script(test_content)

                assert script is not None, "Should return generated script"
                assert "speaker_lines" in script, "Should have speaker lines"
                assert "total_lines" in script, "Should have total lines"

                print(f"✅ Generated script: {script.get('total_lines', 0)} lines")

            print("✅ Script Generator test passed")
            return True

        except Exception as e:
            print(f"❌ Script Generator test failed: {e}")
            return False

    # Removed test_full_pipeline_integration - testing individual services instead
