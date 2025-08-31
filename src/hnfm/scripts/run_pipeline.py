#!/usr/bin/env python3
"""CLI for running the hn.fm pipeline."""

import argparse
import sys
from pathlib import Path

# Add src to path (scripts are now in src/hnfm/scripts/)
sys.path.insert(0, str(Path(__file__).parent / ".." / ".."))

from hnfm.pipeline import PipelineManager
from hnfm.utils.config import config_manager
from hnfm.utils.logger import setup_logging


def main():
    """Main CLI function."""
    # Setup logging first
    log_level = config_manager.get("development.log_level", "INFO")
    setup_logging(level=log_level)

    parser = argparse.ArgumentParser(
        description="Run the hn.fm pipeline workflow",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run full pipeline for a story from top stories (default)
  python run_pipeline.py

  # Run pipeline for newest stories
  python run_pipeline.py --story-type newest

  # Run pipeline for Show HN stories
  python run_pipeline.py --story-type show

  # Run pipeline for Ask HN stories
  python run_pipeline.py --story-type ask

  # Resume from a specific step
  python run_pipeline.py --start-from "tts_generation"

  # Run with custom configuration
  python run_pipeline.py --config custom_config.yaml

  # List available steps
  python run_pipeline.py --list-steps

  # Show pipeline status
  python run_pipeline.py --status

  # Run with custom output directory
  python run_pipeline.py --output-dir custom_outputs

  # Run with custom cache directory
  python run_pipeline.py --cache-dir custom_cache
        """,
    )

    # Pipeline options
    parser.add_argument(
        "--story-type",
        choices=["top", "newest", "show", "ask"],
        default="top",
        help="Type of HN stories to scrape (default: top)",
    )

    parser.add_argument(
        "--start-from",
        choices=config_manager.get("pipeline.skippable_steps", []),
        help="Step to start from (resume pipeline)",
    )

    # Configuration options
    parser.add_argument("--config", help="Path to custom configuration file")

    # Pipeline management options
    parser.add_argument(
        "--list-steps", action="store_true", help="List available pipeline steps"
    )

    parser.add_argument("--status", action="store_true", help="Show pipeline status")

    # Output options
    parser.add_argument("--output-dir", help="Custom output directory")

    parser.add_argument("--cache-dir", help="Custom cache directory")

    # Development options
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be executed without running",
    )

    args = parser.parse_args()

    # Handle special commands that don't require story info
    if args.list_steps:
        list_pipeline_steps()
        return

    if args.status:
        show_pipeline_status()
        return

    # Load custom configuration if specified
    if args.config:
        config_manager.config_file = args.config
        config_manager.reload()

    # Set debug mode
    if args.debug:
        config_manager.set("development.debug", True)
        config_manager.set("development.log_level", "DEBUG")

    # Initialize pipeline manager
    pipeline_manager = PipelineManager(cache_dir=args.cache_dir)

    # Show dry run information
    if args.dry_run:
        show_dry_run_info(args, pipeline_manager)
        return

    # Run the pipeline
    try:
        print("🎬 Starting hn.fm pipeline")
        print(f"📰 Story Type: {args.story_type}")

        if args.start_from:
            print(f"🔄 Resuming from step: {args.start_from}")

        # Run pipeline with auto-generated story info
        state = pipeline_manager.run_pipeline(
            story_id="auto",
            story_title="auto",
            story_type=args.story_type,
            start_from_step=args.start_from,
        )

        # Show results
        show_pipeline_results(state)

    except Exception as e:
        print(f"❌ Pipeline failed: {e}")
        sys.exit(1)


def list_pipeline_steps():
    """List available pipeline steps."""
    print("🔧 Available Pipeline Steps:")
    print("=" * 50)

    steps = config_manager.get("pipeline.skippable_steps", [])
    for i, step in enumerate(steps, 1):
        print(f"{i:2d}. {step}")

    print(f"\nTotal steps: {len(steps)}")
    print("\nNote: Steps can be skipped using cached data when resuming.")


def show_pipeline_status():
    """Show pipeline status."""
    print("📊 Pipeline Status")
    print("=" * 50)

    # This would integrate with persistent storage
    print("Status tracking not yet implemented.")
    print("Use --dry-run to see what would be executed.")


def show_dry_run_info(args, pipeline_manager):
    """Show what would be executed in a dry run."""
    print("🔍 DRY RUN - No actual execution")
    print("=" * 50)
    print(f"Story Type: {args.story_type}")

    if args.start_from:
        print(f"Resume from: {args.start_from}")
        print(f"Steps to execute: {args.start_from} and dependencies")
    else:
        print("Execute all steps from beginning")

    print(f"\nConfiguration:")
    print(f"  TTS Service: {config_manager.get('tts.base_url', 'Not configured')}")
    print(
        f"  Studio Voice: {config_manager.get('studio_voice.target', 'Not configured')}"
    )
    print(f"  Default Voice: {config_manager.get('voice.default', 'Not configured')}")
    print(f"  Batch Size: {config_manager.get('tts.batch_size', 'Not configured')}")

    print(
        f"\nOutput Directory: {args.output_dir or config_manager.get('output.base_directory', 'outputs')}"
    )
    print(
        f"Cache Directory: {args.cache_dir or config_manager.get('pipeline.cache.directory', 'cache')}"
    )

    if args.debug:
        print(f"Debug Mode: Enabled")
        print(f"Log Level: {config_manager.get('development.log_level', 'INFO')}")


def show_pipeline_results(state):
    """Show pipeline execution results."""
    print("\n🎉 Pipeline Completed Successfully!")
    print("=" * 50)
    print(f"Story: {state.story_title}")
    print(f"Story ID: {state.story_id}")
    print(f"Completed at: {state.updated_at}")

    print(f"\n📋 Step Summary:")
    for step_name, step in state.steps.items():
        status = "✅" if step.completed else "❌"
        duration = ""
        if step.start_time and step.end_time:
            delta = step.end_time - step.start_time
            duration = f" ({delta.total_seconds():.1f}s)"

        print(f"  {status} {step_name}{duration}")

        if step.error:
            print(f"     Error: {step.error}")


if __name__ == "__main__":
    main()
