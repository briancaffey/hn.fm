#!/usr/bin/env python3
"""Simple test script for hn.fm scraper."""

import os
from hnfm.scraper.hn_scraper import HNScraper
from hnfm.scraper.content_scraper import ContentScraper
from hnfm.utils.config import Config


def test_hn_scraper():
    """Test the HN scraper."""
    print("🧪 Testing HN Scraper...")

    scraper = HNScraper()

    # Get top stories
    stories = scraper.get_top_stories(limit=3)
    print(f"📰 Found {len(stories)} stories")

    for i, story in enumerate(stories, 1):
        print(f"  {i}. {story.get('title', 'No title')}")
        if story.get("url"):
            print(f"     URL: {story['url']}")

    # Get URLs
    urls = scraper.get_story_urls(limit=3)
    print(f"\n🔗 Found {len(urls)} URLs:")
    for url in urls:
        print(f"  - {url}")

    return urls


def test_content_scraper(urls):
    """Test the content scraper."""
    print("\n🧪 Testing Content Scraper...")

    config = Config()
    if not config.firecrawl_api_key:
        print("⚠️  FIRECRAWL_API_KEY not set, skipping content scraping test")
        return

    scraper = ContentScraper(config.firecrawl_api_key)

    for i, url in enumerate(urls[:1], 1):  # Just test first URL
        print(f"\n📄 Scraping URL {i}: {url}")

        content = scraper.scrape_url(url)
        if content:
            print(f"✅ Successfully scraped content")
            print(f"   Title: {content.get('metadata', {}).get('title', 'No title')}")
            print(f"   Markdown length: {len(content.get('markdown', ''))} characters")

            # Debug: Show full response structure
            print(f"\n🔍 Full response keys: {list(content.keys())}")
            if "metadata" in content:
                print(f"   Metadata keys: {list(content['metadata'].keys())}")
            if "error" in content:
                print(f"   Error: {content['error']}")
            if "status" in content:
                print(f"   Status: {content['status']}")

            # Save to file
            filename = f"scraped_content_{i}.md"
            if scraper.save_markdown(content, filename):
                print(f"💾 Saved markdown to {filename}")
        else:
            print(f"❌ Failed to scrape content")


def main():
    """Main test function."""
    print("🚀 Starting hn.fm scraper tests...\n")

    try:
        urls = test_hn_scraper()
        test_content_scraper(urls)
        print("\n✅ All tests completed!")

    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()
