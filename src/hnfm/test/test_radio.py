"""HNFM on air: the format, the planner's rules, the writers' room checks,
the mix graphs, the director's sequencing, and the switch that keeps all of
it off. No test here calls a model or runs ffmpeg."""

from datetime import datetime

import pytest

from ..db import repo
from ..radio import director, format as fmt, mix, planner, qa, writers
from ..radio.schemas import Copy, Line, Review, copy_schema
from ..radio.segments import BIT_ROTATION, SEGMENTS, resolve_bit, segment, story_matches


def _stories(n=8, **over):
    out = []
    for i in range(1, n + 1):
        out.append({"item_id": 100 + i, "title": f"Story {i}", "age_hours": i, "score": 10 * i,
                    "comments": i, "kind": "story", "discussed": False, "what": f"what {i}", **over})
    return out


def _copy(*texts, speaker="mia"):
    return Copy(lines=[Line(speaker=speaker, mood="default", text=t) for t in texts])


# ---------------------------------------------------------------------------
# The format: code owns the shape
# ---------------------------------------------------------------------------


class TestFormat:
    def test_the_shows_cover_the_day_exactly_once(self):
        hours = [h for s in fmt.SHOWS for h in s.hours()]
        assert sorted(hours) == list(range(24))

    def test_every_slot_in_every_clock_is_a_segment(self):
        for s in fmt.SHOWS:
            assert len(s.clock) == 4
            for quarter in s.clock:
                for slot in quarter:
                    assert slot == "bit" or slot in SEGMENTS, f"{s.key}: {slot}"

    def test_every_host_in_a_show_can_speak(self):
        from ..radio.voice import HOSTS

        for s in fmt.SHOWS:
            for h in (s.anchor, s.cohost, *s.cast):
                assert h in HOSTS

    def test_the_show_changes_with_the_hour_and_wraps_midnight(self):
        assert fmt.show_at(datetime(2026, 11, 12, 7, 0)).key == "cold_start"
        assert fmt.show_at(datetime(2026, 11, 12, 23, 30)).key == "night_shift"
        assert fmt.show_at(datetime(2026, 11, 12, 1, 0)).key == "night_shift"
        assert fmt.show_at(datetime(2026, 11, 12, 3, 0)).key == "garbage_collection"

    def test_a_new_hour_opens_the_show_and_quarters_follow_in_order(self):
        noon = datetime(2026, 11, 12, 12, 5)
        assert fmt.next_quarter(None, noon) == 0
        assert fmt.next_quarter({"hour": "2026-11-12T11", "quarter": 2}, noon) == 0
        assert fmt.next_quarter({"hour": "2026-11-12T12", "quarter": 0}, noon) == 1
        assert fmt.next_quarter({"hour": "2026-11-12T12", "quarter": 2}, noon) == 3

    def test_a_fast_hour_goes_round_again_without_reopening_the_show(self):
        late = datetime(2026, 11, 12, 12, 50)
        seq, q = [], 3
        for _ in range(6):
            q = fmt.next_quarter({"hour": "2026-11-12T12", "quarter": q}, late)
            seq.append(q)
        assert seq == [1, 2, 3, 1, 2, 3]

    def test_only_the_first_quarter_has_the_show_open(self):
        for s in fmt.SHOWS:
            assert s.clock[0][:2] == ("cold_open", "theme")
            assert all("theme" not in q for q in s.clock[1:])

    def test_schedule_marks_the_show_on_air(self):
        on = [s for s in fmt.schedule(datetime(2026, 11, 12, 15, 0)) if s["on_air"]]
        assert [s["key"] for s in on] == ["the_diff"]


class TestSegments:
    def test_fallbacks_exist_and_end_somewhere(self):
        for s in SEGMENTS.values():
            seen, cur = set(), s
            while cur.fallback:
                assert cur.fallback in SEGMENTS and cur.fallback not in seen
                seen.add(cur.fallback)
                cur = SEGMENTS[cur.fallback]

    def test_bits_rotate(self):
        assert all(b in SEGMENTS for b in BIT_ROTATION)
        assert len({resolve_bit(n) for n in range(len(BIT_ROTATION))}) == len(BIT_ROTATION)

    def test_story_filters(self):
        assert story_matches(segment("show_hn"), {"title": "Show HN: a thing"})
        assert not story_matches(segment("show_hn"), {"title": "A thing"})
        assert story_matches(segment("ask_hn"), {"title": "Ask HN: why?"})
        assert not story_matches(segment("two_hander"), {"title": "x", "discussed": False})
        assert story_matches(segment("headline"), {"title": "x"})

    def test_every_written_segment_has_a_worked_example(self):
        for s in SEGMENTS.values():
            if s.written:
                assert writers._examples().get(s.key), f"no example for {s.key}"


# ---------------------------------------------------------------------------
# The planner: the model chooses stories, never the shape
# ---------------------------------------------------------------------------


class TestAssign:
    def _items(self, hour=12, quarter=0):
        now = datetime(2026, 11, 12, hour, 5)
        return planner._slots_to_items(fmt.rundown(now, quarter), fmt.show_at(now), now, quarter)

    def test_the_shape_is_the_clock_whatever_the_picks_say(self):
        items = self._items()
        got = planner.assign(items, _stories(discussed=True), {99: (101, "x"), 0: (101, "not a story slot")})
        assert [i["segment"] for i in got] == [i["segment"] for i in items]

    def test_valid_picks_are_honoured_and_carry_their_angle(self):
        items = self._items()
        slot = next(i["n"] for i in items if i["segment"] == "headline")
        got = planner.assign(items, _stories(discussed=True), {slot: (105, "the number")})
        it = next(i for i in got if i["n"] == slot)
        assert it["story"] == 105 and it["angle"] == "the number" and it["title"] == "Story 5"

    def test_a_story_is_used_once(self):
        items = self._items()
        heads = [i["n"] for i in items if i["segment"] == "headline"]
        got = planner.assign(items, _stories(discussed=True), {heads[0]: (101, "a"), heads[1]: (101, "b")})
        stories = [i["story"] for i in got if i.get("story")]
        assert len(stories) == len(set(stories))

    def test_an_unqualified_pick_is_replaced_by_the_freshest_that_qualifies(self):
        items = self._items()
        th = next(i["n"] for i in items if i["segment"] == "two_hander")
        stories = _stories()
        stories[3]["discussed"] = True
        got = planner.assign(items, stories, {th: (101, "not discussed")})
        assert next(i for i in got if i["n"] == th)["story"] == 104

    def test_a_slot_nothing_qualifies_for_becomes_its_fallback(self):
        items = self._items(quarter=2)  # has a Show HN desk
        got = planner.assign(items, _stories(), {})
        assert "show_hn" not in [i["segment"] for i in got]
        assert len(got) == len(items)

    def test_with_no_stories_the_story_slots_go_and_the_rest_stays(self):
        got = planner.assign(self._items(), [], {})
        assert not any(i.get("story") for i in got)
        assert any(i["segment"] == "theme" for i in got)

    def test_the_last_quarter_of_a_shows_last_hour_ends_on_a_handoff(self):
        now = datetime(2026, 11, 12, 13, 50)  # Main Thread ends at 14
        items = planner._slots_to_items(fmt.rundown(now, 3), fmt.show_at(now), now, 3)
        assert items[-1]["segment"] == "handoff"
        assert items[-1]["speakers"] == ["sofia", "aria"] and items[-1]["next_show"] == "the_diff"
        mid = datetime(2026, 11, 12, 12, 50)
        assert planner._slots_to_items(fmt.rundown(mid, 3), fmt.show_at(mid), mid, 3)[-1]["segment"] == "ident"

    def test_used_stories_are_skipped_before_the_pool_is_counted(self, monkeypatch):
        from ..radio import sheets

        pool = [{"item_id": i, "title": f"S{i}", "age_hours": i} for i in range(1, 101)]
        monkeypatch.setattr(planner, "recent_stories", lambda limit=60, hours=48: pool[:limit])
        monkeypatch.setattr(sheets, "sheet_for", lambda iid: {
            "title": f"S{iid}", "kind": "story", "score": 1, "comments": 0,
            "sheet": {"what": "w", "callers": []}})
        got = planner.candidates(limit=5, exclude=set(range(1, 61)))
        assert [c["item_id"] for c in got] == [61, 62, 63, 64, 65]

    def test_plan_without_the_model_is_deterministic(self):
        now = datetime(2026, 11, 12, 12, 5)
        a = planner.plan(now, 0, stories=_stories(discussed=True), ask_model=False)
        b = planner.plan(now, 0, stories=_stories(discussed=True), ask_model=False)
        assert a["items"] == b["items"] and a["source"] == "fallback" and a["stories"] >= 3
        assert [i["n"] for i in a["items"]] == list(range(len(a["items"])))


