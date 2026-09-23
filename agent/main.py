"""
FastAPI 入口。给前端提供 /chat 接口。
"""
import os
from pathlib import Path
from typing import Any
from fastapi import FastAPI
from fastapi import HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from agent import chat
from config import DEEPSEEK_API_KEY, KNOWLEDGE_DIR

app = FastAPI(title="楠溪江文旅剧本 Agent")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[x.strip() for x in os.getenv(
        "ALLOWED_ORIGINS",
        "https://hfddth.github.io,http://127.0.0.1:5500,http://localhost:5500",
    ).split(",") if x.strip()],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    session_id: str = Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_-]+$")
    message: str = Field(default="", max_length=4000)


class ChatResponse(BaseModel):
    reply: str
    script: dict[str, Any]
    stage: str


@app.post("/chat", response_model=ChatResponse)
def chat_endpoint(req: ChatRequest):
    result = chat(req.session_id, req.message)
    # 兼容：agent 可能返回没有 missing_fields 的 dict
    return ChatResponse(
        reply=result.get("reply", ""),
        script=result.get("script", {}),
        stage=result.get("stage", ""),
    )


@app.get("/project/{session_id}")
def get_project(session_id: str):
    from agent import SESSIONS
    state = SESSIONS.get(session_id)
    if not state or not state.get("script"):
        raise HTTPException(status_code=404, detail="项目不存在")
    return state["script"].model_dump(mode="json")


@app.get("/")
def root():
    return {"service": "sanshui-agent", "status": "ok"}


@app.get("/health")
def health():
    missing = []
    if not DEEPSEEK_API_KEY:
        missing.append("model_api_key")
    knowledge_root = Path(KNOWLEDGE_DIR)
    if not knowledge_root.exists() or not any(knowledge_root.rglob("*.md")):
        missing.append("knowledge_base")
    if missing:
        raise HTTPException(
            status_code=503,
            detail={"status": "not_ready", "missing": missing},
        )
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
