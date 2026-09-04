"""Negative cache and domain denylist for scraping (issue #18).

A URL that cannot be scraped was retried from scratch on every run, paying the
full firecrawl timeout plus a Wayback lookup each time. The same Twitter URL
was attempted twice within one hour during a diagnostic run, failing
identically both times.

The cache is deliberately negative-only: a *successful* scrape is already
persisted on the run row, and re-scraping on a new run is intentional (sources
change). Only the failures are worth remembering, and only briefly — a site
that is down now may be up in an hour.
"""

import logging
import os
import urllib.parse

logger = logging.getLogger(__name__)

# Hours, not days. A 503 is usually transient; the point is to stop paying for
# the same failure inside one batch, not to give up on a domain.
FAILURE_TTL_SECONDS = int(os.getenv("SCRAPE_FAILURE_TTL", "21600"))  # 6h

# Hosts that firecrawl cannot retrieve at all — it returns empty markdown every
# time. Skipping the attempt saves the timeout AND the pointless Wayback
# lookup that follows it. The discussion carries these stories instead.
DENYLISTED_HOSTS = {
    "twitter.com", "www.twitter.com", "x.com", "www.x.com", "mobile.twitter.com",
}

_KEY = "hnfm:scrape:failed:"


def _host(url: str) -> str:
    try:
        return (urllib.parse.urlparse(url).hostname or "").lower()
    except Exception:
        return ""


def is_denylisted(url: str) -> bool:
    return _host(url) in DENYLISTED_HOSTS


def _redis():
    from ..db import repo

    return getattr(repo, "redis_client", None) or _redis_from_env()


def _redis_from_env():
    import redis

    return redis.Redis(
        host=os.getenv("REDIS_HOST", "localhost"),
        port=int(os.getenv("REDIS_PORT", "6379")),
        db=int(os.getenv("REDIS_DB", "0")),
        password=os.getenv("REDIS_PASSWORD") or None,
        decode_responses=True,
    )


def recent_failure(url: str) -> str | None:
    """The recorded reason this URL failed recently, or None.

    Never raises: a cache miss and a broken cache must behave identically, or
    a Redis blip would stop all scraping.
    """
    if is_denylisted(url):
        return f"{_host(url)} is denylisted — firecrawl returns empty markdown for it"
    try:
        return _redis().get(_KEY + url)
    except Exception as e:
        logger.debug(f"scrape cache read failed (non-fatal): {e}")
        return None


def record_failure(url: str, reason: str) -> None:
    try:
        _redis().setex(_KEY + url, FAILURE_TTL_SECONDS, str(reason)[:300])
    except Exception as e:
        logger.debug(f"scrape cache write failed (non-fatal): {e}")


def forget(url: str) -> None:
    """Drop a cached failure — for a manual retry that should really try."""
    try:
        _redis().delete(_KEY + url)
    except Exception as e:
        logger.debug(f"scrape cache delete failed (non-fatal): {e}")
