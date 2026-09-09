"""Source images (plans/18): collect, store, analyse, cast.

The network and the models are mocked; PIL is real, because the resize is
the one thing here that must actually happen to a real image.
"""

import io
from datetime import datetime
from unittest import mock

from PIL import Image

from ..content import source_casting as casting
from ..content import source_image_analysis as analysis
from ..db import repo
from ..scraper import source_images as src
from ..web.models import HNItem, ProcessedRun


def _png(w, h, color=(200, 30, 30)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (w, h), color).save(buf, "PNG")
    return buf.getvalue()


class TestCollect:
    HTML = """
    <html><head>
      <meta property="og:image" content="/social.jpg">
      <meta name="twitter:image" content="https://cdn.x/social.jpg">
    </head><body>
      <img src="/img/logo.png" alt="logo">
      <img src="pixel.gif">
      <img data-src="/lazy/real.jpg" src="data:image/gif;base64,R0lGOD" alt="the board">
      <img srcset="/a-400.jpg 400w, /a-1600.jpg 1600w, /a-800.jpg 800w" alt="chart">
      <img src="/tiny.png" width="32" height="32">
      <img src="/dup.jpg"><img src="/dup.jpg">
      <img src="/diagram.svg">
    </body></html>
    """

    def test_og_first_then_page_order_junk_dropped(self):
        out = src.collect(self.HTML, "https://x.test/post/1")
        urls = [c["url"] for c in out]
        assert urls[0] == "https://x.test/social.jpg"
        assert out[0]["origin"] == "og:image"
        assert "https://cdn.x/social.jpg" in urls
        assert "https://x.test/lazy/real.jpg" in urls
        assert "https://x.test/a-1600.jpg" in urls          # widest srcset candidate
        assert "https://x.test/a-800.jpg" not in urls
        assert not any("logo" in u or "pixel" in u or ".svg" in u or "tiny" in u for u in urls)
        assert urls.count("https://x.test/dup.jpg") == 1

    def test_alt_and_origin_recorded(self):
        out = {c["url"]: c for c in src.collect(self.HTML, "https://x.test/")}
        assert out["https://x.test/lazy/real.jpg"]["alt"] == "the board"
        assert out["https://x.test/a-1600.jpg"]["origin"] == "srcset"

    def test_largest_srcset(self):
        assert src._largest_srcset("/s.jpg 1x, /l.jpg 2x") == "/l.jpg"
        assert src._largest_srcset("/only.jpg") == "/only.jpg"


class TestStore:
    def _fake_get(self, table):
        def get(url, **kw):
            body = table.get(url)
            m = mock.MagicMock()
            m.__enter__.return_value = m
            m.status_code = 200 if body is not None else 404
            m.headers = {"content-type": "image/png", "content-length": str(len(body or b""))}
            m.iter_content = lambda n: [body or b""]
            return m
        return get

    def test_downscales_large_keeps_small_drops_tiny_and_dupes(self, tmp_path):
        big = _png(4000, 2000)
        small = _png(600, 400, (0, 0, 200))
        table = {
            "https://x/big.png": big, "https://x/small.png": small,
            "https://x/tiny.png": _png(100, 100), "https://x/again.png": big,
            "https://x/missing.png": None,
        }
        cands = [{"url": u, "alt": "", "origin": "img"} for u in table]
        with mock.patch.object(src.requests, "get", self._fake_get(table)):
            kept = src.store(cands, str(tmp_path), max_dim=1536)

        assert [k["url"] for k in kept] == ["https://x/big.png", "https://x/small.png"]
        b, s = kept
        assert (b["width"], b["height"]) == (4000, 2000)
        assert b["resized"] is True
        assert max(b["stored_width"], b["stored_height"]) == 1536
        assert b["bytes"] == len(big)
        assert b["stored_bytes"] > 0 and b["stored_bytes"] < b["bytes"] * 2
        assert s["resized"] is False
        assert (s["stored_width"], s["stored_height"]) == (600, 400)
        assert (tmp_path / "src_1.jpg").exists() and (tmp_path / "src_2.jpg").exists()
        # The stored copy really is the downscaled one.
        assert max(Image.open(tmp_path / "src_1.jpg").size) == 1536

    def test_refuses_oversized_downloads(self, tmp_path, monkeypatch):
        monkeypatch.setattr(src, "MAX_DOWNLOAD_BYTES", 10_000)
        table = {"https://x/huge.png": _png(2000, 2000)}
        with mock.patch.object(src.requests, "get", self._fake_get(table)):
            kept = src.store([{"url": "https://x/huge.png", "alt": "", "origin": "img"}],
                             str(tmp_path))
        assert kept == []


