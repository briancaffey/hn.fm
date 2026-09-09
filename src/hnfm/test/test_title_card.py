"""The title card (plans/19): credits derived from the trail, a tagline that
speaks as the episode, and markup that sizes itself to the frame."""

from unittest import mock

from ..video import title_card as tc


class TestCredits:
    def test_sample_lists_the_whole_stack(self, monkeypatch):
        monkeypatch.setenv("TTS_BACKEND", "magpie")
        monkeypatch.setenv("IMAGE_GENERATION_BACKEND", "NIM")
        names = [(c["vendor"], c["products"]) for c in tc.credits_for()]
        assert names == [
            ("nvidia", ["Nemotron 3", "Magpie TTS"]),
            ("bfl", ["FLUX.2"]),
            ("lightricks", ["LTX-2"]),
            ("hyperframes", ["kinetic text"]),
        ]

    def test_dia_voice_credits_nari(self, monkeypatch):
        monkeypatch.setenv("TTS_BACKEND", "dia")
        by = {c["vendor"]: c["products"] for c in tc.credits_for()}
        assert by["nari"] == ["Dia"] and by["nvidia"] == ["Nemotron 3"]

    def test_a_story_without_motion_or_kinetic_text_omits_them(self, monkeypatch):
        monkeypatch.setenv("TTS_BACKEND", "magpie")
        with mock.patch("hnfm.db.steps.list_steps", return_value=[
                {"status": "ok", "model": "nvidia/nemotron-3-nano-omni"}]), \
                mock.patch("hnfm.utils.segment_utils.list_segment_images", return_value=[1]), \
                mock.patch("hnfm.utils.segment_utils.get_segment_image",
                           return_value=mock.Mock(video_clip_path=None)), \
                mock.patch("hnfm.utils.segment_utils.get_segment",
                           return_value=mock.Mock(meta_plan=[{"template": "image_sequence"}])):
            vendors = [c["vendor"] for c in tc.credits_for(1, 1, 1)]
        assert vendors == ["nvidia", "bfl"]


class TestTagline:
    def test_strips_reviewer_framing(self):
        assert tc._deframe("The article announces a complete wiring diagram.") == \
            "A complete wiring diagram."
        assert tc._deframe("Bare claim stays.") == "Bare claim stays."

    def test_thesis_wins_and_long_text_falls_back_to_first_sentence(self):
        long = "First sentence here. " + "x" * 200
        with mock.patch("hnfm.db.repo.get_latest_story_brief",
                        return_value={"brief": {"thesis": long}}), \
                mock.patch("hnfm.utils.run_utils.get_run", return_value=None):
            assert tc.tagline_for(1, 1) == "First sentence here"


class TestMarkup:
    def test_sized_to_the_frame_with_every_part(self):
        html = tc.build_html("9:16", 720, 1280, tagline="A tag & line",
                             credits=tc.credits_for(), presenter="brian")
        assert "width: 720px; height: 1280px" in html
        assert html.count('<span style="background:#') == 5      # the squares
        assert ">HNFM</text>" in html
        assert "Presented by <b>brian</b>" in html
        assert "A tag &amp; line" in html
        assert "Black Forest Labs" in html and "Nemotron 3" in html

    def test_logo_override_is_inlined(self, tmp_path, monkeypatch):
        monkeypatch.setattr(tc, "LOGO_DIR", tmp_path)
        (tmp_path / "nvidia.svg").write_text("<svg xmlns='http://www.w3.org/2000/svg'/>")
        html = tc.build_html("16:9", 1280, 720, credits=tc.credits_for())
        assert 'src="data:image/svg+xml;base64,' in html
        assert html.count('class="mark tile"') == 3               # the other three

    def test_card_path_is_per_format(self):
        p = tc.card_path_for("/o", 5, 2, 1, "9:16")
        assert p.endswith("/hn/item/5/runs/2/segments/1/title/title_9x16.png")
