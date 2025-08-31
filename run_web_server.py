#!/usr/bin/env python3
"""Run the hn.fm web server"""

import os
import sys
import uvicorn

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from hnfm.web.server import app

if __name__ == "__main__":
    # Get configuration from environment
    host = os.getenv("WEB_HOST", "0.0.0.0")
    port = int(os.getenv("WEB_PORT", "8000"))
    reload = os.getenv("WEB_RELOAD", "true").lower() == "true"

    print(f"Starting hn.fm web server on {host}:{port}")
    print(f"Open http://localhost:{port} in your browser")

    uvicorn.run(
        "src.hnfm.web.server:app", host=host, port=port, reload=reload, log_level="info"
    )
