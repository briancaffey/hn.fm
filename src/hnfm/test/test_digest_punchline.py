"""The punchline edition: the whole list, every story cut to its bullets.

Three things distinguish it from the prose editions and each is covered here:
it accepts stories that have only a scrape (no brief), it writes bullets
rather than paragraphs and must survive the model's formatting habits, and
it groups stories by which HN list they came from.
"""

from datetime import datetime
from unittest import mock

from ..digest import compose as _compose
from ..digest import render as _render
from ..digest.compose import Section, compose_punchline, parse_bullets, scrub_bullets
from ..digest.select import Digest, DigestStory


def _story(item_id, title, source=None, brief=None, excerpt=""):
    return DigestStory(
        item_id=item_id, run=1, title=title, url=f"https://x.test/{item_id}",
        hn_score=10, interest=70, rank=80.0, brief=brief or {},
        source=source, summary="", excerpt=excerpt,
    )


def _digest(*stories):
    return Digest(title="hn.fm · Punchline", subtitle="", generated_at=datetime(2026, 9, 7),
                  stories=list(stories))


class TestParseBullets:
    def test_strips_dashes_dots_and_numbers(self):
        text = "- first\n• second\n3. third\n* fourth"
        assert parse_bullets(text) == ["first", "second", "third", "fourth"]

    def test_caps_at_four(self):
        text = "\n".join(f"- bullet {i}" for i in range(7))
        assert len(parse_bullets(text)) == 4

    def test_drops_preamble_and_blank_lines(self):
        text = "Here are the bullets:\n\n- the answer\n\n- the catch"
        assert parse_bullets(text) == ["the answer", "the catch"]

    def test_empty_when_nothing_came_back(self):
        assert parse_bullets("") == []
        assert parse_bullets(None) == []


class TestComposePunchline:
    def test_groups_by_source_front_page_first(self):
        stories = [
            _story(1, "A new thing", source="new", excerpt="text"),
            _story(2, "A top thing", source="top", brief={"thesis": "t"}),
            _story(3, "An old thing", source=None, excerpt="text"),
        ]
        with mock.patch.object(_compose, "_write", return_value="- a\n- b"):
            sections = compose_punchline(_digest(*stories), workers=1)

        kinds = [(s.kind, s.title) for s in sections]
        assert kinds == [
            ("heading", "Front page"), ("punchline", "A top thing"),
            ("heading", "New arrivals"), ("punchline", "A new thing"),
            ("heading", "Elsewhere on Hacker News"), ("punchline", "An old thing"),
        ]
        assert sections[1].body == "a\nb"
        assert sections[1].story_id == 2

    def test_a_story_whose_call_fails_is_dropped_with_its_heading(self):
        stories = [
            _story(1, "Only story", source="new", excerpt="text"),
            _story(2, "Top story", source="top", excerpt="text"),
        ]

        def write(task, **fields):
            return None if fields["title"] == "Only story" else "- fine"

        with mock.patch.object(_compose, "_write", side_effect=write):
            sections = compose_punchline(_digest(*stories), workers=2)
        assert [s.title for s in sections] == ["Front page", "Top story"]

    def test_material_uses_the_scrape_when_there_is_no_brief(self):
        s = _story(1, "Bare", excerpt="the article says X")
        material = _compose._punchline_material(s)
        assert "no research brief" in material
        assert "the article says X" in material

    def test_material_uses_the_brief_when_there_is_one(self):
        s = _story(1, "Briefed", brief={
            "thesis": "the thesis", "key_facts": [{"claim": "fact one"}],
            "unknowns": ["who paid"],
        })
        material = _compose._punchline_material(s)
        assert "the thesis" in material
        assert "fact one" in material
        assert "who paid" in material
        assert "no research brief" not in material

    def test_order_is_preserved_across_the_thread_pool(self):
        stories = [_story(i, f"S{i}", source="top", excerpt="t") for i in range(12)]

        def write(task, **fields):
            import time
            # Later stories answer first; the page must not care.
            time.sleep(0.01 * (12 - int(fields["title"][1:])))
            return f"- {fields['title']}"

        with mock.patch.object(_compose, "_write", side_effect=write):
            sections = compose_punchline(_digest(*stories), workers=4)
        assert [s.body for s in sections[1:]] == [f"S{i}" for i in range(12)]