# ---------------------------------------------------------------------------
# The writers' room: rules that cost nothing
# ---------------------------------------------------------------------------


class TestLint:
    seg = segment("headline")

    def _ok(self):
        return _copy("Eleven minutes is how long the ferry now takes to cross, since the operator moved to electric boats.",
                     "The batteries charge at each end while the cars drive off, so the boat never waits for a plug.",
                     "The operator says fares stay the same, and the thread would like to see that in a year or so.")

    def test_a_good_piece_passes(self):
        assert writers.lint(self.seg, self._ok(), ["mia"]) == []

    def test_reading_the_instructions_aloud_is_caught(self):
        notes = writers.lint(self.seg, _copy("The story is about a database. " * 8), ["mia"])
        assert any(n.startswith("You read your instructions") for n in notes)

    def test_banned_phrases_length_and_strangers(self):
        long = _copy(" ".join(["word"] * 200))
        assert any(n.startswith("Too long") for n in writers.lint(self.seg, long, ["mia"]))
        assert any(n.startswith("Too short") for n in writers.lint(self.seg, _copy("Short."), ["mia"]))
        assert any("deep dive" in n for n in writers.lint(self.seg, _copy("A deep dive. " * 12), ["mia"]))
        assert any(n.startswith("Only these speakers") for n in writers.lint(self.seg, self._ok(), ["leo"]))

    def test_two_items_may_not_open_the_same_way(self):
        notes = writers.lint(self.seg, self._ok(), ["mia"], earlier_openers=["eleven minutes is"])
        assert any("already opened" in n for n in notes)

    def test_a_phone_in_needs_a_caller(self):
        seg = segment("comment_line")
        c = _copy(*["The lines are open and nobody has called in yet this hour at all."] * 9)
        assert any(n.startswith("No caller speaks") for n in writers.lint(seg, c, ["mia", "caller1"]))

    def test_a_second_host_who_only_echoes_is_sent_back(self):
        seg = segment("two_hander")
        c = Copy(lines=[
            Line(speaker="aria", mood="default", text="Motorola promises seven years of security updates for the phone."),
            Line(speaker="leo", mood="default", text="Seven years promised."),
            Line(speaker="aria", mood="default", text="GrapheneOS has historically supported only Google Pixel phones."),
            Line(speaker="leo", mood="default", text="Historically, only Pixels."),
        ])
        assert any(n.startswith("The second speaker only repeats") for n in writers.lint(seg, c, ["aria", "leo"]))
        ok = Copy(lines=[
            Line(speaker="aria", mood="default", text="Motorola promises seven years of security updates for the phone."),
            Line(speaker="leo", mood="default", text="Has anyone ever collected on that?"),
        ])
        assert writers.echo_count(ok.lines) == 0

    def test_copying_the_example_is_caught_but_station_furniture_is_not(self):
        ex = writers._examples()["headline"][0]["lines"][1]["text"]
        assert writers.copied_from_examples("headline", ex) is not None
        assert writers.copied_from_examples("comment_line", "The lines are open. Line one.") is None
        assert writers.copied_from_examples("headline", "Something entirely different was said here today.") is None

    def test_the_examples_obey_the_stations_own_rules(self):
        """An example is what the writer imitates. One that breaks a rule
        teaches the rule's opposite."""
        for key, exs in writers._examples().items():
            if key == "version":
                continue
            seg = segment(key)
            for ex in exs:
                c = Copy(lines=[Line(**l) for l in ex["lines"]])
                speakers = list(dict.fromkeys(l.speaker for l in c.lines))  # in order of speaking
                notes = [n for n in writers.lint(seg, c, speakers)
                         if not n.startswith(("You reused the example", "Too short", "Too long"))]
                assert notes == [], f"{key}: {notes}"


