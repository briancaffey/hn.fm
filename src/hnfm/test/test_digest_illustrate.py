"""The art director and where its pictures land."""

import random
from types import SimpleNamespace

from hnfm.content.llm_schemas import ArtDirection
from hnfm.digest import illustrate
from hnfm.digest.compose import Section
from hnfm.digest.render import _section_body


def _story():
    return SimpleNamespace(item_id=1, title="A bakery replaces its ovens with a kiln",
                           brief={"thesis": "An old kiln bakes better bread."}, url=None, hn_url=None)


class TestDirect:
    def test_a_direction_becomes_a_style_and_a_subject(self, monkeypatch):
        seen = {}

        class _Svc:
            def __init__(self, task):
                seen["task"] = task

            def generate_structured(self, prompt, schema):
                seen["prompt"] = prompt
                return ArtDirection(subject="A baker sliding a loaf into a brick kiln.",
                                    treatment="Linocut, hard shadow",
                                    prompt="Linocut print of a baker sliding a loaf into a brick kiln, "
                                           "seen from inside the oven, black ink on white paper, no colour",
                                    steps=50, cfg=1.0)
        monkeypatch.setattr("hnfm.content.llm_service.LLMService", _Svc)
        out = illustrate.direct(_story(), illustrate.REGISTERS[1], ["woodcut", "brass"], random.Random(1))
        assert out is not None
        style, subject = out
        assert seen["task"] == "image.direct"
        assert subject == "a baker sliding a loaf into a brick kiln"
        assert style.label == "Linocut, hard shadow" and style.technique == "art-directed"
        assert style.build(subject, "x").startswith("Linocut print")
        assert (style.steps, style.cfg) == (36, 3.0)  # clamped

    def test_a_prompt_without_the_paper_line_gets_one(self, monkeypatch):
        class _Svc:
            def __init__(self, task): pass
            def generate_structured(self, prompt, schema):
                return ArtDirection(subject="A kiln", treatment="Etching",
                                    prompt="Fine etching of a brick kiln at night with a long shadow on cobbles")
        monkeypatch.setattr("hnfm.content.llm_service.LLMService", _Svc)
        style, _ = illustrate.direct(_story(), None, [], random.Random(1))
        assert style.build("", "").endswith("no colour.")

    def test_model_down_means_none_not_an_error(self, monkeypatch):
        class _Svc:
            def __init__(self, task): pass
            def generate_structured(self, prompt, schema):
                raise RuntimeError("connection error")
        monkeypatch.setattr("hnfm.content.llm_service.LLMService", _Svc)
        assert illustrate.direct(_story(), None, [], random.Random(1)) is None

    def test_off_switch(self, monkeypatch):
        monkeypatch.setenv("DIGEST_ART_DIRECTOR", "false")
        assert illustrate.directed() is False


class TestPunchlinePictures:
    def test_html_punchline_carries_its_picture_under_the_title(self):
        illo = SimpleNamespace(data_uri="data:image/jpeg;base64,AAA", ink=0.1, seconds=1.0, prompt="p",
                               style=SimpleNamespace(label="Linocut", technique="art-directed"))
        sec = Section(kind="punchline", title="Kiln bread", body="one\ntwo", story_id=1)
        html = _section_body(sec, [illo])
        assert html.index("<h2>") < html.index("<figure>") < html.index("<ul>")
