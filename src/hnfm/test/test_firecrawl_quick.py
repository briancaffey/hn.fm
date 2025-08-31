#!/usr/bin/env python3
"""Quick test script for Firecrawl functionality.

This script provides a simple way to test Firecrawl scraping and content processing
without running the full pytest suite. Useful for development and debugging.
"""

import requests
import time
from hnfm.scraper.content_scraper import ContentScraper
from hnfm.content.content_processor import ContentProcessor
from hnfm.content.script_generator import ScriptGenerator


def test_web_server():
    """Test if the web server is running and serving test HTML."""
    print("🧪 Testing web server availability...")

    base_url = "http://localhost:8000"
    test_html_path = "/static/test_html/test_content.html"
    test_url = f"{base_url}{test_html_path}"

    try:
        # Test health endpoint
        response = requests.get(f"{base_url}/api/health", timeout=5)
        if response.status_code == 200:
            print("✅ Web server is running")
        else:
            print(f"⚠️  Web server responded with status {response.status_code}")
            return False

        # Test static file serving
        response = requests.get(test_url, timeout=5)
        if response.status_code == 200:
            print("✅ Test HTML file is accessible")
            html_content = response.text
            if "large language model" in html_content.lower():
                print("✅ Test HTML contains expected content")
                return test_url
            else:
                print("⚠️  Test HTML doesn't contain expected content")
                return False
        else:
            print(f"❌ Test HTML file not accessible: {response.status_code}")
            return False

    except requests.exceptions.RequestException as e:
        print(f"❌ Web server not accessible: {e}")
        print("   Start the web server with: uv run python -m src.hnfm.web.server")
        return False


def test_firecrawl_scraping(test_url):
    """Test Firecrawl scraping of the test HTML."""
    real_url = "https://briancaffey.github.io/2025/07/17/flux-plugin-for-project-g-assist-hackathon"
    print(f"\n🧪 Testing Firecrawl scraping of: {real_url}")

    try:
        scraper = ContentScraper(base_url="http://localhost:3002")
        scraped_content = scraper.scrape_url(real_url)

        if scraped_content.success:
            print("✅ Successfully scraped content")
            print(f"   Title: {scraped_content.title}")
            print(f"   Content length: {len(scraped_content.content)} characters")
            print(f"   URL: {scraped_content.url}")

            # Show first 300 characters of content
            preview = scraped_content.content[:300] + "..." if len(scraped_content.content) > 300 else scraped_content.content
            print(f"   Content preview: {preview}")

            return scraped_content
        else:
            print(f"❌ Scraping failed: {scraped_content.error}")
            return None

    except Exception as e:
        print(f"❌ Scraping error: {e}")
        return None


def test_content_processing(scraped_content):
    """Test content processing of scraped content."""
    print("\n🧪 Testing content processing...")

    try:
        processor = ContentProcessor()
        processed_content = processor.process_content(
            title=scraped_content.title,
            raw_content=scraped_content.content
        )

        if processed_content:
            print("✅ Content processing successful")
            print(f"   Cleaned content length: {len(processed_content.cleaned_content)} characters")
            print(f"   Meaningful paragraphs: {len(processed_content.meaningful_paragraphs)}")

            # Show first paragraph
            if processed_content.meaningful_paragraphs:
                first_para = processed_content.meaningful_paragraphs[0]
                preview = first_para[:150] + "..." if len(first_para) > 150 else first_para
                print(f"   First paragraph preview: {preview}")

            return processed_content
        else:
            print("❌ Content processing failed")
            return None

    except Exception as e:
        print(f"❌ Content processing error: {e}")
        return None


def test_script_generation(processed_content):
    """Test script generation from processed content."""
    print("\n🧪 Testing script generation...")

    try:
        generator = ScriptGenerator()
        script = generator.generate_script_from_content(
            title=processed_content.title,
            paragraphs=processed_content.meaningful_paragraphs
        )

        if script:
            print("✅ Script generation successful")
            print(f"   Script length: {len(script['script'])} characters")
            print(f"   TTS lines: {len(script['tts_lines'])}")

            # Show script preview
            script_preview = script['script'][:300] + "..." if len(script['script']) > 300 else script['script']
            print(f"   Script preview: {script_preview}")

            # Show first few TTS lines
            if script['tts_lines']:
                print(f"   First TTS lines:")
                for i, line in enumerate(script['tts_lines'][:3]):
                    print(f"     {i+1}. {line}")

            return script
        else:
            print("❌ Script generation failed")
            return None

    except Exception as e:
        print(f"❌ Script generation error: {e}")
        return None


def run_full_test():
    """Run the complete test pipeline."""
    print("🚀 Starting Firecrawl Quick Test Suite...\n")

    start_time = time.time()

    # Test 1: Web server availability
    test_url = test_web_server()
    if not test_url:
        print("\n❌ Web server test failed. Cannot continue.")
        return False

    # Test 2: Firecrawl scraping
    scraped_content = test_firecrawl_scraping(test_url)
    if not scraped_content:
        print("\n❌ Scraping test failed. Cannot continue.")
        return False

    # Test 3: Content processing
    processed_content = test_content_processing(scraped_content)
    if not processed_content:
        print("\n❌ Content processing test failed. Cannot continue.")
        return False

    # Test 4: Script generation
    script = test_script_generation(processed_content)
    if not script:
        print("\n❌ Script generation test failed.")
        return False

    total_time = time.time() - start_time

    print(f"\n✅ All tests completed successfully in {total_time:.2f} seconds!")
    print("\n📊 Test Summary:")
    print(f"   - Web server: ✅ Running")
    print(f"   - HTML access: ✅ Accessible")
    print(f"   - Firecrawl scraping: ✅ Success")
    print(f"   - Content processing: ✅ Success")
    print(f"   - Script generation: ✅ Success")
    print(f"   - Total time: {total_time:.2f}s")

    return True


def main():
    """Main function."""
    try:
        success = run_full_test()
        if success:
            print("\n🎉 All tests passed! Your Firecrawl integration is working correctly.")
        else:
            print("\n💥 Some tests failed. Check the output above for details.")

    except KeyboardInterrupt:
        print("\n\n⏹️  Test interrupted by user")
    except Exception as e:
        print(f"\n💥 Unexpected error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