class TestRepair:
    def test_recited_and_repeated_sentences_are_cut(self):
        lines = [{"speaker": "mia", "mood": "default",
                  "text": "A phone runs a new system. The hook: seven years of updates. A phone runs a new system. It ships in May."}]
        out = writers.repair(segment("headline"), lines)
        assert out[0]["text"] == "A phone runs a new system. It ships in May."

    def test_a_spelled_acronym_does_not_end_a_sentence(self):
        text = "One point is that L.L.M. inference cost varies. It ran on a G.P.U. The bill came later."
        assert writers._sentences(text) == [
            "One point is that L.L.M. inference cost varies.", "It ran on a G.P.U.", "The bill came later."]

    def test_notes_about_the_source_are_cut(self):
        lines = [{"speaker": "mia", "mood": "default",
                  "text": "Valkey is the fastest tested. The source does not establish who ran the benchmark."}]
        assert writers.repair(segment("headline"), lines)[0]["text"] == "Valkey is the fastest tested."

    def test_the_shows_tone_is_direction_not_copy(self):
        tone = "Afternoon. Opinionated, and fond of an argument in the comment section."
        lines = [{"speaker": "aria", "mood": "default",
                  "text": "The Diff is opinionated, and fond of an argument in the comment section. A phone now runs GrapheneOS."}]
        assert writers.repair(segment("headline"), lines, never=[tone])[0]["text"] == "A phone now runs GrapheneOS."

    def test_a_long_piece_loses_sentences_from_the_end(self):
        lines = [{"speaker": "mia", "mood": "default",
                  "text": " ".join(f"Sentence number {i} goes here now." for i in range(40))}]
        out = writers.repair(segment("headline"), lines)
        assert sum(len(l["text"].split()) for l in out) <= int(70 * writers.LENGTH_BAND[1])

    def test_a_dialogue_keeps_its_last_line(self):
        lines = [{"speaker": s, "mood": "default",
                  "text": f"Turn {n} one two three four five six seven eight nine. Turn {n} again two three four five."}
                 for n, s in enumerate(("aria", "leo") * 6)]
        lines[-1]["text"] = "The patch is nine days old."
        out = writers.repair(segment("two_hander"), lines)
        assert out[-1]["text"] == "The patch is nine days old."

    def test_a_sentence_lifted_from_the_worked_example_is_cut(self):
        """Asked to stop borrowing from the example, the model has handed
        the example back. The borrowed sentence is cut; the rest airs."""
        lines = [{"speaker": "mia", "mood": "default",
                  "text": "The phone costs a thousand dollars. The weekend was the easy part."}]
        out = writers.repair(segment("headline"), lines)
        assert out[0]["text"] == "The phone costs a thousand dollars."

    def test_a_sentence_that_describes_the_host_is_cut(self):
        from ..radio.cast import sheets

        lines = [{"speaker": "leo", "mood": "default",
                  "text": "The build failed twice. Leo has the shortest sentences on the station."}]
        out = writers.repair(segment("headline"), lines, never=sheets(["leo"]))
        assert out[0]["text"] == "The build failed twice."


class TestSchemas:
    def test_speakers_and_moods_are_closed_sets_in_the_response_schema(self):
        from ..content.llm_schemas import to_strict_schema

        schema = to_strict_schema(copy_schema(["mia", "caller1"]))
        line = schema["$defs"]["Line"]["properties"]
        assert line["speaker"]["enum"] == ["mia", "caller1"]
        assert "angry" in line["mood"]["enum"]
        assert list(schema["properties"]) == ["plan", "lines"]  # the plan is written first

    def test_the_pass_mark_is_applied_in_code(self):
        r = Review(heard="x", hook=5, clarity=5, faithful=5, speakable=5, voice=5)
        assert r.passes()
        assert not r.model_copy(update={"unsupported": ["a made-up number"]}).passes()
        assert not r.model_copy(update={"recited": ["the hook"]}).passes()
        assert not r.model_copy(update={"faithful": 3}).passes()
        assert not r.model_copy(update={"hook": 2}).passes()
        assert r.model_copy(update={"unsupported": ["x"]}).to_notes()[0].startswith("Not in the material")


class TestCopy:
    def test_numbers_symbols_and_acronyms(self):
        from ..radio.copy import speakable

        assert speakable("GPU prices rose 40% to $1,200") == \
            "G.P.U. prices rose forty percent to one thousand two hundred dollars"
        assert speakable("HNFM in 2026") == "H.N.F.M. in twenty twenty-six"
        assert speakable("16GB of RAM") == "sixteen gigabytes of RAM"

    def test_a_price_keeps_the_space_after_it(self):
        from ..radio.copy import speakable

        assert speakable("cost $2.11 one run") == "cost two point one one dollars one run"
        assert speakable("raised $3 million") == "raised three million dollars"
        assert speakable("$5k a month") == "five thousand dollars a month"

    def test_a_word_stuck_to_a_number_is_two_words(self):
        from ..radio.copy import speakable

        assert speakable("arm64 and Qwen3") == "arm sixty-four and Qwen three"

    def test_network_notation(self):
        from ..radio.copy import speakable

        assert speakable("a /48 IPv6 subnet") == "a slash forty-eight I.P. version six subnet"
        assert speakable("see docs/3 and 1/2") == "see docs slash three and one slash two"

    def test_lyrics_are_sung_in_words(self):
        from ..radio.copy import singable

        assert singable("[verse]\n32 cores roar\nAGPL-3.0 appears\n\n[chorus]\n9 times the pace") == \
            "[verse]\nthirty-two cores roar\nAGPL three point zero appears\n\n[chorus]\nnine times the pace"

    def test_ordinals(self):
        from ..radio.copy import speakable

        assert speakable("a 10th-century king") == "a tenth-century king"
        assert speakable("the 21st, the 3rd and the 30th") == "the twenty-first, the third and the thirtieth"

    def test_clock_times_read_like_a_host(self):
        from ..radio.copy import speakable, time_words

        assert speakable("It's 4:04 AM.") == "It's four oh four A.M."
        assert speakable("at 9:00") == "at nine o'clock"
        assert time_words(datetime(2026, 9, 13, 16, 5)) == "four oh five in the afternoon"


class TestSheets:
    def test_a_sheet_is_rendered_without_labels_worth_reading_out(self):
        from ..radio.sheets import render_story

        s = {"title": "T", "sheet": {"what": "A thing.", "hook": "A number.", "facts": ["One.", "Two."],
                                     "catch": "Unproven.", "callers": ["I doubt it.", "I ran it."]}}
        text = render_story(s)
        assert "hook" not in text.lower() and "catch" not in text.lower()
        assert "- A number." in text and "BUT: Unproven." in text
        assert "caller1: I doubt it." in render_story(s, with_callers=True)

    def test_callers_say_the_point_and_invented_ones_are_dropped(self):
        from ..radio.sheets import clean_callers

        assert clean_callers([
            "One commenter noted that the same task cost two dollars one run and one the next.",
            "A caller might ask if the panel is large enough.",
            "I ran this at work and it fell over on day two.",
        ]) == ["The same task cost two dollars one run and one the next.",
               "I ran this at work and it fell over on day two."]

    def test_a_caller_claims_experience_only_if_a_commenter_did(self):
        from ..radio.sheets import clean_callers

        said = ["I worked on the partnership with Motorola. It is a significant step for the platform."]
        assert clean_callers(said, quotes=["Looks weird with four lenses."]) == ["It is a significant step for the platform."]
        assert clean_callers(said, quotes=["I worked on one of these at Moto."]) == said

    def test_story_kinds(self):
        from ..radio.sheets import story_kind

        assert story_kind("Show HN: x") == "show_hn" and story_kind("Ask HN: y?") == "ask_hn"
        assert story_kind("Postgres 19") == "story"


# ---------------------------------------------------------------------------
# The booth's parts
# ---------------------------------------------------------------------------


