"""
RAG 检索模块：本地优先 + 相似度阈值触发 + DeepSeek 联网补充 + 低质量过滤 + 缓存 + 并行检索。
"""
import os
import httpx
from concurrent.futures import ThreadPoolExecutor, as_completed

from langchain_community.document_loaders import DirectoryLoader, TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings

from config import (
    KNOWLEDGE_DIR, CHROMA_PERSIST_DIR, EMBEDDING_MODEL,
    DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL,
    SIMILARITY_THRESHOLD, MAX_LOCAL_SCORE,
    ENABLE_WEB_SEARCH, DEEPSEEK_SEARCH_MODEL,
)


# ===== 全局单例 =====
_EMBEDDINGS = None
_VECTORSTORE = None
_WEB_CACHE: dict[str, str] = {}
_RETRIEVE_CACHE: dict[str, list] = {}


def get_embeddings():
    """全局单例。嵌入模型只加载一次。"""
    global _EMBEDDINGS
    if _EMBEDDINGS is not None:
        return _EMBEDDINGS

    try:
        _EMBEDDINGS = HuggingFaceEmbeddings(
            model_name=EMBEDDING_MODEL,
            model_kwargs={"local_files_only": True},
        )
        print("✅ 使用本地缓存的嵌入模型")
        return _EMBEDDINGS
    except Exception as e:
        print(f"⚠️ 本地没有找到模型，准备联网下载：{e}")

    os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"
    _EMBEDDINGS = HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL)
    print("✅ 已联网下载并加载嵌入模型")
    return _EMBEDDINGS


def preload():
    """预加载向量库和嵌入模型，供服务启动时调用。"""
    get_embeddings()
    get_vectorstore()
    print("✅ RAG 模块预加载完成")


def get_vectorstore():
    """全局单例。Chroma 只初始化一次。"""
    global _VECTORSTORE
    if _VECTORSTORE is not None:
        return _VECTORSTORE

    _VECTORSTORE = Chroma(
        persist_directory=CHROMA_PERSIST_DIR,
        embedding_function=get_embeddings(),
    )
    return _VECTORSTORE


def build_vectorstore():
    """构建向量库，加载所有 .md 文件并写入 Chroma。"""
    global _VECTORSTORE
    _VECTORSTORE = None
    _RETRIEVE_CACHE.clear()

    if not os.path.exists(KNOWLEDGE_DIR):
        raise FileNotFoundError(
            f"知识库目录不存在：{KNOWLEDGE_DIR}，请先创建并放入 .md 文件"
        )

    loader = DirectoryLoader(
        KNOWLEDGE_DIR,
        glob="**/*.md",
        loader_cls=TextLoader,
        loader_kwargs={"encoding": "utf-8"},
    )
    docs = loader.load()
    if not docs:
        raise ValueError(f"在 {KNOWLEDGE_DIR} 中没有找到任何 .md 文件")

    for doc in docs:
        source = doc.metadata.get("source", "")
        rel = os.path.relpath(source, KNOWLEDGE_DIR)
        parts = rel.split(os.sep)
        doc.metadata["source_dir"] = parts[0] if len(parts) >= 2 else ""

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=500,
        chunk_overlap=80,
        separators=["##", "\n\n", "\n", "。", "；"],
    )
    chunks = splitter.split_documents(docs)

    embeddings = get_embeddings()
    import shutil
    if os.path.exists(CHROMA_PERSIST_DIR):
        shutil.rmtree(CHROMA_PERSIST_DIR)
    Chroma.from_documents(
        chunks,
        embeddings,
        persist_directory=CHROMA_PERSIST_DIR,
    )
    print(f"向量库构建完成，共 {len(chunks)} 个文本块，已保存到 {CHROMA_PERSIST_DIR}")


def retrieve_with_score(query: str, k: int = 5, source_dir: str = None, max_score: float = MAX_LOCAL_SCORE):
    """本地检索，带缓存。"""
    cache_key = f"{query}||{k}||{source_dir}"
    if cache_key in _RETRIEVE_CACHE:
        return _RETRIEVE_CACHE[cache_key]

    vectorstore = get_vectorstore()
    try:
        if source_dir:
            results = vectorstore.similarity_search_with_score(
                query, k=k, filter={"source_dir": source_dir}
            )
        else:
            results = vectorstore.similarity_search_with_score(query, k=k)
    except Exception as e:
        print(f"⚠️ 本地检索失败：{e}")
        results = []

    filtered = [(doc, score) for doc, score in results if score <= max_score]
    docs = [doc for doc, score in filtered]
    best_score = min([score for _, score in filtered]) if filtered else float("inf")
    out = (docs, best_score)
    _RETRIEVE_CACHE[cache_key] = out
    return out


