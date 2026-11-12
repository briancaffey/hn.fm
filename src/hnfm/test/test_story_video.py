"""The story video: brief, kit, treatments, and the checks on what the
author sends back. No model, no renderer."""

import pytest

from hnfm.hyperframes import author, kit, scenes, story

TEXT = ("You need 64 GB of unified memory just to load a 70-billion-parameter model, "
        "and Apple's chips can do it without a separate graphics card.")


def scene(n=1, text=TEXT, seconds=8.0, asset=None, start=0.0):
    return {"n": n, "text": text, "start": start, "seconds": seconds, "beat": "cold_open", "asset": asset,
            "cues": story.cues(text, start, start + seconds, [])}


BRIEF = {"title": "Which Mac Should You Buy to Run Local LLMs in 2026?", "summary": "A buyer's guide.",
         "theme": "infographic", "lead": 3.0, "tail": 4.0, "seconds": 15.0, "item_id": 1, "domain": "example.com",
         "narration": {"seconds": 8.0}, "scenes": [scene()]}


class TestBrief:
    def test_clean_drops_the_speaker_tag_and_quotes(self):
        assert story.clean('[S2] "Memory bandwidth is the‑thing."') == "Memory bandwidth is the-thing."
        assert story.speaker_of("[S2] hello") == "S2"

    def test_phrases_are_caption_sized_and_lose_nothing(self):
        parts = story.phrases(TEXT)
        assert " ".join(parts) == TEXT
        assert all(len(p.split()) <= story.CAPTION_WORDS + 2 for p in parts)

    def test_cues_follow_the_words_heard(self):
        heard = [{"word": "w", "start": 10 + i * 0.4} for i in range(20)]
        got = story.cues(TEXT, 10.0, 18.0, heard)
        times = [c["t"] for c in got]
        assert times == sorted(times) and times[0] >= 10.0 and times[-1] < 18.0
        assert all(c["d"] >= 0.3 for c in got)

    def test_cues_without_a_recogniser_are_spread_by_length(self):
        got = story.cues(TEXT, 0.0, 8.0, [])
        assert got[0]["t"] == 0.0 and got[-1]["t"] < 8.0


class TestKit:
    def test_host_has_a_slot_per_scene_and_every_caption(self):
        html = kit.host(BRIEF)
        assert 'data-composition-id="main"' in html and 'data-duration="15.00"' in html
        for cid in ("intro", "scene-01", "outro"):
            assert f'data-composition-src="compositions/{cid}.html"' in html
        assert html.count('class="clip k-cap"') == len(BRIEF["scenes"][0]["cues"])
        assert 'id="narration"' in html and 'data-start="3.00"' in html

    def test_a_scene_file_is_a_template_with_one_registered_timeline(self):
        text = kit.plain_scene(scene())
        assert text.count("<template>") == 1 and 'data-composition-id="scene-01"' in text
        assert 'window.__timelines["scene-01"] = tl;' in text and "paused: true" in text

    def test_plain_scene_finds_the_figure(self):
        assert "64 GB" in kit.plain_scene(scene())

    def test_intro_hides_a_score_too_small_to_boast_of(self):
        assert "points" not in kit.intro({**BRIEF, "points": 1, "comments": 0})
        assert "120 points" in kit.intro({**BRIEF, "points": 120, "comments": 0})


CARDS = [
    {"treatment": "figure", "value": "64 GB", "label": "unified memory", "kicker": "to load"},
    {"treatment": "compare", "left": {"name": "Apple's chips", "value": "64 GB"},
     "right": {"name": "graphics card", "value": "separate"}},
    {"treatment": "bars", "title": "unified memory", "rows": [{"name": "model", "value": 70}, {"name": "memory", "value": 64}]},
    {"treatment": "list", "items": ["unified memory", "Apple's chips", "graphics card"]},
    {"treatment": "steps", "items": ["load", "model", "chips"]},
    {"treatment": "phrase", "words": "without a separate graphics card", "accent": "card"},
    {"treatment": "quote", "quote": "Apple's chips can do it without a separate graphics card"},
]