class TestMix:
    def test_callers_go_down_the_phone_and_hosts_do_not(self):
        g = mix.join_graph(["studio", "phone", "studio"], [300, 420, 0])
        parts = g.split(";")
        assert "acrusher" not in parts[0] and "acrusher" in parts[1] and "acrusher" not in parts[2]
        assert "lowpass=f=3300" in parts[1] and "lowpass" not in parts[0]
        assert "apad=pad_dur=0.3" in parts[0] and "apad" not in parts[2]
        assert parts[-1].endswith("concat=n=3:v=0:a=1[out]")

    def test_the_bed_ducks_under_the_voice_and_everything_is_levelled(self):
        g = mix.over_bed_graph()
        assert "sidechaincompress" in g and "loudnorm=I=-16" in g and g.endswith("[out]")
        assert "adelay=1400|1400" in g
        assert "loudnorm=I=-16" in mix.plain_graph()

    def test_every_ffmpeg_call_refuses_stdin(self):
        """A worker's stdin is not a terminal; ffmpeg reading it has eaten
        input meant for something else."""
        import inspect

        src = inspect.getsource(mix)
        assert src.count('"ffmpeg", "-nostdin"') == src.count('["ffmpeg"')


class TestQA:
    def test_the_same_words_in_another_spelling_match(self):
        assert qa.match("The G.P.U. has 16GB.", "the gpu has sixteen gigabytes") == 1.0
        assert qa.match("It costs forty percent more.", "it costs 40% more") == 1.0

    def test_a_dropped_sentence_does_not(self):
        full = "GrapheneOS has only ever run on Pixels. Now it runs on a Motorola."
        assert qa.match(full, "graphene os has only ever run on pixels") < 0.8
        assert qa.match(full, "") == 0.0

    def test_levels_window(self):
        assert qa.levels_ok({"seconds": 20, "lufs": -16.5, "peak": -1.5})
        assert not qa.levels_ok({"seconds": 20, "lufs": -30.0, "peak": -12})
        assert not qa.levels_ok({"seconds": 0.4, "lufs": -16.0, "peak": -1})
        assert qa.levels_ok(None)

    def test_an_unreachable_recogniser_is_not_a_failure(self, monkeypatch):
        monkeypatch.setenv("ASR_BASE_URL", "")
        assert qa.round_trip("hello", b"RIFF") is None


class TestVoice:
    def test_callers_never_share_a_voice_with_a_host(self):
        from ..radio import voice

        hosts = {v[1] for v in voice.HOSTS.values()}
        assert not hosts & set(voice.CALLER_VOICES)
        assert voice.voice_name("caller1", seed=0) != voice.voice_name("caller2", seed=0)
        assert voice.voice_name("caller1", seed=0) != voice.voice_name("caller1", seed=1)

    def test_default_is_the_plain_voice(self, monkeypatch):
        from ..radio import voice

        monkeypatch.setattr(voice, "available_voices", lambda: ["Magpie-Multilingual.EN-US.Mia.Calm"])
        assert voice.voice_name("mia", "default") == "Magpie-Multilingual.EN-US.Mia"
        assert voice.voice_name("mia", "calm").endswith("Mia.Calm")
        assert voice.voice_name("mia", "happy") == "Magpie-Multilingual.EN-US.Mia"  # not served: plain

    def test_the_same_line_in_the_same_voice_has_one_file(self):
        from ..radio import voice

        a = voice.cache_path("v", "Hello there.")
        assert a == voice.cache_path("v", "Hello there.") and a != voice.cache_path("w", "Hello there.")


# ---------------------------------------------------------------------------
# The director
# ---------------------------------------------------------------------------


def _file(tmp_path, name="a.mp3"):
    p = tmp_path / name
    p.write_bytes(b"x" * 2000)
    return str(p)


class TestDirector:
    @pytest.fixture(autouse=True)
    def quiet(self, monkeypatch):
        self.asked = []
        monkeypatch.setattr(director, "request_plan", lambda *a, **k: self.asked.append(k) or {"status": "idle"})

    def _sheet(self, items, sheet_id="s1"):
        for n, it in enumerate(items):
            it.setdefault("n", n)
            it.setdefault("show", "main_thread")
        return repo.radio_save_sheet(sheet_id=sheet_id, title="t", minutes=15, items=items, source="test")

    def test_serves_what_was_made_in_order_and_skips_what_was_not(self, tmp_path):
        self._sheet([
            {"segment": "theme", "kind": "station_id", "status": "ready", "path": _file(tmp_path, "0.mp3"), "title": "Open"},
            {"segment": "headline", "kind": "brief", "status": "skipped", "reason": "no material"},
            {"segment": "headline", "kind": "brief", "status": "ready", "path": "/gone.mp3", "title": "Gone"},
            {"segment": "headline", "kind": "brief", "status": "ready", "path": _file(tmp_path, "3.mp3"),
             "title": "A story", "story": 77, "host": "leo"},
        ])
        first = director.next_item()
        assert first["title"] == "Open" and first["n"] == "0" and first["sheet_id"] == "s1"
        second = director.next_item()
        assert second["title"] == "A story" and second["ref"] == "story:77" and second["segment"] == "headline"

    def test_asks_for_the_next_block_when_this_one_runs_low(self, tmp_path):
        self._sheet([{"segment": "music", "kind": "music", "status": "ready", "path": _file(tmp_path)}])
        director.next_item()
        assert self.asked

    def test_with_no_block_it_plays_from_the_shelf_and_never_a_spoken_loop(self, monkeypatch):
        monkeypatch.setattr(director, "pick_from_bank",
                            lambda kind, **kw: {"id": f"{kind}1", "kind": kind, "path": "/m.mp3", "style": "x"})
        got = [director.next_item() for _ in range(8)]
        assert all(g.get("hold") for g in got)
        spoken = [g for g in got if g["kind"] != "music"]
        assert len(spoken) <= 2 and all(g["segment"] == "ident" for g in spoken)

    def test_an_empty_shelf_is_the_safety_file_or_quiet_never_a_missing_file(self, monkeypatch, tmp_path):
        monkeypatch.setattr(director, "pick_from_bank", lambda kind, **kw: None)
        import os

        def fake_silence(dst, seconds=15.0):
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            open(dst, "wb").write(b"x" * 2000)
            return True

        monkeypatch.setattr(mix, "silence", fake_silence)
        got = director.next_item()
        assert got.get("safety") is True and got["path"].endswith("quiet.mp3")
        assert os.path.exists(got["path"])

    def test_idle_repeats_an_evergreen_piece_from_an_earlier_block(self, tmp_path, monkeypatch):
        s = self._sheet([{"segment": "sponsor", "kind": "bit", "status": "ready", "path": _file(tmp_path),
                          "title": "A word from nobody"}], sheet_id="old")
        repo.radio_advance_sheet(s["sheet_id"])  # it has aired; the block is finished
        monkeypatch.setattr(director, "pick_from_bank",
                            lambda kind, **kw: {"id": f"{kind}1", "kind": kind, "path": "/m.mp3", "style": "x"})
        got = [director.next_item() for _ in range(4)]
        assert any(g.get("rerun") and g["segment"] == "sponsor" for g in got)

    def test_queue_jumps_the_line(self, monkeypatch):
        monkeypatch.setattr(director, "episode", lambda ref: {"ref": ref, "path": "/e/q.mp3", "title": "Queued",
                                                              "item_id": 5, "run": 1, "seg": 1})
        assert director.enqueue("5:1:1") == ["5:1:1"]
        item = director.next_item()
        assert item["queued"] is True and director.queue() == []

    def test_now_playing_carries_the_words(self, tmp_path):
        self._sheet([{"segment": "headline", "kind": "brief", "status": "ready", "path": _file(tmp_path),
                      "title": "A story", "story": 9, "name": "Headline",
                      "text": [{"speaker": "leo", "mood": "default", "text": "Somebody put Doom on a toothbrush."}]}])
        director.record_event({"title": "A story", "hnfm_kind": "brief", "hnfm_ref": "story:9",
                               "hnfm_sheet": "s1", "hnfm_n": "0", "hnfm_segment": "headline", "hnfm_host": "leo"})
        now = director.now_playing()
        assert now["segment"] == "headline" and now["item_id"] == 9
        assert now["text"][0]["text"].startswith("Somebody put Doom")

    def test_a_double_announcement_is_one_play(self):
        director.record_event({"title": "A", "hnfm_kind": "music", "hnfm_bank_id": "b9"})
        assert director.record_event({"title": "A", "hnfm_kind": "music", "hnfm_bank_id": "b9"}).get("ignored")
        assert director.record_event({"title": "x"}).get("ignored")  # not ours
        assert len(repo.radio_recent_events(hours=1)) == 1


