"""FastAPI entry point for the conversational script planning Agent."""
import os
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from agent import SESSIONS, chat, get_session_state


BASE_DIR = Path(__file__).resolve().parent


def _allowed_origins() -> list[str]:
    configured = os.getenv(
        "ALLOWED_ORIGINS",
        "https://hfddth.github.io,https://sanshuiyouxi.zxiehuan898572.chatgpt.site,"
        "https://sanshuiyouxi-m2ycntgf.edgeone.cool,https://hfddth.cn,"
        "https://www.hfddth.cn,http://localhost:5500,http://127.0.0.1:5500",
    )
    return [origin.strip().rstrip("/") for origin in configured.split(",") if origin.strip()]


app = FastAPI(title="文旅剧本游策划 Agent", version="10")
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins(),
    allow_origin_regex=r"^(https://([a-z0-9-]+\.)?hfddth\.cn|http://(localhost|127\.0\.0\.1)(:\d+)?)$",
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Makers-Conversation-Id"],
)


@app.on_event("startup")
async def startup_event() -> None:
    """Preload the bundled knowledge index when the service starts."""
    try:
        from rag import preload

        preload()
    except Exception as exc:
        print(f"RAG preload failed: {exc}")


class ChatRequest(BaseModel):
    session_id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,128}$")
    message: str = Field(default="", max_length=20000)


class ChatResponse(BaseModel):
    reply: str
    script: dict[str, Any]
    stage: str
    progress: dict[str, Any]
    loading_hint: str = ""
    next_hint: str = ""
    stage5_audit_lines: list[Any] = Field(default_factory=list)


@app.get("/")
async def root() -> dict[str, str]:
    return {"service": "sanshuiyouxi-agent", "status": "ok", "version": "10"}


@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(req: ChatRequest) -> ChatResponse:
    result = chat(req.session_id, req.message)
    return ChatResponse(
        reply=result.get("reply", ""),
        script=result.get("script", {}),
        stage=result.get("stage", ""),
        progress=result.get("progress", {}),
        loading_hint=result.get("loading_hint", ""),
        next_hint=result.get("next_hint", ""),
        stage5_audit_lines=result.get("stage5_audit_lines", []),
    )


@app.get("/session/{session_id}")
async def session_state_api(session_id: str) -> dict[str, Any]:
    return get_session_state(session_id)


@app.get("/project/{session_id}")
async def get_project(session_id: str) -> dict[str, Any]:
    if session_id not in SESSIONS:
        return {"error": "会话不存在"}
    script = SESSIONS[session_id].get("script")
    if script is None:
        return {"error": "策划案尚未生成"}
    return script.model_dump()


@app.get("/health")
async def health() -> dict[str, Any]:
    knowledge_dir = Path(os.getenv("KNOWLEDGE_DIR", BASE_DIR / "data" / "nanxijiang"))
    has_knowledge = knowledge_dir.exists() and any(knowledge_dir.rglob("*.md"))
    has_provider_key = bool(
        os.getenv("DEEPSEEK_API_KEY")
        or os.getenv("AI_GATEWAY_API_KEY")
        or os.getenv("ANTHROPIC_API_KEY")
        or os.getenv("OLLAMA_BASE_URL")
    )
    return {
        "status": "ok" if has_knowledge else "degraded",
        "version": "10",
        "knowledge": "ready" if has_knowledge else "missing",
        "provider_configured": has_provider_key,
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8000")))
