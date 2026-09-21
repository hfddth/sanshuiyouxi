"""EdgeOne Makers entry point for the 山水有戏 Agent.

File path ``agents/chat/index.py`` maps to ``POST /chat``.
"""
from __future__ import annotations

import asyncio
import importlib
import os
import sys
from pathlib import Path
from typing import Any


CORE_DIR = Path(__file__).resolve().parent / "core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

_core_chat = None


def _env_value(context: Any, name: str) -> str:
    env = getattr(context, "env", None)
    if isinstance(env, dict):
        return str(env.get(name) or "")
    return str(getattr(env, name, "") or "")


def _load_core(context: Any):
    global _core_chat
    if _core_chat is not None:
        return _core_chat

    # Makers automatically injects the model gateway credentials. Map them to
    # the names already used by the existing DeepSeek-compatible core.
    mappings = {
        "DEEPSEEK_API_KEY": "AI_GATEWAY_API_KEY",
        "DEEPSEEK_BASE_URL": "AI_GATEWAY_BASE_URL",
        "DEEPSEEK_MODEL": "AI_GATEWAY_MODEL",
    }
    for target, source in mappings.items():
        value = os.getenv(target) or os.getenv(source) or _env_value(context, source)
        if value:
            os.environ[target] = value
    os.environ.setdefault("LLM_PROVIDER", "deepseek")
    os.environ.setdefault("DEEPSEEK_MODEL", "@makers/deepseek-v4-flash")
    os.environ.setdefault("KNOWLEDGE_DIR", str(CORE_DIR / "data" / "nanxijiang"))

    module = importlib.import_module("agent")
    _core_chat = module.chat
    return _core_chat


async def handler(context: Any) -> dict:
    body = context.request.body if isinstance(context.request.body, dict) else {}
    conversation_id = str(
        getattr(context, "conversation_id", "")
        or body.get("session_id")
        or body.get("sessionId")
        or ""
    ).strip()
    message = str(body.get("message") or "")

    if not conversation_id:
        return {
            "status_code": 400,
            "body": {"reply": "缺少会话标识。", "script": {}, "stage": "error"},
        }

    chat = _load_core(context)
    return await asyncio.to_thread(chat, conversation_id, message)