class TestListenerAware:
    def _listeners(self, monkeypatch, n):
        monkeypatch.setattr(director, "icecast_status",
                            lambda timeout=5: {"up": True, "mounts": [{"listeners": n}]})
        director._LISTENERS.update(at=0.0, n=0)

    def test_nobody_listening_means_nothing_is_made(self, monkeypatch):
        monkeypatch.setenv("RADIO_PRODUCE", "listeners")
        self._listeners(monkeypatch, 0)
        assert director.should_produce() is False
        assert director.request_plan("sheet low") == {"status": "idle", "why": "nobody is listening"}

    def test_a_listener_wakes_the_producer_and_it_lingers_after_they_leave(self, monkeypatch):
        monkeypatch.setenv("RADIO_PRODUCE", "listeners")
        self._listeners(monkeypatch, 2)
        assert director.should_produce() is True
        self._listeners(monkeypatch, 0)
        assert director.audience()["present"] is True  # within the linger window

    def test_modes(self, monkeypatch):
        self._listeners(monkeypatch, 0)
        monkeypatch.setenv("RADIO_PRODUCE", "always")
        assert director.should_produce() is True
        monkeypatch.setenv("RADIO_PRODUCE", "off")
        assert director.should_produce() is False

    def test_a_person_asking_overrides_and_one_plan_is_in_flight(self, monkeypatch):
        self._listeners(monkeypatch, 0)
        monkeypatch.setenv("RADIO_PRODUCE", "off")
        sent = []

        class _T:
            def apply_async(self, kwargs):
                sent.append(kwargs)
                return type("R", (), {"id": "t1"})()

        monkeypatch.setattr("hnfm.web.tasks.radio_plan_block", _T())
        assert director.request_plan("manual", force=True)["status"] == "queued"
        monkeypatch.setenv("RADIO_PRODUCE", "always")
        assert director.request_plan("sheet low")["status"] == "already planning"
        assert len(sent) == 1

    def test_a_parked_block_counts_as_a_plan_in_flight(self, monkeypatch):
        monkeypatch.setenv("RADIO_PRODUCE", "always")
        repo.radio_save_sheet(sheet_id="park", title="t", minutes=15, source="llm", ready=False,
                              items=[{"n": 0, "segment": "headline", "kind": "brief", "story": 1}])
        assert director.request_plan("sheet low")["status"] == "already planning"
        assert all(sh["sheet_id"] != "park" for sh in repo.radio_open_sheets())
        repo.radio_mark_ready("park")
        assert any(sh["sheet_id"] == "park" for sh in repo.radio_open_sheets())

    def test_an_edition_for_the_archive_never_airs_and_its_stories_are_used(self, tmp_path):
        repo.radio_save_sheet(sheet_id="ed1", title="t", minutes=15, source="llm", ready=False, items=[
            {"n": 0, "segment": "headline", "kind": "brief", "story": 4242, "title": "Used", "status": "ready",
             "path": _file(tmp_path)}])
        repo.radio_update_sheet("ed1", cursor=1)
        repo.radio_mark_ready("ed1")
        assert repo.radio_current_sheet() is None
        ids, titles = director._used()
        assert 4242 in ids and "Used" in titles

    def test_the_edition_endpoint_checks_its_hour(self, monkeypatch):
        from fastapi.testclient import TestClient
        from ..web.api import app

        monkeypatch.setenv("RADIO_ENABLED", "true")
        c = TestClient(app)
        assert c.post("/api/radio/edition", json={}).status_code == 400
        assert c.post("/api/radio/edition", json={"hour": 25}).status_code == 400

    def test_editions_are_due_once_per_edition_hour(self, monkeypatch):
        from ..radio import housekeeping

        monkeypatch.setenv("RADIO_EDITION_HOURS", "8,13")
        monkeypatch.setattr(housekeeping, "station_now", lambda: datetime(2026, 11, 12, 8, 20))
        key = housekeeping.edition_due()
        assert key == "2026-11-12T08"
        housekeeping.mark_edition(key)
        assert housekeeping.edition_due() is None
        monkeypatch.setattr(housekeeping, "station_now", lambda: datetime(2026, 11, 12, 9, 0))
        assert housekeeping.edition_due() is None


class TestLibrary:
    def test_a_show_gets_its_own_stock_first(self, monkeypatch):
        from ..radio import library

        items = [{"id": "a", "kind": "music", "show": "cold_start", "created_at": "1"},
                 {"id": "b", "kind": "music", "show": "night_shift", "created_at": "2"}]
        monkeypatch.setattr(library, "load_bank", lambda: items)
        assert library.pick_from_bank("music", show="night_shift")["id"] == "b"
        assert library.pick_from_bank("music", show="the_diff")["id"] == "a"  # none of its own: anything

    def test_what_played_longest_ago_comes_round_first(self, monkeypatch):
        from ..radio import library

        items = [{"id": i, "kind": "music", "created_at": i} for i in "abc"]
        monkeypatch.setattr(library, "load_bank", lambda: items)
        assert library.pick_from_bank("music", avoid_ids=["a", "c", "b"])["id"] == "b"
        assert library.pick_from_bank("music", avoid_ids=["a"])["id"] == "b"
        assert library.pick_from_bank("music", avoid_ids=["a", "b", "c"], strict=True) is None

    def test_the_same_sentence_counts_as_played_whichever_take_it_is(self, monkeypatch):
        from ..radio import library

        monkeypatch.setattr(library, "load_bank", lambda: [
            {"id": "x", "kind": "station_id", "text": "You're listening", "created_at": "1"},
            {"id": "y", "kind": "station_id", "text": "You're listening", "created_at": "2"},
            {"id": "z", "kind": "station_id", "text": "Made by machines", "created_at": "3"},
        ])
        assert library.pick_from_bank("station_id", avoid_ids=["x"], strict=True)["id"] == "z"


