"""Railway 运行配置。密钥只从环境变量读取。"""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent

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
LLM_TIMEOUT_SECONDS = float(os.getenv("LLM_TIMEOUT_SECONDS", "120"))
LLM_MAX_RETRIES = int(os.getenv("LLM_MAX_RETRIES", "2"))
KNOWLEDGE_DIR = os.getenv("KNOWLEDGE_DIR", str(BASE_DIR / "data" / "nanxijiang"))
