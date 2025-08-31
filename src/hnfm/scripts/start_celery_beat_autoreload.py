#!/usr/bin/env python3
"""
Auto-reloading Celery Beat for hn.fm development
Adapted from Django example for FastAPI
"""

import os
import shlex
import subprocess
import sys
import time
from pathlib import Path

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

# Set environment variables for debugging
os.environ.setdefault("DEBUG", "true")

# PID file for beat
PIDFILE = os.environ.get("PIDFILE", "/tmp/celerybeat.pid")


def restart_celery_beat():
    """Restart the Celery Beat process"""
    print("🔄 Restarting Celery Beat...")

    # Kill existing Celery processes
    try:
        subprocess.run(shlex.split("pkill -f 'celery.*beat'"),
                      capture_output=True, timeout=5)
        time.sleep(1)  # Give time for processes to terminate
    except subprocess.TimeoutExpired:
        print("⚠️  Force killing Celery Beat processes...")
        subprocess.run(shlex.split("pkill -9 -f 'celery.*beat'"),
                      capture_output=True)

    # Remove old PID file if it exists
    try:
        os.remove(PIDFILE)
        print(f"🗑️  Removed old PID file: {PIDFILE}")
    except FileNotFoundError:
        pass

    # Start new beat process
    cmd = [
        "celery",
        "--app=src.hnfm.web.celery_app:celery_app",
        "beat",
        "--loglevel=info",
        f"--pidfile={PIDFILE}",
        "--scheduler=celery.beat.PersistentScheduler"
    ]

    print(f"🚀 Starting Beat with command: {' '.join(cmd)}")
    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to start Celery Beat: {e}")
        return False

    return True


def watch_for_changes():
    """Watch for file changes and restart beat when needed"""
    print("👀 Watching for code changes...")

    # Directories to watch
    watch_dirs = [
        Path("src/hnfm"),
        Path("src/hnfm/web"),
        Path("src/hnfm/content"),
        Path("src/hnfm/audio"),
        Path("src/hnfm/video"),
        Path("src/hnfm/scraper"),
    ]

    # File extensions to watch
    watch_extensions = {'.py', '.pyx', '.pyi'}

    # Track file modification times
    file_times = {}

    def get_file_times():
        """Get modification times for all Python files"""
        times = {}
        for watch_dir in watch_dirs:
            if watch_dir.exists():
                for py_file in watch_dir.rglob("*.py"):
                    try:
                        times[str(py_file)] = py_file.stat().st_mtime
                    except OSError:
                        continue
        return times

    # Initialize file times
    file_times = get_file_times()
    print(f"📁 Watching {len(file_times)} Python files for changes...")

    while True:
        try:
            time.sleep(1)  # Check every second

            current_times = get_file_times()

            # Check for changes
            for file_path, current_time in current_times.items():
                if file_path not in file_times or file_times[file_path] != current_time:
                    print(f"📝 Detected change in {file_path}")
                    file_times = current_times

                    # Restart beat
                    if restart_celery_beat():
                        print("✅ Beat restarted successfully")
                    else:
                        print("❌ Failed to restart Beat")
                    break

            # Update file times
            file_times = current_times

        except KeyboardInterrupt:
            print("\n🛑 Stopping auto-reload watcher...")
            break
        except Exception as e:
            print(f"⚠️  Error in file watcher: {e}")
            time.sleep(5)  # Wait before retrying


if __name__ == "__main__":
    print("🚀 Starting Celery Beat with auto-reload...")
    print("Press Ctrl+C to stop")

    # Start initial beat
    restart_celery_beat()

    # Start file watcher
    watch_for_changes()