class TestArchive:
    def test_the_feed_lists_editions_with_their_audio(self, monkeypatch):
        from ..radio import archive

        monkeypatch.setattr(archive, "editions", lambda limit=50: [{
            "id": "0800-cold_start-abc", "show_name": "Cold Start", "title": "Morning & more",
            "aired_at": "2026-11-12T08:00:00-05:00", "seconds": 600,
            "stories": [{"item_id": 1, "title": "A <b>story</b>"}]}])
        xml = archive.feed("https://hnfm.lan")
        assert "https://hnfm.lan/api/radio/archive/0800-cold_start-abc.mp3" in xml
        assert "Morning &amp; more" in xml and "&lt;b&gt;" in xml and "<itunes:duration>600<" in xml

    def test_a_block_with_almost_nothing_spoken_is_not_archived(self, tmp_path):
        from ..radio import archive

        sheet = {"sheet_id": "s", "title": "t", "items": [
            {"n": 0, "segment": "music", "kind": "music", "show": "main_thread", "status": "ready",
             "path": _file(tmp_path)}]}
        assert archive.render(sheet) is None


# ---------------------------------------------------------------------------
# The switch
# ---------------------------------------------------------------------------


class TestSwitch:
    def test_api_is_404_when_off(self, monkeypatch):
        from fastapi.testclient import TestClient
        from ..web.api import app

        monkeypatch.setenv("RADIO_ENABLED", "false")
        c = TestClient(app)
        assert c.get("/api/radio/status").json() == {"enabled": False}
        for path in ("/api/radio/next", "/api/radio/script", "/api/radio/schedule", "/api/radio/archive"):
            assert c.get(path).status_code == 404

    def test_the_station_answers_when_on(self, monkeypatch):
        from fastapi.testclient import TestClient
        from ..web.api import app

        monkeypatch.setenv("RADIO_ENABLED", "true")
        c = TestClient(app)
        body = c.get("/api/radio/script").text
        assert "output.icecast" in body and "/api/radio/next" in body and "hnfm_n" in body
        sched = c.get("/api/radio/schedule").json()
        assert len(sched["shows"]) == 6 and sched["on_air"]["name"] and sched["clock"]
        assert c.get("/api/radio/archive").json() == {"editions": []}
        assert c.get("/api/radio/archive/feed.xml").text.startswith("<?xml")
        snap = c.get("/api/radio/studio").json()
        assert "log" in snap and "sheet_items" in snap and "show" in snap and "produce" in snap

    def test_beat_leaves_no_entry_when_off(self, monkeypatch):
        from .. import schedule as sched

        monkeypatch.delenv("RADIO_ENABLED", raising=False)
        cfg = {"enabled": True, "jobs": {
            "radio-monitor": {"task": "x", "every": "5m", "requires_env": "RADIO_ENABLED"},
            "fetch-new": {"task": "y", "every": "10m"},
        }}
        assert list(sched.beat_schedule(cfg)) == ["fetch-new"]
        monkeypatch.setenv("RADIO_ENABLED", "true")
        assert sorted(sched.beat_schedule(cfg)) == ["fetch-new", "radio-monitor"]

    def test_services_page_lists_the_radio_only_when_on(self, monkeypatch):
        from ..utils import service_registry as reg

        monkeypatch.setenv("RADIO_ENABLED", "false")
        assert not [s for s in reg.get_service_specs() if s.role == "Radio"]
        monkeypatch.setenv("RADIO_ENABLED", "true")
        assert len([s for s in reg.get_service_specs() if s.role == "Radio"]) == 2

    def test_the_station_narrates(self):
        from .. import radio

        radio.log("dj", "asked what's next")
        radio.log("director", "served item 1/3: theme — hi", kind="station_id")
        tail = repo.radio_log_tail(limit=10)
        assert [t["component"] for t in tail[-2:]] == ["dj", "director"]
        assert tail[-1]["meta"] == {"kind": "station_id"}


class TestSoundDesign:
    """Issue #40: effects and treatments are code, and the model never
    chooses them."""

    def test_every_effect_is_a_command_ffmpeg_can_be_given(self):
        from ..radio import fx

        for e in fx.EFFECTS.values():
            cmd = fx.effect_command(e, "/tmp/x.wav")
            assert cmd[:2] == ["ffmpeg", "-nostdin"] and "lavfi" in cmd and cmd[-1] == "/tmp/x.wav"
            assert 0.1 <= e.seconds <= 3 and e.what

    def test_an_unknown_role_is_treated_as_the_studio(self):
        from ..radio import fx

        assert fx.treatment("nowhere") == fx.treatment("studio")
        assert "atempo=1.32" in fx.treatment("fineprint")

    def test_an_effect_clip_is_left_as_it_is(self):
        g = mix.join_graph(["fx", "big"], [140, 0]).split(";")
        assert "acompressor" not in g[0] and "aecho" in g[1]

    def test_a_phone_in_rings_once_and_hangs_up_after_the_last_caller(self):
        from ..radio import booth

        lines = [{"speaker": s, "mood": "default", "text": "x"}
                 for s in ("sofia", "caller1", "sofia", "caller2", "sofia")]
        steps = booth.layout(lines, segment("comment_line"))
        names = [s[1] for s in steps if s[0] == "fx"]
        assert names == ["ring", "pickup", "hangup"]
        assert steps.index(("fx", "ring")) < steps.index(("line", 1, "phone"))
        assert steps.index(("fx", "hangup")) == steps.index(("line", 3, "phone")) + 1

    def test_a_correspondent_arrives_and_leaves_through_static(self):
        from ..radio import booth

        lines = [{"speaker": s, "mood": "default", "text": "x"} for s in ("sofia", "sam", "sam", "sofia")]
        steps = booth.layout(lines, segment("correspondent"))
        assert steps == [("line", 0, "studio"), ("fx", "static"), ("line", 1, "field"), ("line", 2, "field"),
                         ("fx", "static"), ("line", 3, "studio")]

    def test_the_bulletin_opens_on_the_pips_and_ticks_between_stories(self):
        from ..radio import booth

        lines = [{"speaker": "mia", "mood": "default", "text": "x"}] * 3
        steps = booth.layout(lines, segment("bulletin"))
        assert [s[1] for s in steps if s[0] == "fx"] == ["pips", "tick", "tick"]

    def test_the_chart_rolls_into_number_one_and_ends_on_an_impact(self):
        from ..radio import booth

        lines = [{"speaker": "ray", "mood": "default", "text": "x"}] * 6
        fx_names = [s[1] for s in booth.layout(lines, segment("chart")) if s[0] == "fx"]
        assert fx_names == ["blip"] * 4 + ["roll", "impact"]

    def test_the_last_line_of_an_advert_is_fine_print(self):
        from ..radio import booth

        lines = [{"speaker": "mia", "mood": "default", "text": "x"}] * 3
        assert booth.layout(lines, segment("sponsor"))[-1] == ("line", 2, "fineprint")

    def test_the_thread_swears_and_the_station_bleeps(self):
        from ..radio.copy import bleeped

        assert bleeped("Holy shit. I never drank again.") == "Holy bleep. I never drank again."
        assert bleeped("A shitty, fucking mess") == "A bleep, bleep mess"
        assert bleeped("The shiitake and the Dickens novel") == "The shiitake and the Dickens novel"