def deepseek_web_search(query: str) -> str:
    """联网搜索，带缓存。"""
    if query in _WEB_CACHE:
        return _WEB_CACHE[query]

    base = (DEEPSEEK_BASE_URL or "https://api.deepseek.com").rstrip("/")
    url = f"{base}/anthropic/v1/messages"

    headers = {
        "x-api-key": DEEPSEEK_API_KEY,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    payload = {
        "model": DEEPSEEK_SEARCH_MODEL,
        "max_tokens": 1024,
        "messages": [
            {"role": "user", "content": [{"type": "text", "text": query}]}
        ],
        "tools": [
            {"type": "web_search_20250305", "name": "web_search"}
        ],
        "tool_choice": {"type": "auto"},
    }

    try:
        with httpx.Client(timeout=60.0) as client:
            resp = client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()

        texts = []
        for block in data.get("content", []):
            if isinstance(block, dict) and block.get("type") == "text":
                texts.append(block.get("text", ""))
        result = "\n".join(texts).strip()
        _WEB_CACHE[query] = result
        return result
    except Exception as e:
        print(f"⚠️ DeepSeek 联网搜索失败：{e}")
        return ""


def retrieve_hybrid(query: str, k: int = 5, source_dir: str = None) -> list[str]:
    """混合检索：本地优先，分数低于阈值时触发联网补充。"""
    local_docs, best_score = retrieve_with_score(query, k=k, source_dir=source_dir)

    if local_docs and best_score <= SIMILARITY_THRESHOLD:
        return [doc.page_content for doc in local_docs]

    if ENABLE_WEB_SEARCH and DEEPSEEK_API_KEY:
        print(f"⚠️ 本地最高分 {best_score:.4f} 高于阈值 {SIMILARITY_THRESHOLD}，触发联网搜索")
        web_text = deepseek_web_search(query)
        combined = [doc.page_content for doc in local_docs]
        if web_text:
            combined.append(f"【联网搜索结果】\n{web_text}")
        return combined

    return [doc.page_content for doc in local_docs]


def retrieve(query: str, k: int = 5, source_dir: str = None) -> list[str]:
    """对外保留的检索接口。"""
    return retrieve_hybrid(query, k=k, source_dir=source_dir)


def retrieve_multi_dimension(spot: str, script_type: str) -> str:
    """
    分维度并行检索。四个维度同时跑，最后合并。
    """
    queries = [
        ("【空间资料】", f"{spot} {script_type} 空间 布局 建筑", 3, "01_古村落空间"),
        ("【民俗资料】", f"{spot} 民俗 非遗 传说 戏曲", 3, "02_非遗民俗"),
        ("【文学资料】", f"{spot} 诗歌 文学 文人 耕读", 3, "03_文学语料"),
        ("【政策资料】", f"{spot} 政策 产业 品牌 创建", 2, "04_政策产业"),
    ]

    results = {}

    def _fetch_one(label, q, k, sd):
        return label, retrieve_hybrid(q, k=k, source_dir=sd)

    # 并行执行
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = [
            executor.submit(_fetch_one, label, q, k, sd)
            for label, q, k, sd in queries
        ]
        for future in as_completed(futures):
            label, docs = future.result()
            results[label] = docs

    # 按原顺序拼接
    parts = []
    for label, _, _, _ in queries:
        docs = results.get(label, [])
        if docs:
            parts.append(label + "\n" + "\n".join(docs))

    return "\n\n".join(parts)


def list_available_spots() -> list[str]:
    """扫描 01_古村落空间 子目录，返回所有景区名称。"""
    spots_dir = os.path.join(KNOWLEDGE_DIR, "01_古村落空间")
    if not os.path.exists(spots_dir):
        return []
    spots = []
    for fname in os.listdir(spots_dir):
        if fname.endswith(".md"):
            spots.append(fname[:-3])
    return spots