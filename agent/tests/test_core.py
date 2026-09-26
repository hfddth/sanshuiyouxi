from pathlib import Path

from agent import is_confirm, make_greeting
from config import KNOWLEDGE_DIR
from rag import list_available_spots


def test_knowledge_base_is_available():
    spots = list_available_spots()
    assert len(spots) >= 4
    sample = Path(KNOWLEDGE_DIR) / "01_古村落空间" / f"{spots[0]}.md"
    assert sample.exists()
    assert sample.read_text(encoding="utf-8").strip()


def test_greeting_options_match_numbered_choices():
    greeting, options = make_greeting()
    assert options
    for index, option in enumerate(options, 1):
        assert f"{index}. {option}" in greeting


def test_confirm_requires_an_exact_confirmation():
    assert is_confirm("确认！")
    assert is_confirm("OK")
    assert not is_confirm("我还没有确认")