class TestCast:
    """Issue #41."""

    def test_every_show_is_staffed_from_the_cast(self):
        from ..radio import cast

        for s in fmt.SHOWS:
            for h in (s.anchor, s.cohost, *s.cast):
                assert cast.CAST[h].role == "host"

    def test_no_two_characters_share_a_voice_and_callers_share_none(self):
        from ..radio import cast

        voices = [c.voice for c in cast.CAST.values() if c.key != "announcer"]
        assert len(voices) == len(set(voices))
        assert not set(voices) & set(cast.CALLER_VOICES)

    def test_any_three_callers_in_a_row_are_three_people(self):
        from ..radio import cast

        people = [v.rsplit(".", 1)[-1] for v in cast.CALLER_VOICES]
        n = len(people)
        for i in range(n):
            assert len({people[i], people[(i + 1) % n], people[(i + 2) % n]}) == 3

    def test_a_mood_the_voice_does_not_have_is_the_plain_voice(self):
        from ..radio import cast, voice

        assert cast.mood_or_default("jason", "happy") == "happy"
        assert cast.mood_or_default("mia", "happy") == "default"
        assert cast.mood_or_default("caller2", "angry") == "default"
        assert voice.voice_name("mia", "happy").endswith("EN-US.Mia")

    def test_where_a_voice_is_treated_follows_from_who_it_is(self):
        from ..radio import cast

        assert [cast.role_of(s) for s in ("mia", "caller1", "sam", "announcer")] == \
            ["studio", "phone", "field", "big"]

    def test_the_writer_is_told_only_about_the_people_in_the_piece(self):
        from ..radio import cast

        b = cast.briefing(["sofia", "sam"])
        assert "sofia:" in b and "sam:" in b and "mia:" not in b
        assert "fearful" in b and 'Called "Sam" on air' in b

    def test_a_correspondent_piece_is_opened_by_the_host(self):
        seg = segment("correspondent")
        ok = [("sofia", "A town of forty thousand runs every one of its buses from a spreadsheet."),
              ("sam", "Eleven tabs, and one person who understands tab nine of them all."),
              ("sam", "A vendor wanted two million dollars. The town said no and kept it."),
              ("sam", "That person retires in the spring, which is the whole problem here.")]
        c = Copy(lines=[Line(speaker=s, text=t) for s, t in ok])
        notes = [n for n in writers.lint(seg, c, ["sofia", "sam"]) if not n.startswith(("Too", "You reused"))]
        assert notes == []
        c.lines = c.lines[1:]
        assert any(n.startswith("The host opens") for n in writers.lint(seg, c, ["sofia", "sam"]))

    def test_the_station_adds_the_handover_and_the_thanks(self):
        L = lambda s, t: {"speaker": s, "mood": "default", "text": t}  # noqa: E731
        lines = [L("sofia", "A town runs its buses from a spreadsheet."), L("sam", "Eleven tabs."),
                 L("sofia", "Fifty-three incidents were found."), L("sofia", "So what is the risk?"),
                 L("sam", "The person who knows it retires."), L("sofia", "Thanks, Sam.")]
        out = writers.dress_correspondent(lines, "sofia", "sam", seed=1)
        assert out[0]["text"] == "A town runs its buses from a spreadsheet. Sam is on the line."
        assert [l["speaker"] for l in out] == ["sofia", "sam", "sofia", "sam", "sofia"]
        assert out[2]["text"] == "So what is the risk?" and out[-1]["text"] == "Sam, thank you."
        # A piece that is not shaped like a report is left alone.
        assert writers.dress_correspondent(lines[1:2], "sofia", "sam") == lines[1:2]


class TestNewSegments:
    """Issue #42."""

    def test_the_first_quarter_opens_cold_and_every_clock_names_real_segments(self):
        from ..radio.segments import SEGMENTS

        for s in fmt.SHOWS:
            assert s.clock[0][0] == "cold_open"
            for q in s.clock:
                assert all(k == "bit" or k in SEGMENTS for k in q)

    def test_the_chart_counts_down_from_five(self, monkeypatch):
        from ..db import repo
        from ..radio import material

        rows = [{"item_id": n, "title": f"Story {n}", "points": 900 - n * 100, "comments": n} for n in range(1, 6)]
        monkeypatch.setattr(repo, "radio_chart", lambda limit=5, hours=24: rows)
        out = material.chart().splitlines()
        assert out[1].startswith("- Number 5:") and out[-1].startswith('- Number 1: "Story 1" with 800 points')
        monkeypatch.setattr(repo, "radio_chart", lambda limit=5, hours=24: rows[:3])
        assert material.chart() is None

    def test_the_cold_open_is_cut_from_the_block_and_needs_two_pieces(self, monkeypatch):
        from ..radio import booth, production

        said = {}
        monkeypatch.setattr(production, "_bed", lambda *a, **k: None)
        monkeypatch.setattr(booth, "record", lambda lines, seg, out, **k: said.update(lines=lines, seg=seg.key)
                            or {"path": out, "seconds": 20.0, "qa": {"match": 1.0}})
        sh = fmt.show("cold_start")
        cold = {"n": 0, "segment": "cold_open", "kind": "station_id", "show": sh.key}
        piece = lambda n, who, text, seg="headline": {  # noqa: E731
            "n": n, "segment": seg, "status": "ready", "story": 100 + n,
            "text": [{"speaker": who, "mood": "default", "text": text}]}
        items = [cold, piece(1, "sofia", "Eleven tabs run every bus in town. Nobody planned it."),
                 piece(2, "mia", "The bulletin line does not count here at all.", "bulletin"),
                 piece(3, "leo", "A font made of nothing but circles. It is legible, somehow.")]
        assert production._cold_open(cold, items, sh, "/tmp", []) is True
        assert [l["speaker"] for l in said["lines"]] == ["mia", "sofia", "leo"]
        assert said["lines"][0]["text"] == "Coming up on Cold Start."
        assert said["lines"][1]["text"] == "Eleven tabs run every bus in town."
        assert cold["status"] == "ready" and said["seg"] == "cold_open"
        assert production._cold_open({"n": 0, "segment": "cold_open"}, items[:2], sh, "/tmp", []) is False


