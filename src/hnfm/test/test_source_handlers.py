"""Source-specific extraction (issue #17).

Firecrawl returns empty markdown for YouTube and HTTP 500 for PDFs, and both
are common on HN. Measured against the exact URLs that failed in a diagnostic
run: the Anthropic system card yields 478,824 characters where firecrawl gave
a 500, and two YouTube links yield 14,745 and 27,563 characters where
firecrawl gave a bare headline.
"""

from unittest.mock import MagicMock, patch

import pytest

from ..scraper import source_handlers as sh


class TestYouTubeDetection:
    @pytest.mark.parametrize(
        "url,expected",
        [
            ("https://www.youtube.com/watch?v=-Gnrp_caPvo", "-Gnrp_caPvo"),
            ("https://youtube.com/watch?v=abc123&t=30", "abc123"),
            ("https://youtu.be/nM86DBOqgPM", "nM86DBOqgPM"),
            ("https://www.youtube.com/shorts/xyz789", "xyz789"),
            ("https://www.youtube.com/embed/qqq111", "qqq111"),
            ("https://m.youtube.com/watch?v=mob01", "mob01"),
        ],
    )
    def test_video_ids_are_parsed(self, url, expected):
        assert sh.youtube_video_id(url) == expected

    @pytest.mark.parametrize(
        "url",
        [
            "https://iscinumpy.dev/post/flake8-lazy/",
            "https://notyoutube.com/watch?v=abc",
            "https://www.youtube.com/",
            "not a url at all",
        ],
    )
    def test_non_youtube_urls_return_none(self, url):
        assert sh.youtube_video_id(url) is None


class TestPdfDetection:
    def test_extension_is_enough(self):
        assert sh.looks_like_pdf("https://example.com/paper.pdf")

    def test_content_type_is_enough(self):
        assert sh.looks_like_pdf("https://example.com/download", "application/pdf")

    def test_an_ordinary_page_is_not_a_pdf(self):
        assert not sh.looks_like_pdf("https://example.com/post/")


class TestFailuresAreNonFatal:
    """A missing transcript is an ordinary outcome — many videos have none —
    and must fall through to the normal scrape path, not fail the run."""

    def test_transcript_errors_return_none(self):
        with patch(
            "youtube_transcript_api.YouTubeTranscriptApi.fetch",
            side_effect=RuntimeError("no transcript"),
        ):
            assert sh.fetch_youtube_transcript("https://youtu.be/abc") is None

    def test_pdf_errors_return_none(self):
        with patch("requests.get", side_effect=RuntimeError("timeout")):
            assert sh.fetch_pdf_text("https://example.com/x.pdf") is None

    def test_a_scan_with_no_text_layer_returns_none(self):
        resp = MagicMock()
        resp.headers = {"content-type": "application/pdf"}
        resp.content = b"%PDF-1.4"
        reader = MagicMock()
        reader.pages = [MagicMock(extract_text=lambda: "")]
        with (
            patch("requests.get", return_value=resp),
            patch("pypdf.PdfReader", return_value=reader),
        ):
            assert sh.fetch_pdf_text("https://example.com/scan.pdf") is None


class TestExtractDispatch:
    def test_an_ordinary_url_is_left_to_firecrawl(self):
        assert sh.extract("https://iscinumpy.dev/post/flake8-lazy/") == (None, None)

    def test_a_transcript_is_labelled_by_source(self):
        with patch.object(
            sh, "fetch_youtube_transcript", return_value="the talk"
        ):
            assert sh.extract("https://youtu.be/abc") == ("the talk", "youtube_transcript")

    def test_a_pdf_is_labelled_by_source(self):
        with patch.object(sh, "fetch_pdf_text", return_value="the paper"):
            assert sh.extract("https://example.com/x.pdf") == ("the paper", "pdf")


class TestExtractCap:
    def test_a_long_extract_is_truncated(self):
        """summarize_text_v1 passes its whole input to the LLM untruncated, so
        an unbounded extract blows the context window: the system card that
        motivated this handler is 478,824 characters."""
        out = sh._capped("word " * 40_000, "https://example.com/x.pdf")
        assert len(out) <= sh.MAX_EXTRACT_CHARS + 20
        assert out.endswith("[…truncated]")

    def test_a_normal_extract_is_untouched(self):
        text = "word " * 100
        assert sh._capped(text, "u") == text
