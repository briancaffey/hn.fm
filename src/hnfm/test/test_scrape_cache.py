"""Negative scrape cache and Wayback age gate (issue #18)."""

from unittest.mock import MagicMock, patch

import pytest

from ..scraper import scrape_cache
from ..scraper.content_scraper import ContentScraper, MIN_HOURS_FOR_ARCHIVE


class TestDenylist:
    @pytest.mark.parametrize(
        "url",
        [
            "https://twitter.com/GergelyOrosz/status/2095453567955968398",
            "https://x.com/someone/status/1",
            "https://mobile.twitter.com/a/status/2",
        ],
    )
    def test_known_unscrapeable_hosts_are_skipped(self, url):
        assert scrape_cache.is_denylisted(url)
        assert scrape_cache.recent_failure(url) is not None

    def test_ordinary_hosts_are_not(self):
        assert not scrape_cache.is_denylisted("https://iscinumpy.dev/post/flake8-lazy/")

    def test_malformed_urls_do_not_raise(self):
        assert scrape_cache.is_denylisted("not a url") is False


class TestNegativeCache:
    def test_a_cached_failure_short_circuits_the_scrape(self):
        scraper = ContentScraper()
        with (
            patch.object(
                scrape_cache, "recent_failure", return_value="503 last time"
            ),
            patch.object(scraper, "_scrape_with_local_firecrawl") as firecrawl,
        ):
            result = scraper.scrape_url("https://example.com/x")

        assert result.success is False
        assert "503 last time" in result.error
        firecrawl.assert_not_called()

    def test_a_failure_is_recorded_for_next_time(self):
        scraper = ContentScraper()
        with (
            patch.object(scrape_cache, "recent_failure", return_value=None),
            patch.object(scrape_cache, "record_failure") as record,
            patch.object(
                scraper, "_scrape_with_local_firecrawl",
                side_effect=RuntimeError("empty markdown"),
            ),
            patch("hnfm.scraper.content_scraper.get_wayback_url", return_value=None),
        ):
            scraper.scrape_url("https://example.com/x")

        record.assert_called_once()
        assert "empty markdown" in record.call_args[0][1]

    def test_cache_errors_behave_exactly_like_a_miss(self):
        """A Redis blip must not stop all scraping."""
        with patch.object(
            scrape_cache, "_redis", side_effect=RuntimeError("redis down")
        ):
            assert scrape_cache.recent_failure("https://example.com/x") is None
            scrape_cache.record_failure("https://example.com/x", "boom")  # no raise


class TestWaybackAgeGate:
    def test_a_fresh_story_skips_the_wayback_lookup(self):
        """Nothing has archived a URL submitted hours ago."""
        scraper = ContentScraper()
        with (
            patch.object(scrape_cache, "recent_failure", return_value=None),
            patch.object(scrape_cache, "record_failure"),
            patch.object(
                scraper, "_scrape_with_local_firecrawl",
                side_effect=RuntimeError("empty markdown"),
            ),
            patch("hnfm.scraper.content_scraper.get_wayback_url") as wayback,
        ):
            result = scraper.scrape_url("https://example.com/x", submitted_hours_ago=3.0)

        wayback.assert_not_called()
        assert result.success is False
        assert "too recent" in result.error

    def test_an_old_story_still_tries_wayback(self):
        scraper = ContentScraper()
        with (
            patch.object(scrape_cache, "recent_failure", return_value=None),
            patch.object(scrape_cache, "record_failure"),
            patch.object(
                scraper, "_scrape_with_local_firecrawl",
                side_effect=RuntimeError("empty markdown"),
            ),
            patch(
                "hnfm.scraper.content_scraper.get_wayback_url", return_value=None
            ) as wayback,
        ):
            scraper.scrape_url(
                "https://example.com/x", submitted_hours_ago=MIN_HOURS_FOR_ARCHIVE + 1
            )
        wayback.assert_called_once()

    def test_unknown_age_still_tries_wayback(self):
        """Age is a hint; absent it, behave as before."""
        scraper = ContentScraper()
        with (
            patch.object(scrape_cache, "recent_failure", return_value=None),
            patch.object(scrape_cache, "record_failure"),
            patch.object(
                scraper, "_scrape_with_local_firecrawl",
                side_effect=RuntimeError("empty markdown"),
            ),
            patch(
                "hnfm.scraper.content_scraper.get_wayback_url", return_value=None
            ) as wayback,
        ):
            scraper.scrape_url("https://example.com/x")
        wayback.assert_called_once()


class TestArchiveFloor:
    def test_a_43_char_archive_is_rejected(self):
        """Observed: 43 chars of an archived HTTP status page, recorded as a
        real scrape with fallback=False."""
        from ..scraper.content_scraper import ScrapedContent

        scraper = ContentScraper()
        tiny = ScrapedContent(title="t", content="404 Not Found", url="u", success=True)
        with (
            patch.object(scrape_cache, "recent_failure", return_value=None),
            patch.object(scrape_cache, "record_failure"),
            patch.object(
                scraper, "_scrape_with_local_firecrawl",
                side_effect=[RuntimeError("empty"), tiny],
            ),
            patch(
                "hnfm.scraper.content_scraper.get_wayback_url",
                return_value="https://web.archive.org/x",
            ),
        ):
            result = scraper.scrape_url("https://example.com/x", submitted_hours_ago=99)

        assert result.success is False