class TestEditions:
    """Issue #43: an edition stands on its own."""

    def _edition(self, tmp_path, monkeypatch):
        import json

        from ..radio import archive

        monkeypatch.setenv("OUTPUTS_DIR", str(tmp_path))
        day = tmp_path / "radio" / "archive" / "2026-11-12"
        day.mkdir(parents=True)
        meta = {"id": "0800-cold_start-abc", "show": "cold_start", "show_name": "Cold Start", "title": "Thursday",
                "date": "2026-11-12", "seconds": 60.0, "rundown": [
                    {"at": 0.0, "seconds": 8.0, "segment": "sweeper", "title": "Cold Start. On H.N.F.M."},
                    {"at": 8.0, "seconds": 30.0, "segment": "headline", "title": "Eleven tabs",
                     "text": [{"speaker": "sofia", "mood": "default", "text": "Eleven tabs run the buses."},
                              {"speaker": "sofia", "mood": "default", "text": "One person understands tab nine."}],
                     "cues": [{"n": 0, "at": 1.4, "seconds": 3.0}, {"n": 1, "at": 4.7, "seconds": 3.5}]},
                    {"at": 38.0, "seconds": 22.0, "segment": "track", "title": "slow jazz"}]}
        (day / "0800-cold_start-abc.json").write_text(json.dumps(meta))
        (day / "0800-cold_start-abc.mp3").write_bytes(b"x" * 2000)
        return archive

    def test_chapters_are_the_spoken_items_at_the_second_they_start(self, tmp_path, monkeypatch):
        archive = self._edition(tmp_path, monkeypatch)
        assert archive.chapters("0800-cold_start-abc") == {
            "version": "1.2.0", "chapters": [{"startTime": 8, "title": "Eleven tabs"}]}
        assert archive.chapters("nope") is None

    def test_the_transcript_names_who_spoke_and_when(self, tmp_path, monkeypatch):
        archive = self._edition(tmp_path, monkeypatch)
        t = archive.transcript("0800-cold_start-abc")
        assert "[0:08] Eleven tabs" in t and "SOFIA: Eleven tabs run the buses." in t and "slow jazz" not in t

    def test_an_edition_can_be_featured_renamed_and_removed(self, tmp_path, monkeypatch):
        archive = self._edition(tmp_path, monkeypatch)
        e = archive.update("0800-cold_start-abc", featured=True, title="The spreadsheet one")
        assert e["featured"] is True and e["title"] == "The spreadsheet one" and "rundown" not in e
        assert archive.editions()[0]["featured"] is True
        assert archive.remove("0800-cold_start-abc") is True
        assert archive.editions() == [] and archive.remove("0800-cold_start-abc") is False

    def test_the_feed_carries_art_and_chapters(self, tmp_path, monkeypatch):
        archive = self._edition(tmp_path, monkeypatch)
        xml = archive.feed("https://hnfm.lan")
        assert "/api/radio/art/cold_start.jpg" in xml and "/0800-cold_start-abc/chapters.json" in xml

    def test_captions_follow_the_recorded_timing(self, tmp_path, monkeypatch):
        from ..radio import video

        archive = self._edition(tmp_path, monkeypatch)
        ass = video.subtitles(archive.edition("0800-cold_start-abc"))
        # Line one starts 1.4 s into an item that starts at 8 s, and holds until line two.
        assert "Dialogue: 0,0:00:09.40,0:00:12.70,Words,,0,0,0,,{\\c&H006AFF&\\fs20\\b1}SOFIA{\\r}\\NEleven tabs" in ass
        assert "Dialogue: 0,0:00:38.00,0:01:00.00,Chapter" in ass and "♪  slow jazz" in ass

    def test_an_edition_made_before_timing_was_recorded_still_gets_captions(self, tmp_path, monkeypatch):
        from ..radio import video

        archive = self._edition(tmp_path, monkeypatch)
        e = archive.edition("0800-cold_start-abc")
        e["rundown"][1].pop("cues")
        assert video.subtitles(e).count(",Words,") == 2

    def test_the_booth_knows_when_each_line_starts(self, tmp_path):
        import wave

        from ..radio import booth

        def wav(name, seconds):
            p = str(tmp_path / name)
            with wave.open(p, "wb") as w:
                w.setnchannels(1); w.setsampwidth(2); w.setframerate(8000)  # noqa: E702
                w.writeframes(b"\0\0" * int(8000 * seconds))
            return p

        clips = [(wav("fx.wav", 1.0), "fx", 140), (wav("a.wav", 2.0), "studio", 300),
                 (wav("b.wav", 1.32), "fineprint", 0)]
        assert booth.cues(clips, {1: 0, 2: 1}, lead=1.4) == [
            {"n": 0, "at": 2.54, "seconds": 2.0}, {"n": 1, "at": 4.84, "seconds": 1.0}]


class TestDeskSettings:
    """Issue #44: production is switched at the desk, not by a deploy."""

    def test_the_desk_overrides_the_environment(self, monkeypatch):
        from ..db import repo
        from ..radio import director, housekeeping

        monkeypatch.setenv("RADIO_PRODUCE", "listeners")
        monkeypatch.setenv("RADIO_EDITION_HOURS", "8,13,19")
        store = {}
        monkeypatch.setattr(repo, "get_setting", lambda k, d=None: store.get(k, d))
        monkeypatch.setattr(repo, "set_setting", lambda k, v: store.__setitem__(k, v))
        assert director.produce_mode() == "listeners" and housekeeping.edition_hours() == [8, 13, 19]
        director.set_produce_mode("off")
        assert director.produce_mode() == "off" and director.should_produce() is False
        assert housekeeping.set_edition_hours([]) == []          # none is a choice, not "use the default"
        assert housekeeping.set_edition_hours(["7", 25, "x", 7, 18]) == [7, 18]
        with pytest.raises(ValueError):
            director.set_produce_mode("sometimes")

    def test_a_database_that_is_away_falls_back_to_the_environment(self, monkeypatch):
        from ..db import repo
        from ..radio import director

        def away(*a, **k):
            raise RuntimeError("no database")

        monkeypatch.setattr(repo, "get_setting", away)
        monkeypatch.setenv("RADIO_PRODUCE", "always")
        assert director.produce_mode() == "always"
