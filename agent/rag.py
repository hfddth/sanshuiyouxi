"""
RAG 检索模块：加载 .md 知识库 → 切分 → 向量化 → 存入 Chroma → 提供检索接口。
策略：优先使用本地缓存的嵌入模型，本地没有时再联网下载（走国内镜像）。
"""
import os

from langchain_community.document_loaders import DirectoryLoader, TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings

from config import KNOWLEDGE_DIR, CHROMA_PERSIST_DIR, EMBEDDING_MODEL


# ===== 全局单例 =====
_EMBEDDINGS = None


def get_embeddings():
    """全局单例。先尝试只用本地缓存，本地没有时再联网下载（走镜像）。"""
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
    _EMBEDDINGS = HuggingFaceEmbeddings(
        model_name=EMBEDDING_MODEL,
    )
    print("✅ 已联网下载并加载嵌入模型")
    return _EMBEDDINGS


def build_vectorstore():
    """
    构建向量库。加载所有 .md 文件，为每个文本块打上来源文件夹标签。
    """
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

    # 为每个文档打上来源文件夹标签
    for doc in docs:
        source = doc.metadata.get("source", "")
        rel = os.path.relpath(source, KNOWLEDGE_DIR)
        parts = rel.split(os.sep)
        # parts[0] 是顶层子目录名，如 "01_古村落空间"
        doc.metadata["source_dir"] = parts[0] if len(parts) >= 2 else ""

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=500,
        chunk_overlap=80,
        separators=["##", "\n\n", "\n", "。", "；"],
    )
    chunks = splitter.split_documents(docs)

    embeddings = get_embeddings()
    # 删除旧库，避免重复数据
    import shutil
    if os.path.exists(CHROMA_PERSIST_DIR):
        shutil.rmtree(CHROMA_PERSIST_DIR)
    Chroma.from_documents(
        chunks,
        embeddings,
        persist_directory=CHROMA_PERSIST_DIR,
    )
    print(f"向量库构建完成，共 {len(chunks)} 个文本块，已保存到 {CHROMA_PERSIST_DIR}")


def get_retriever():
    """返回 retriever（无过滤，供简单检索用）。"""
    vectorstore = Chroma(
        persist_directory=CHROMA_PERSIST_DIR,
        embedding_function=get_embeddings(),
    )
    return vectorstore.as_retriever(search_kwargs={"k": 5})


def retrieve(query: str, k: int = 5, source_dir: str = None) -> list[str]:
    """
    检索接口。可按 source_dir 过滤（如 "01_古村落空间"）。
    """
    vectorstore = Chroma(
        persist_directory=CHROMA_PERSIST_DIR,
        embedding_function=get_embeddings(),
    )
    if source_dir:
        results = vectorstore.similarity_search(
            query, k=k, filter={"source_dir": source_dir}
        )
    else:
        results = vectorstore.similarity_search(query, k=k)
    return [doc.page_content for doc in results]


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
    spots_dir = os.path.join(KNOWLEDGE_DIR, "01_古村落空间")
    if not os.path.exists(spots_dir):
        return []
    spots = []
    for fname in os.listdir(spots_dir):
        if fname.endswith(".md"):
            spots.append(fname[:-3])
    return spots