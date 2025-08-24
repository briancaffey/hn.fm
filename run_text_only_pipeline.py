#!/usr/bin/env python3
"""Example script for running the pipeline in text-only mode."""

import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

from hnfm.pipeline import PipelineManager


def run_text_only_pipeline():
    """Run the pipeline in text-only mode to generate main.yaml."""
    print("🚀 Running Text-Only Pipeline")
    print("=" * 50)
    print("This will generate the main.yaml file with script content")
    print("No TTS, images, or video will be generated")
    print()

    try:
        # Initialize pipeline manager in text-only mode
        pipeline = PipelineManager(text_only=True)

        print("📋 Available pipeline steps:")
        for step_name, step in pipeline.pipeline_steps.items():
            print(f"   • {step_name}: {step.description}")

        print(f"\n🎯 Running {len(pipeline.pipeline_steps)} steps...")

        # Run the pipeline - let it get the actual story from HN
        result = pipeline.run_pipeline(
            story_id="auto",  # Will be determined by actual story
            story_title="auto",  # Will be determined by actual story
            story_type="top"
        )

        if result:
            print("\n✅ Pipeline completed successfully!")
            print(f"📁 Story ID: {result.story_id}")
            print(f"📁 Story Title: {result.story_title}")

                        # Check if main.yaml was created
            # Find the most recent story directory in outputs
            outputs_dir = Path("outputs")
            if outputs_dir.exists():
                # Get the most recently modified directory
                story_dirs = [d for d in outputs_dir.iterdir() if d.is_dir() and not d.name.startswith('.')]
                if story_dirs:
                    # Sort by modification time, newest first
                    latest_story_dir = max(story_dirs, key=lambda d: d.stat().st_mtime)
                    main_yaml_path = latest_story_dir / "content" / "main.yaml"

                    if main_yaml_path.exists():
                        print(f"📄 Main content file: {main_yaml_path}")
                        print(f"📁 Story directory: {latest_story_dir.name}")
                        print("   You can now review the content and run the full pipeline later")
                    else:
                        print("⚠️  Main content file not found in latest story directory")
                        print(f"   Latest story dir: {latest_story_dir}")
                        print(f"   Expected location: {main_yaml_path}")
                else:
                    print("⚠️  No story directories found in outputs")
            else:
                print("⚠️  Outputs directory not found")

            return True
        else:
            print("\n❌ Pipeline failed")
            return False

    except Exception as e:
        print(f"\n💥 Pipeline error: {e}")
        return False


def main():
    """Main entry point."""
    print("hn.fm Text-Only Pipeline")
    print("Generates script content and main.yaml structure")
    print()

    success = run_text_only_pipeline()

    if success:
        print("\n🎉 Success! Check the outputs directory for your content.")
        print("\nNext steps:")
        print("1. Review the generated main.yaml file")
        print("2. Run the full pipeline when ready for media generation")
        print("3. Or run individual steps as needed")
        return 0
    else:
        print("\n💥 Pipeline failed. Check the logs for details.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
