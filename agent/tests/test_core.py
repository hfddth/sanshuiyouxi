from agent import is_confirm, make_greeting
from rag import list_available_spots, retrieve


def test_knowledge_base_is_available():
    spots = list_available_spots()
    assert len(spots) >= 4
    assert retrieve(spots[0], k=1)


def test_greeting_options_match_numbered_choices():
    greeting, options = make_greeting()
    assert options
    for index, option in enumerate(options, 1):
        assert f"{index}. {option}" in greeting


def test_confirm_requires_an_exact_confirmation():
    assert is_confirm("确认！")
    assert is_confirm("OK")
    assert not is_confirm("我还没有确认")
