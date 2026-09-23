"""轻量知识库检索。

直接读取仓库内的 Markdown 资料并按关键词排序，避免在无服务器运行时下载
大型向量模型。19 份授权资料会随部署包一起发布。
"""
import re
from functools import lru_cache
from pathlib import Path

from config import KNOWLEDGE_DIR


def _chunks(text: str, size: int = 1800) -> list[str]:
    sections = [part.strip() for part in re.split(r"\n(?=#{1,4}\s)|\n{2,}", text) if part.strip()]
    result: list[str] = []
    for section in sections:
        if len(section) <= size:
            result.append(section)
        else:
            result.extend(section[i:i + size] for i in range(0, len(section), size))
    return result


@lru_cache(maxsize=1)
def _load_documents() -> list[dict]:
    root = Path(KNOWLEDGE_DIR)
    documents: list[dict] = []
    if not root.exists():
        return documents
    for path in sorted(root.rglob("*.md")):
        text = path.read_text(encoding="utf-8", errors="ignore")
        rel = path.relative_to(root)
        source_dir = rel.parts[0] if len(rel.parts) > 1 else ""
        for chunk in _chunks(text):
            documents.append({
                "text": chunk,
                "source_dir": source_dir,
                "title": path.stem,
            })
    return documents


def _terms(query: str) -> list[str]:
    words = re.findall(r"[A-Za-z0-9_-]+|[\u4e00-\u9fff]{2,}", query.lower())
    terms: list[str] = []
    for word in words:
        terms.append(word)
        if len(word) > 4 and re.fullmatch(r"[\u4e00-\u9fff]+", word):
            terms.extend(word[i:i + 2] for i in range(len(word) - 1))
    return list(dict.fromkeys(terms))


def retrieve(query: str, k: int = 5, source_dir: str | None = None) -> list[str]:
    terms = _terms(query)
    scored: list[tuple[int, str]] = []
    for doc in _load_documents():
        if source_dir and doc["source_dir"] != source_dir:
            continue
        haystack = f'{doc["title"]}\n{doc["text"]}'.lower()
        score = sum((8 if term in doc["title"].lower() else 1) * haystack.count(term) for term in terms)
        scored.append((score, f'【来源：{doc["title"]}】\n{doc["text"]}'))
    scored.sort(key=lambda item: item[0], reverse=True)
    matches = [text for score, text in scored if score > 0][:k]
    if matches:
        return matches
    return [text for _, text in scored[:k]]


def build_vectorstore():
    """兼容旧启动脚本：预热 Markdown 缓存即可。"""
    docs = _load_documents()
    print(f"知识库加载完成，共 {len(docs)} 个文本片段")


def get_retriever():
    class Retriever:
        def invoke(self, query: str):
            return retrieve(query)
    return Retriever()


def retrieve_multi_dimension(spot: str, script_type: str) -> str:
    """
    分维度检索：空间、民俗、文学、政策四类资料都拉一些，拼成一段文本。
    用于生成 plot_nodes 时提供多维度参考。
    """
    parts = []

    # 01 空间（景区相关）
    docs = retrieve(f"{spot} {script_type} 空间 布局 建筑", k=3, source_dir="01_古村落空间")
    if docs:
        parts.append("【空间资料】\n" + "\n".join(docs))

    # 02 民俗（非遗、民俗、传说）
    docs = retrieve(f"{spot} 民俗 非遗 传说 戏曲", k=3, source_dir="02_非遗民俗")
    if docs:
        parts.append("【民俗资料】\n" + "\n".join(docs))

    # 03 文学（诗歌、文人、书院）
    docs = retrieve(f"{spot} 诗歌 文学 文人 耕读", k=3, source_dir="03_文学语料")
    if docs:
        parts.append("【文学资料】\n" + "\n".join(docs))

    # 04 政策（政策、产业、品牌）
    docs = retrieve(f"{spot} 政策 产业 品牌 创建", k=2, source_dir="04_政策产业")
    if docs:
        parts.append("【政策资料】\n" + "\n".join(docs))

    return "\n\n".join(parts)


def list_available_spots() -> list[str]:
    """
    扫描 01_古村落空间 子目录，返回所有可用的景区名称（.md 文件名去掉后缀）。
    """
    spots_dir = Path(KNOWLEDGE_DIR) / "01_古村落空间"
    if not spots_dir.exists():
        return []
    return sorted(path.stem for path in spots_dir.glob("*.md"))
