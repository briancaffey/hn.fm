#!/usr/bin/env python3
"""Full pipeline test for hn.fm: Scraping → Processing → Script Generation."""

import os
from hnfm.scraper.hn_scraper import HNScraper
from hnfm.scraper.content_scraper import ContentScraper
from hnfm.content.content_processor import ContentProcessor
from hnfm.content.script_generator import ScriptGenerator
from hnfm.utils.config import Config

def test_full_pipeline():
    """Test the complete pipeline from HN scraping to script generation."""
    print("🚀 Testing Full hn.fm Pipeline\n")

    # Step 1: Get HN content
    print("📰 Step 1: Scraping Hacker News...")
    hn_scraper = HNScraper()
    stories = hn_scraper.get_top_stories(limit=1)

    if not stories:
        print("❌ No stories found from HN")
        return

    story = stories[0]
    url = story.get('url')
    title = story.get('title', 'Unknown')

    print(f"   Found: {title}")
    print(f"   URL: {url}")

    # Step 2: Scrape content with Firecrawl
    print("\n🔥 Step 2: Scraping content with Firecrawl...")
    config = Config()
    if not config.firecrawl_api_key:
        print("❌ FIRECRAWL_API_KEY not set")
        return

    content_scraper = ContentScraper(config.firecrawl_api_key)
    scraped_content = content_scraper.scrape_url(url)

    if not scraped_content:
        print("❌ Failed to scrape content")
        return

    print(f"   ✅ Successfully scraped content")
    print(f"   Title: {scraped_content.get('metadata', {}).get('title', 'No title')}")
    print(f"   Markdown length: {len(scraped_content.get('markdown', ''))} characters")

    # Save raw scraped content
    raw_file = f"raw_scraped_{title.replace(' ', '_')[:30]}.md"
    content_scraper.save_markdown(scraped_content, raw_file)
    print(f"   💾 Raw content saved to: {raw_file}")

    # Step 3: Process content
    print("\n🧹 Step 3: Processing and cleaning content...")
    processor = ContentProcessor()
    processed_content = processor.process_content(scraped_content)

    if not processed_content:
        print("❌ Failed to process content")
        return

    print(f"   ✅ Content processed successfully")
    print(f"   Cleaned text: {processed_content.get('word_count', 0)} words")
    print(f"   Key points extracted: {len(processed_content.get('key_points', []))}")

    # Save processed content
    processed_file = f"processed_{title.replace(' ', '_')[:30]}.md"
    processor.save_processed_content(processed_content, processed_file)
    print(f"   💾 Processed content saved to: {processed_file}")

    # Step 4: Generate podcast script
    print("\n🎙️ Step 4: Generating podcast script...")
    script_generator = ScriptGenerator()
    script = script_generator.generate_script(processed_content)

    if not script:
        print("❌ Failed to generate script")
        return

    print(f"   ✅ Script generated successfully")
    print(f"   Total speaker lines: {script.get('total_lines', 0)}")
    print(f"   Script saved to outputs/ directory")

    # Show sample of generated script
    print(f"\n📝 Sample of generated script:")
    speaker_lines = script.get('speaker_lines', [])
    for i, line in enumerate(speaker_lines[:6], 1):
        print(f"   {i:2d}. {line}")

    if len(speaker_lines) > 6:
        print(f"   ... and {len(speaker_lines) - 6} more lines")

    # Save prompts template for customization
    print(f"\n📋 Step 5: Saving prompts template...")
    script_generator.save_prompts_template("prompts_template.json")
    print(f"   💾 Prompts template saved to: prompts_template.json")

    print(f"\n🎉 Pipeline completed successfully!")
    print(f"\n📁 Files generated:")
    print(f"   • Raw content: {raw_file}")
    print(f"   • Processed content: {processed_file}")
    print(f"   • Script files: outputs/ directory")
    print(f"   • Prompts template: prompts_template.json")

    return script

def main():
    """Main test function."""
    try:
        script = test_full_pipeline()
        if script:
            print(f"\n✅ Full pipeline test completed successfully!")
            print(f"🎙️ Ready for TTS processing with {script.get('total_lines', 0)} speaker lines!")
        else:
            print(f"\n❌ Pipeline test failed")

    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