class TestTreatments:
    @pytest.mark.parametrize("card", CARDS, ids=[c["treatment"] for c in CARDS])
    def test_every_treatment_builds_a_valid_scene(self, card):
        sc = scene()
        assert author.check_card(dict(card), sc, BRIEF) == []
        text = scenes.build(sc, card)
        a, b = text.index("<template>"), text.index("</template>") + len("</template>")
        parts = author.extract("```html\n" + text[a:b] + "\n```")
        # the same rules a free-form scene is held to
        assert author.vet(parts, "scene-01", None) == []
        assert 'window.__timelines["scene-01"] = tl;' in text

    def test_picture_needs_an_image(self):
        card = {"treatment": "picture", "label": "a separate graphics card"}
        assert author.check_card(dict(card), scene(), BRIEF)
        sc = scene(asset="assets/still-01.jpg")
        assert author.check_card(dict(card), sc, BRIEF) == []
        assert 'src="assets/still-01.jpg"' in scenes.build(sc, card)

    def test_items_arrive_in_order_and_before_the_scene_ends(self):
        sc = scene()
        times = scenes._spread(sc, ["unified memory", "Apple's chips", "graphics card"])
        assert times == sorted(times) and times[-1] <= sc["seconds"] - 0.9

    def test_when_finds_where_a_phrase_is_spoken(self):
        sc = scene()
        assert scenes.when(sc, "graphics card", 0.0) > scenes.when(sc, "64 GB", 0.0)

    def test_the_menu_offers_picture_only_with_an_image(self):
        assert "`picture`" not in scenes.menu(False) and "`picture`" in scenes.menu(True)


class TestCardChecks:
    def test_a_number_the_narrator_did_not_say_is_refused(self):
        notes = author.check_card({"treatment": "figure", "value": "24 GB", "label": "unified memory"}, scene(), BRIEF)
        assert any("not in the narration" in n for n in notes)

    def test_the_year_in_the_title_is_not_a_figure(self):
        notes = author.check_card({"treatment": "figure", "value": "2026", "label": "unified memory"}, scene(), BRIEF)
        assert any("not in the narration" in n for n in notes)

    def test_a_figure_holds_a_number(self):
        notes = author.check_card({"treatment": "figure", "value": "unified memory", "label": "Apple's chips"},
                                  scene(), BRIEF)
        assert any("must be a number" in n for n in notes)

    def test_words_from_nowhere_are_refused(self):
        card = {"treatment": "list", "items": ["quantum annealing", "blockchain ledgers", "solar panels"]}
        assert any("not in the narration" in n for n in author.check_card(card, scene(), BRIEF))

    def test_a_phrase_is_a_run_of_the_narrators_words(self):
        bad = {"treatment": "phrase", "words": "unified memory Apple's chips card"}
        assert any("consecutive" in n for n in author.check_card(bad, scene(), BRIEF))
        trailing = {"treatment": "phrase", "words": "just to load a"}
        assert any("ends on" in n for n in author.check_card(trailing, scene(), BRIEF))

    def test_the_same_treatment_twice_running_is_sent_back_once(self):
        card = {"treatment": "figure", "value": "64 GB", "label": "unified memory"}
        assert any("previous scene" in n for n in author.check_card(dict(card), scene(), BRIEF, previous="figure"))
        assert author.check_card(dict(card), scene(), BRIEF, previous="list") == []

    def test_fields_a_treatment_does_not_take_are_named(self):
        card = {"treatment": "figure", "value": "64 GB", "label": "memory", "items": ["a"]}
        assert any("does not take" in n for n in author.check_card(card, scene(), BRIEF))

    def test_a_kicker_that_repeats_the_value_is_dropped(self):
        card = {"treatment": "figure", "value": "64 GB", "label": "unified memory", "kicker": "64 GB"}
        assert author.check_card(card, scene(), BRIEF) == [] and "kicker" not in card

    def test_parse_card_reads_the_fenced_block_or_bare_json(self):
        assert author.parse_card('ok\n```json\n{"treatment": "phrase", "words": "a b c"}\n```')["treatment"] == "phrase"
        assert author.parse_card('{"treatment": "list", "items": ["a", "b"]}')["treatment"] == "list"
        assert author.parse_card("no card here") is None


