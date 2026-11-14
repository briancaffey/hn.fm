"""Regression tests for the issues found while writing docs/HOW-IT-WORKS.md
(GitHub #53-#60). Each test names its issue."""

import os
import time


def test_53_orphans_are_requeued_into_triage(monkeypatch):
    from hnfm.web import tasks

    queued = []
    monkeypatch.setattr(tasks, "orphan_ids", lambda limit: [11, 12])
    monkeypatch.setattr(tasks.process_hn_item_run, "apply_async",
                        lambda args, kwargs: queued.append((args, kwargs)))
    assert tasks._rescue_orphans(10) == 2
    assert queued[0] == ([11, None, False], {"continue_to_triage": True})


def test_55_narrated_digests_are_listed_for_the_feed(monkeypatch, tmp_path):
    from hnfm.web import api

    d = tmp_path / "digests"
    d.mkdir()
    (d / "hnfm-digest-2026-11-14.mp3").write_bytes(b"x" * 10)
    (d / "hnfm-digest-2026-11-14.html").write_text("<html/>")
    monkeypatch.setenv("OUTPUTS_ROOT", str(tmp_path))
    eps = api.digest_episodes()
    assert [e["slug"] for e in eps] == ["hnfm-digest-2026-11-14"]
    assert eps[0]["bytes"] == 10


def test_56_the_bank_is_not_stocked_when_production_is_off(monkeypatch):
    from hnfm import radio
    from hnfm.radio import bank, director
    from hnfm.web import tasks

    monkeypatch.setattr(radio, "enabled", lambda: True)
    monkeypatch.setattr(director, "produce_mode", lambda: "off")
    monkeypatch.setattr(bank, "fill", lambda **k: (_ for _ in ()).throw(AssertionError("filled")))
    assert tasks.radio_fill_bank.run()["reason"] == "radio production is off"


def test_57_paragraphs_survive_cleaning():
    from hnfm.utils.run_utils import clean_content

    assert clean_content("A  b.\n\n\nC\td.") == "A b.\n\nC d."


def test_58_a_blind_vision_model_is_skipped_not_failed(monkeypatch):
    from hnfm.content import source_image_analysis as sia

    monkeypatch.setattr(sia, "_blind_until", 0.0)
    assert sia.vision_available()
    assert sia._note_blind("400 - nemotron-lightning is not a multimodal model")
    assert not sia.vision_available()
    assert not sia._note_blind("connection reset")


def test_60_the_brief_reaches_the_script_prompt():
    from hnfm.utils.segment_utils import brief_text

    b = {"angle": "AI lowers the bar for sabotage", "stakes": "grid operators",
         "numbers": [{"value": "66 minutes", "spoken": "sixty-six minutes", "of": "time to shut it down"}]}
    t = brief_text(b)
    assert "Angle: AI lowers the bar" in t and 'say "sixty-six minutes"' in t
    assert brief_text(None) == "(none)"


def test_61_media_files_into_the_story_collection_and_falls_back(monkeypatch):
    from hnfm import club

    monkeypatch.setenv("INFERENCE_CLUB_ENABLED", "true")
    monkeypatch.setenv("INFERENCE_CLUB_BASE_URL", "http://club")
    monkeypatch.setenv("INFERENCE_CLUB_API_KEY", "k")
    monkeypatch.setattr(club, "_down_until", 0.0)
    sent = {}

    class R:
        status_code = 200
        headers = {"content-type": "application/json"}

        def json(self):
            return {"data": [{"b64_json": "aW1n"}]}

    def post(url, json, headers, timeout):
        sent.update(url=url, body=json, headers=headers)
        return R()

    monkeypatch.setattr(club.requests, "post", post)
    with club.filing(42):
        assert club.image("a cat", 1280, 720) == "aW1n"
    assert sent["url"] == "http://club/v1/images/generations"
    assert sent["body"]["collection"] == "hn.fm/story-42" and sent["body"]["visibility"] == "PRIVATE"
    assert club.collection() == "hn.fm"

    class Bad(R):
        status_code = 503
        text = "down"

    monkeypatch.setattr(club.requests, "post", lambda *a, **k: Bad())
    try:
        club.image("a cat", 1280, 720)
        raise AssertionError("expected ClubError")
    except club.ClubError:
        pass
    assert not club.usable()  # cools down instead of timing out on every image
