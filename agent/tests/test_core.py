from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import time

from agent import is_confirm, make_greeting
from config import KNOWLEDGE_DIR
import rag
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


def test_vectorstore_initialization_is_thread_safe(monkeypatch, tmp_path):
    created = []

    class FakeChroma:
        def __init__(self, **kwargs):
            time.sleep(0.02)
            created.append(kwargs)

    monkeypatch.setattr(rag, "Chroma", FakeChroma)
    monkeypatch.setattr(rag, "get_embeddings", lambda: "embedding")
    monkeypatch.setattr(rag, "CHROMA_PERSIST_DIR", str(tmp_path))
    monkeypatch.setattr(rag, "_VECTORSTORE", None)

    with ThreadPoolExecutor(max_workers=4) as pool:
        stores = list(pool.map(lambda _: rag.get_vectorstore(), range(4)))

    assert len(created) == 1
    assert len({id(store) for store in stores}) == 1
