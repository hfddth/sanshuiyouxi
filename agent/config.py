"""Runtime configuration sourced only from environment variables."""
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent


def _as_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


LLM_PROVIDER = os.getenv("LLM_PROVIDER", "deepseek")

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY") or os.getenv("AI_GATEWAY_API_KEY")
DEEPSEEK_BASE_URL = (
    os.getenv("DEEPSEEK_BASE_URL")
    or os.getenv("AI_GATEWAY_BASE_URL")
    or "https://api.deepseek.com"
)
DEEPSEEK_MODEL = (
    os.getenv("DEEPSEEK_MODEL")
    or os.getenv("AI_GATEWAY_MODEL")
    or "deepseek-chat"
)

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:7b")

EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "BAAI/bge-small-zh-v1.5")
CHROMA_PERSIST_DIR = os.getenv("CHROMA_PERSIST_DIR", str(BASE_DIR / "chroma_db"))
KNOWLEDGE_DIR = os.getenv("KNOWLEDGE_DIR", str(BASE_DIR / "data" / "nanxijiang"))

# Network search remains opt-in. Local knowledge is enough for the bundled
# scenic spots, and disabling it avoids relying on an unsupported search model.
ENABLE_WEB_SEARCH = _as_bool("ENABLE_WEB_SEARCH", False)
DEEPSEEK_SEARCH_MODEL = os.getenv("DEEPSEEK_SEARCH_MODEL", DEEPSEEK_MODEL)
SIMILARITY_THRESHOLD = float(os.getenv("SIMILARITY_THRESHOLD", "0.99"))
MAX_LOCAL_SCORE = float(os.getenv("MAX_LOCAL_SCORE", "2"))
LOCAL_TOP_K = int(os.getenv("LOCAL_TOP_K", "3"))