class TestAnalyze:
    def test_returns_row_fields_and_tokens(self, tmp_path):
        path = tmp_path / "a.jpg"
        Image.new("RGB", (900, 600)).save(path)

        class Result:
            description = "A bar chart of latency by version."
            kind = "chart"
            subjects = ["bar chart", "latency", ""]
            text_in_image = "p99 latency"
            interest = 82
            usable = True
            use_hint = "Hold on it while the numbers are read."
            caveat = ""

        svc = mock.Mock()
        svc.usage = {"calls": 1, "tokens_in": 1200, "tokens_out": 90, "model": "omni"}
        svc.generate_structured_vision.return_value = Result()
        with mock.patch.object(analysis, "LLMService", return_value=svc, create=True), \
                mock.patch("hnfm.content.llm_service.LLMService", return_value=svc):
            out = analysis.analyze(str(path), title="T", summary="S", alt="", origin="img")

        assert out["kind"] == "chart" and out["usable"] is True and out["interest"] == 82
        assert out["subjects"] == ["bar chart", "latency"]
        assert (out["tokens_in"], out["tokens_out"], out["analysis_model"]) == (1200, 90, "omni")
        assert out["analysis_error"] is None
        # The model was shown a small copy, not the stored one.
        b64 = svc.generate_structured_vision.call_args.kwargs["image_b64"]
        assert len(b64) < 200_000

    def test_failure_is_recorded_not_raised(self, tmp_path):
        path = tmp_path / "a.jpg"
        Image.new("RGB", (300, 300)).save(path)
        svc = mock.Mock()
        svc.usage = {"calls": 0, "tokens_in": 0, "tokens_out": 0, "model": None}
        svc.generate_structured_vision.side_effect = RuntimeError("omni down")
        with mock.patch("hnfm.content.llm_service.LLMService", return_value=svc):
            out = analysis.analyze(str(path), title="T", summary="S")
        assert "omni down" in out["analysis_error"]
        assert out["tokens_in"] is None


def _img(id_, path, kind="photo", interest=80, usable=True):
    return {"id": id_, "path": path, "kind": kind, "interest": interest,
            "usable": usable, "description": f"image {id_}", "text_in_image": "",
            "use_hint": ""}