class TestFreeform:
    def test_extract_takes_three_blocks_and_drops_timeline_boilerplate(self):
        reply = ('```css\n#scene-01-a{color:red}\n```\n```html\n<p id="scene-01-a">hi</p>\n```\n'
                 '```js\nconst tl = gsap.timeline({ paused: true });\n'
                 'tl.fromTo("#scene-01-a", {opacity:0}, {opacity:1}, 0.2);\n'
                 'window.__timelines["scene-01"] = tl;\n```')
        parts = author.extract(reply)
        assert "gsap.timeline" not in parts["js"] and "__timelines" not in parts["js"] and "fromTo" in parts["js"]
        assert author.vet(parts, "scene-01", None) == []
        assert 'window.__timelines["scene-01"] = tl;' in author.assemble("scene-01", parts)

    @pytest.mark.parametrize("bad,why", [
        ('<img src="https://example.com/x.png">', "web address"),
        ('<p id="other">x</p>', "must start with"),
        ('<p id="scene-01-a">x</p><script>fetch("/")</script>', "only the elements"),
    ])
    def test_vet_refuses(self, bad, why):
        notes = author.vet({"css": "", "html": bad, "js": 'tl.fromTo("#scene-01-a", {}, {}, 0);'}, "scene-01", None)
        assert any(why in n for n in notes), notes

    def test_vet_refuses_clocks_and_randomness(self):
        parts = {"css": "", "html": '<p id="scene-01-a">x</p>',
                 "js": 'setTimeout(() => {}, 5); tl.fromTo("#scene-01-a", {x: Math.random()}, {x: 0}, 0);'}
        assert len(author.vet(parts, "scene-01", None)) == 2

    def test_the_skill_is_shipped_and_carries_no_frontmatter_when_sent(self):
        for page in ("SKILL.md", "FREEFORM.md"):
            text = author.instructions(page)
            assert not text.startswith("---") and "hnfm-video" in text


class TestVideos:
    def test_a_video_with_no_narration_fails_plainly(self, tmp_path, monkeypatch):
        from hnfm.hyperframes import videos

        monkeypatch.setenv("OUTPUTS_DIR", str(tmp_path))
        monkeypatch.setattr(story, "brief", lambda *a: None)
        st = videos.make(1, 1, 1)
        assert st["state"] == "failed" and "no narration" in st["error"]
        assert videos.get("1-1-1")["state"] == "failed"
        assert [v["id"] for v in videos.listing()] == ["1-1-1"]
        assert videos.remove("1-1-1") and videos.get("1-1-1") is None

    def test_remove_stays_inside_the_videos_folder(self, tmp_path, monkeypatch):
        from hnfm.hyperframes import videos

        monkeypatch.setenv("OUTPUTS_DIR", str(tmp_path))
        assert videos.remove("../..") is False


class TestAgentClient:
    def test_base_is_the_profile_route(self, monkeypatch):
        from hnfm.hyperframes import hermes

        monkeypatch.setenv("HERMES_BASE_URL", "http://agent:8642/")
        monkeypatch.setenv("HERMES_PROFILE", "hnfm")
        assert hermes.base() == "http://agent:8642/p/hnfm"
        monkeypatch.delenv("HERMES_API_KEY", raising=False)
        assert not hermes.configured()
        with pytest.raises(hermes.AgentError):
            hermes.ask("hello")
