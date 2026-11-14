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

    def test_a_video_in_the_making_is_not_started_twice(self, tmp_path, monkeypatch):
        from hnfm.hyperframes import videos

        monkeypatch.setenv("OUTPUTS_DIR", str(tmp_path))
        videos.queued(1, 1, 1)
        assert videos.busy("1-1-1")
        st = videos.get("1-1-1")
        st["state"] = "directing"
        videos._save("1-1-1", st)
        assert videos.make(1, 1, 1)["state"] == "busy"
        # a status that stopped moving belongs to a worker that died
        monkeypatch.setattr(videos, "STALE_SECONDS", -1)
        assert not videos.busy("1-1-1")

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


class TestLocalOnlyAgent:
    """The profile that directs videos must run on the home lab's own model.
    These read the profile script itself, so a change that points it at a
    cloud provider fails here before anyone runs it."""

    SCRIPT = __import__("pathlib").Path(__file__).resolve().parents[3] / "deploy" / "hermes-profile.sh"

    def test_the_profile_model_is_the_local_gateway_route(self):
        text = self.SCRIPT.read_text()
        assert 'MODEL = "nemotron-lightning"' in text
        assert "api: http://litellm.observability.svc.cluster.local:4000/v1" in text
        assert "fallback_providers: []" in text

    def test_the_profile_names_no_cloud_endpoint_or_key(self):
        text = self.SCRIPT.read_text()
        for cloud in ("integrate.api.nvidia.com", "openrouter.ai", "api.groq.com", "api.openai.com"):
            assert cloud not in text
        assert 'mine["NVIDIA_API_KEY"]' not in text

    def test_each_round_keeps_its_hermes_run(self, monkeypatch, tmp_path):
        from hnfm.hyperframes import hermes

        reply = {"text": "no card here", "seconds": 1.0, "tokens": 5, "model": "", "run_id": "run_abc"}
        monkeypatch.setattr(hermes, "ask", lambda *a, **k: reply)
        monkeypatch.setattr(kit, "keep_plain", lambda *a, **k: None)
        monkeypatch.setattr(author, "ROUNDS", 1)
        rec = author.direct_scene(str(tmp_path), BRIEF, BRIEF["scenes"][0], [], job="t")
        assert rec["rounds"][0]["run_id"] == "run_abc"
        assert not rec["accepted"]


class TestThemesRead:
    @pytest.mark.parametrize("theme", sorted(__import__("hnfm.hyperframes.design_identity",
                                                         fromlist=["_"])._IDENTITIES))
    def test_accent_and_muted_text_pass_the_renderers_contrast_review(self, theme):
        d = kit.identity_for(theme)
        assert kit.contrast(d.accent, d.bg) >= 4.5
        assert kit.contrast(d.muted, d.bg) >= 4.5

    def test_a_readable_colour_is_left_alone(self):
        assert kit.readable("#2563eb", "#ffffff") == "#2563eb"


class TestShots:
    """A section is cut into short shots, each with pictures of its own."""

    def _section(self, seconds=15.0):
        text = ("Kurt Gödel left 1,009 pages of shorthand, and a logician fed them to an AI. "
                "In two days it produced a digest. It found hundreds of theorems no one knew existed.")
        sc = {"n": 1, "section": 1, "speaker": "S1", "beat": "", "text": text, "start": 10.0, "seconds": seconds,
              "cues": story.cues(text, 10.0, 10.0 + seconds, []), "image": "hero.png",
              "frames": ["hero.png", "f2.png", "f3.png", "f4.png", "f5.png"]}
        return sc

    def test_beats_cover_the_section_end_to_end_and_are_shot_length(self):
        sc = self._section()
        bs = story.beats(sc, [])
        assert len(bs) >= 2
        assert bs[0]["start"] == sc["start"]
        assert abs(sum(b["seconds"] for b in bs) - sc["seconds"]) < 0.05
        for a, b in zip(bs, bs[1:]):
            assert abs(a["start"] + a["seconds"] - b["start"]) < 0.02
        assert all(b["seconds"] >= story.BEAT_MIN - 0.01 for b in bs)
        assert bs[0]["image"] == "hero.png" and bs[1]["image"] is None

    def test_the_sections_frames_are_spread_over_its_beats(self):
        bs = story.beats(self._section(), [])
        got = [kit.shot_sources({**b, "n": i + 1}) for i, b in enumerate(bs)]
        flat = [p for g in got for p in g]
        assert flat[0] == "hero.png"
        assert len(set(flat)) == len(flat)  # no frame is shown twice

    def test_a_beats_own_picture_leads(self):
        b = {**story.beats(self._section(), [])[1], "n": 2, "picture": "own.png"}
        assert kit.shot_sources(b)[0] == "own.png"

    def test_numbers_count_but_years_do_not(self):
        from hnfm.hyperframes import cinema

        assert cinema.countable("1,009 pages") == ("", 1009.0, 0, True, " pages")
        assert cinema.countable("$2.5B")[1] == 2.5
        assert cinema.countable("1940") is None
        assert cinema.countable("unified memory") is None

    def test_words_are_revealed_when_said(self):
        from hnfm.hyperframes import cinema

        sc = {"seconds": 5.0, "words": [{"w": "Von", "t": 0.4}, {"w": "Plato", "t": 0.6}, {"w": "was", "t": 0.9},
                                         {"w": "flabbergasted,", "t": 1.1}]}
        assert cinema.spoken_times(sc, ["Von", "Plato", "was", "flabbergasted"], 0.2, 0.2) == [0.4, 0.6, 0.9, 1.1]


