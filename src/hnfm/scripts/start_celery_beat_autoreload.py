#!/usr/bin/env python3
"""
Auto-reloading Celery Beat for hn.fm development
Adapted for Docker environment
"""

import os
import signal
import subprocess
import sys
import time
from pathlib import Path

# Add src to path (scripts are now in src/hnfm/scripts/)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

# Set environment variables for debugging
os.environ.setdefault("DEBUG", "true")

# PID file for beat
PIDFILE = os.environ.get("PIDFILE", "/tmp/celerybeat.pid")

# Global variable to track the current process
current_process = None


def restart_celery_beat():
    """Restart the Celery Beat process"""
    global current_process
    print("🔄 Restarting Celery Beat...")

    # Kill existing process if running
    if current_process and current_process.poll() is None:
        print("🛑 Stopping existing Beat process...")
        try:
            current_process.terminate()
            current_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            print("⚠️  Force killing Beat process...")
            current_process.kill()
            current_process.wait()
        except Exception as e:
            print(f"⚠️  Error stopping process: {e}")

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
        current_process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            bufsize=1
        )

        # Give it a moment to start
        time.sleep(2)

        # Check if process is still running
        if current_process.poll() is None:
            print("✅ Beat process started successfully")
            return True
        else:
            print("❌ Beat process failed to start")
            return False

    except Exception as e:
        print(f"❌ Failed to start Celery Beat: {e}")
        return False


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


def signal_handler(signum, frame):
    """Handle shutdown signals gracefully"""
    global current_process
    print(f"\n🛑 Received signal {signum}, shutting down...")

    if current_process and current_process.poll() is None:
        print("🛑 Stopping Beat process...")
        current_process.terminate()
        try:
            current_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            current_process.kill()

    sys.exit(0)


if __name__ == "__main__":
    print("🚀 Starting Celery Beat with auto-reload...")
    print("Press Ctrl+C to stop")

    # Set up signal handlers for graceful shutdown
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    # Start initial beat
    restart_celery_beat()

    # Start file watcher
    watch_for_changes()
