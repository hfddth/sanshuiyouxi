"""
FastAPI 入口。给前端提供 /chat 接口。
"""
import os
from fastapi import FastAPI
from fastapi import HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from agent import chat

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
    session_id: str
    message: str = ""


class ChatResponse(BaseModel):
    reply: str
    script: dict
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


@app.get("/health")
async def health():
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