class TestPicturesAndMusic:
    def test_subjects_used_twice_are_to_be_avoided(self):
        from hnfm.hyperframes import pictures

        seen = ["a handwritten ledger on a wooden desk", "a ledger spread open on a wooden table", "a train at dusk"]
        got = pictures.avoid(seen)
        assert "ledger" in got and "wooden" in got and "train" not in got

    def test_a_near_copy_is_similar_and_a_new_scene_is_not(self):
        from hnfm.hyperframes import pictures

        a = "a handwritten ledger spread open on a desk, pages of dense notation"
        assert pictures._similar(a, a + " under a lamp") > 0.4
        assert pictures._similar(a, "a lone mathematician walks across a snowy campus") < 0.2

    def test_a_picture_with_words_in_it_is_refused(self):
        from hnfm.hyperframes import pictures

        assert pictures.check("a shop sign that says open hangs over a quiet street at night in the rain")
        assert not pictures.check("a lone mathematician walks across a snowy campus at dusk, carrying notebooks")

    def test_the_music_is_one_of_the_moods(self):
        from hnfm.hyperframes import music

        assert music.FALLBACK in music.MOODS.values()
        assert all("vocal" not in v for v in music.MOODS.values())


class TestShotPlan:
    """The menu of forms changes as the film goes; the model chooses from it."""

    def _sc(self, n=2, part=2, seconds=5.0):
        return {"n": n, "part": part, "seconds": seconds, "text": "the blades slow and stop", "start": 0.0}

    def test_the_last_form_is_not_offered_again_and_a_pan_is_rationed(self):
        from hnfm.hyperframes import shots

        hist = [{"form": "pan", "seconds": 4}, {"form": "still", "seconds": 4}]
        got = shots.allowed(self._sc(), hist)
        assert "still" not in got and "pan" not in got and "sequence" in got

    def test_a_section_opener_cannot_continue_and_the_film_opens_on_a_picture(self):
        from hnfm.hyperframes import shots

        got = shots.allowed(self._sc(part=1), [{"form": "drift", "seconds": 4}])
        assert "continue" not in got and "type" in got
        first = shots.allowed(self._sc(n=1, part=1), [])
        assert "type" not in first and "split" not in first

    def test_drift_cannot_repeat_and_the_least_used_form_comes_first(self):
        from hnfm.hyperframes import shots

        hist = [{"form": "drift", "seconds": 4}, {"form": "still", "seconds": 4}, {"form": "drift", "seconds": 4}]
        got = shots.allowed(self._sc(), hist)
        assert "drift" not in got
        assert got[0] not in ("drift", "still")

    def test_continue_cannot_hold_a_shot_past_ten_seconds(self):
        from hnfm.hyperframes import shots

        assert "continue" not in shots.allowed(self._sc(seconds=6), [{"form": "drift", "seconds": 5}])
        assert "continue" in shots.allowed(self._sc(seconds=3), [{"form": "drift", "seconds": 4}])

    def test_a_sequence_needs_its_changes(self):
        from hnfm.hyperframes import shots

        d = {"form": "sequence", "subject": "a wind turbine on a hill", "doing": "its blades slowing",
             "where": "a grey coastal wind farm"}
        assert shots.check_shot(d, self._sc(), ["sequence"], [])
        d["changes"] = ["the blades slow down", "the blades stop", "a red warning light blinks on"]
        assert shots.check_shot(d, self._sc(), ["sequence"], []) == []

    def test_continue_merges_the_beat_into_the_shot_before(self):
        from hnfm.hyperframes import shots

        a = {"text": "one", "cues": [1], "words": [{"w": "one", "t": 0.2}], "start": 10.0, "seconds": 4.0}
        b = {"text": "two", "cues": [2], "words": [{"w": "two", "t": 0.1}], "start": 14.0, "seconds": 3.0}
        shots._merge(a, b)
        assert a["seconds"] == 7.0 and a["text"] == "one two" and a["words"][1]["t"] == 4.1


class TestLayout:
    def test_words_go_where_the_picture_is_calm(self, tmp_path):
        from PIL import Image, ImageDraw

        from hnfm.hyperframes import layout

        img = Image.new("RGB", (1280, 720), (200, 200, 200))
        d = ImageDraw.Draw(img)
        for x in range(700, 1240, 12):  # busy stripes on the right half
            d.line([(x, 80), (x, 560)], fill=(0, 0, 0), width=3)
        p = tmp_path / "pic.png"
        img.save(p)
        order = layout.calm_order(str(p))
        assert order.index("left") < order.index("right")
        assert layout.focus(str(p))[0] > 50

    def test_type_shots_take_the_whole_frame(self):
        assert scenes._place({"n": 1, "form": "type", "shots": []}, ["left", "right"]) == "type"
        assert scenes._place({"n": 1, "form": "still", "shots": ["a"], "calm": ["top", "left"]}, ["left", "right"]) == "left"


def test_a_placeholder_script_title_gives_way_to_the_headline():
    assert story.title_of("hn.fm", "Thinking Machines: 4-Bit Training") == "Thinking Machines: 4-Bit Training"
    assert story.title_of("Gödel's Hidden Theorems", "AI unlocks Gödel's notebooks") == "Gödel's Hidden Theorems"
