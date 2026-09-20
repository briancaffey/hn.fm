"""The reasoning that LM Studio leaves in front of the answer."""

from hnfm.content.llm_service import _strip_reasoning


def test_reasoning_before_a_bare_closing_tag_is_dropped():
    assert _strip_reasoning('The user asks for one word. So: Paris.\n</think>\nParis') == "Paris"


def test_json_after_the_tag_survives():
    assert _strip_reasoning('thinking...\n</think>\n{"a": 1}') == '{"a": 1}'


def test_a_plain_answer_is_untouched():
    assert _strip_reasoning("Paris") == "Paris"
    assert _strip_reasoning(None) is None
