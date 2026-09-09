"""The [dev] marker on Kindle titles (DIGEST_TITLE_PREFIX).

The laptop and the cluster email the same device; the marker is the only way
to tell their editions apart on the shelf, so it has to reach every surface
Amazon might take the title from.
"""

from datetime import datetime

from ..digest import render as _render
from ..digest.docx import safe_filename
from ..digest.select import Digest


WHEN = datetime(2026, 9, 9)


def _digest():
    return Digest(title="hn.fm · Punchline", subtitle="", generated_at=WHEN, stories=[])


class TestPrefix:
    def test_unset_means_bare_title(self, monkeypatch):
        monkeypatch.delenv("DIGEST_TITLE_PREFIX", raising=False)
        assert _render.kindle_title("Punchline", WHEN) == "Punchline · 9/9"
        assert safe_filename("Punchline", WHEN, ext="html") == "Punchline 9-9.html"

    def test_dev_marker_reaches_every_surface(self, monkeypatch, tmp_path):
        monkeypatch.setenv("DIGEST_TITLE_PREFIX", "[dev]")
        assert _render.kindle_title("Punchline", WHEN) == "[dev] Punchline · 9/9"
        assert safe_filename("Punchline", WHEN, ext="html") == "[dev] Punchline 9-9.html"
        # Not doubled when the name already carries it.
        assert safe_filename("[dev] Punchline", WHEN) == "[dev] Punchline 9-9.docx"

        html = _render.render_html(_digest(), edition_name="Punchline")
        assert "<title>[dev] Punchline · 9/9</title>" in html

        import zipfile

        from ..digest.docx import write_docx

        out = write_docx(_digest(), str(tmp_path / "d.docx"), edition_name="Punchline")
        core = zipfile.ZipFile(out).read("docProps/core.xml").decode()
        assert "[dev] Punchline · 9/9" in core

        epub = _render.write_epub(_digest(), str(tmp_path / "d.epub"), edition_name="Punchline")
        opf = zipfile.ZipFile(epub).read("OEBPS/content.opf").decode()
        assert "[dev] Punchline · 9/9" in opf