class TestCast:
    def _entries(self, *triples):
        class E:
            def __init__(self, s, i, t):
                self.section, self.image_id, self.treatment, self.why = s, i, t, "because"
        class R:
            cast = [E(*t) for t in triples]
        return R()

    def test_guardrails(self, tmp_path):
        p = str(tmp_path / "x.jpg"); Image.new("RGB", (10, 10)).save(p)
        images = [
            _img(1, p), _img(2, p, kind="chart"), _img(3, p, usable=False),
            _img(4, p, interest=10), _img(5, p, kind="logo"),
        ]
        result = self._entries(
            (1, 1, "restyle"),   # fine
            (2, 2, "restyle"),   # chart: forced as_is
            (3, 3, "as_is"),     # not usable: dropped
            (4, 4, "as_is"),     # low interest: dropped
            (5, 5, "as_is"),     # logo: dropped
            (6, 1, "as_is"),     # image 1 again: dropped
            (9, 2, "as_is"),     # section out of range
        )
        svc = mock.Mock(); svc.generate_structured.return_value = result
        with mock.patch("hnfm.content.llm_service.LLMService", return_value=svc):
            out = casting.cast(["s1", "s2", "s3", "s4", "s5", "s6"], images, "Noir", max_uses=3)
        assert sorted(out) == [1, 2]
        assert out[1]["treatment"] == "restyle"
        assert out[2]["treatment"] == "as_is"

    def test_nothing_eligible_means_no_call(self):
        svc = mock.Mock()
        with mock.patch("hnfm.content.llm_service.LLMService", return_value=svc):
            assert casting.cast(["s1"], [_img(1, "/nope.jpg")], "Noir") == {}
        svc.generate_structured.assert_not_called()

    def test_place_contains_without_cropping(self, tmp_path):
        p = str(tmp_path / "wide.jpg")
        Image.new("RGB", (1000, 200), (255, 255, 255)).save(p)
        out = casting.place(p, str(tmp_path / "out.png"), 640, 360)
        im = Image.open(out)
        assert im.size == (640, 360)
        # Centre row is the white image; the top row is the darkened backdrop.
        assert im.getpixel((320, 180)) == (255, 255, 255)
        assert max(im.getpixel((320, 5))) < 200

    def test_restyle_prompt_names_theme_and_subject(self):
        theme = mock.Mock(name="Ink Noir Comic", style="ink, halftone")
        theme.name = "Ink Noir Comic"
        s = casting.restyle_prompt({"description": "a green circuit board"}, theme)
        assert "Ink Noir Comic" in s and "ink, halftone" in s and "circuit board" in s


class TestRepo:
    def _seed(self, item_id=7, run=1):
        repo.upsert_item(HNItem(id=item_id, title="Story", url="https://x/p"))
        repo.save_run(ProcessedRun(key=f"{item_id}:{run}", item_id=item_id, run=run,
                                   created_at=datetime.utcnow(), source_url="https://x/p",
                                   content_raw="", content_clean="", summary="s",
                                   short_description="s", tags=["t"], emoji=["x"],
                                   haiku="h"))

    def test_replace_update_list_and_legacy_mirror(self, tmp_path):
        self._seed()
        rows = repo.replace_source_images(7, 1, [
            {"index": 1, "url": "https://x/a.jpg", "alt": "a", "origin": "img",
             "width": 4000, "height": 2000, "bytes": 900000, "stored_width": 1536,
             "stored_height": 768, "stored_bytes": 120000, "resized": True,
             "path": str(tmp_path / "a.jpg")},
            {"index": 2, "url": "https://x/b.jpg", "alt": "", "origin": "og:image",
             "width": 800, "height": 600, "bytes": 50000, "stored_width": 800,
             "stored_height": 600, "stored_bytes": 50000, "resized": False,
             "path": str(tmp_path / "b.jpg")},
        ])
        assert [r["index"] for r in rows] == [1, 2]
        assert rows[0]["id"] and rows[0]["resized"] is True

        repo.update_source_image(rows[0]["id"], description="a chart", kind="chart",
                                 interest=90, usable=True, tokens_in=1000, tokens_out=50)
        items, total, facets = repo.list_source_images(sort="interest")
        assert total == 2
        assert items[0]["description"] == "a chart" and items[0]["title"] == "Story"
        assert facets == {"kinds": {"chart": 1}, "usable": 1,
                          "tokens_in": 1000, "tokens_out": 50}
        assert [i["id"] for i in repo.list_source_images(usable=True)[0]] == [rows[0]["id"]]

        # The media planner's legacy column follows along.
        legacy = repo.get_run_source_images(7, 1)
        assert legacy[0]["description"] == "a chart"
        assert legacy[0]["id"] == rows[0]["id"]

        # A later run of the same story sees the page's pictures.
        assert [i["id"] for i in repo.source_images_for_item(7)] == [r["id"] for r in rows]

        # A re-collect replaces rather than accumulates.
        again = repo.replace_source_images(7, 1, [])
        assert again == [] and repo.list_source_images()[1] == 0
        assert repo.source_images_for_item(7) == []