class TestRenderPunchline:
    def _sections(self):
        return [
            Section(kind="heading", title="Front page", body=""),
            Section(kind="punchline", title="Why X is slow", body="cause\nnumber",
                    story_id=1, url="https://x.test/1",
                    hn_url="https://news.ycombinator.com/item?id=1"),
            Section(kind="punchline", title="Ask HN: Y", body="consensus",
                    story_id=2, url=None,
                    hn_url="https://news.ycombinator.com/item?id=2"),
        ]

    def test_html_has_bullets_links_and_no_rules_between_items(self):
        html = _render.render_html(_digest(), sections=self._sections())
        assert '<h3 class="group">Front page</h3>' in html
        assert "<li>cause</li>" in html and "<li>number</li>" in html
        assert 'href="https://x.test/1">Why X is slow</a>' in html
        # A self-post links only to the thread.
        assert "Ask HN: Y" in html
        assert html.count('<hr class="rule"/>') == 0

    def test_epub_folds_a_group_into_one_chapter(self):
        groups = _render._chapter_groups(self._sections())
        assert len(groups) == 1
        assert [s.kind for s in groups[0]] == ["heading", "punchline", "punchline"]

    def test_epub_keeps_ordinary_sections_as_their_own_chapters(self):
        secs = [
            Section(kind="quick", title="Q", body="p"),
            Section(kind="deep", title="D", body="p"),
        ]
        assert len(_render._chapter_groups(secs)) == 2

    def test_docx_renders_bullets(self, tmp_path):
        from ..digest.docx import write_docx

        out = write_docx(_digest(), str(tmp_path / "p.docx"), sections=self._sections())
        import zipfile

        doc = zipfile.ZipFile(out).read("word/document.xml").decode()
        assert "Front page" in doc
        assert "• cause" in doc
        assert "Why X is slow" in doc


class TestSelectWithoutBrief:
    def test_story_with_only_a_scrape_is_included(self, monkeypatch):
        from ..digest import select as _select

        rows = [{"item_id": 7, "run": 1, "title": "Scraped only", "url": None,
                 "hn_score": 3, "interest": 50, "effective_rank": 40.0,
                 "source": "new"}]

        class Run:
            summary = "a summary"
            content_clean = "x" * 5000

        fake = mock.Mock()
        fake.list_triage.return_value = (rows, 1)
        fake.get_latest_story_brief.return_value = None
        fake.get_run.return_value = Run()
        fake.recently_published_item_ids.return_value = set()
        with mock.patch.dict("sys.modules", {}), \
                mock.patch("hnfm.db.repo.list_triage", fake.list_triage), \
                mock.patch("hnfm.db.repo.get_latest_story_brief", fake.get_latest_story_brief), \
                mock.patch("hnfm.db.repo.get_run", fake.get_run):
            with_brief = _select.select_stories(limit=5, since_hours=None, require_brief=True)
            without = _select.select_stories(limit=5, since_hours=None, require_brief=False)

        assert with_brief.stories == []
        assert len(without.stories) == 1
        st = without.stories[0]
        assert st.source == "new"
        assert st.summary == "a summary"
        assert len(st.excerpt) == _select.EXCERPT_CHARS
        assert not st.has_brief


class TestScrubBullets:
    """The first live edition: 36 of 385 bullets cited "commenter A" or a
    bare "commenter notes", mostly on stories with no discussion; seven
    said "No catch identified"."""

    def test_anonymous_attribution_without_discussion_is_dropped(self):
        bullets = ["the answer", "commenter A notes: NVD summaries are incomplete"]
        assert scrub_bullets(bullets, []) == ["the answer"]

    def test_bare_commenter_notes_is_dropped_even_with_discussion(self):
        bullets = ["the answer", "commenter notes that each engine differs"]
        assert scrub_bullets(bullets, ["tptacek"]) == ["the answer"]

    def test_attribution_to_a_real_username_is_kept(self):
        bullets = ["the answer", "Commenter KomoD notes undisclosed promotion."]
        assert scrub_bullets(bullets, ["KomoD"]) == bullets

    def test_attribution_to_an_unknown_name_is_dropped(self):
        bullets = ["the answer", "commenter Zed says it is fine"]
        assert scrub_bullets(bullets, ["KomoD"]) == ["the answer"]

    def test_filler_is_dropped(self):
        for f in ("No catch identified; the page has only footers.",
                  "None noted.",
                  "Not applicable — the material contains only navigation.",
                  "The article does not mention pricing."):
            assert scrub_bullets(["real", f], ["x"]) == ["real"], f

    def test_ordinary_negatives_survive(self):
        keep = ["No benchmark beat the baseline by more than 2%.",
                "Not all topics include equations; depth varies by subject."]
        assert scrub_bullets(keep, []) == keep

    def test_compose_drops_a_story_left_with_nothing(self):
        s = _story(1, "Thin", source="top", excerpt="t")
        with mock.patch.object(_compose, "_write", return_value="- commenter A notes X"):
            assert compose_punchline(_digest(s), workers=1) == []
