"""hn.fm - Transform Hacker News into your personalized AI-powered podcast."""

__version__ = "0.1.0"
__author__ = "Brian Caffey"
__email__ = "brian@example.com"

# Import modules when they're ready
try:
    from . import scraper
except ImportError:
    pass

try:
    from . import content
except ImportError:
    pass

try:
    from . import audio
except ImportError:
    pass

try:
    from . import video
except ImportError:
    pass

try:
    from . import utils
except ImportError:
    pass

__all__ = ["scraper", "content", "audio", "video", "utils"]
