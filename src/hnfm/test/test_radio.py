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
            assert s.clock[0][0] == "theme"
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
                speakers = sorted({l.speaker for l in c.lines})
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
        lines[-1]["text"] = "The post is four days old."
        out = writers.repair(segment("two_hander"), lines)
        assert out[-1]["text"] == "The post is four days old."


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
        assert "highpass" not in parts[0] and "highpass" in parts[1] and "highpass" not in parts[2]
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
