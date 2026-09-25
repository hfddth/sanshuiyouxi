"""FastAPI entry point for the tourism script Agent."""
import os

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from agent import SESSIONS, chat, get_session_state


app = FastAPI(title="文旅剧本游策划 Agent")

allowed_origins = [
    item.strip()
    for item in os.getenv(
        "ALLOWED_ORIGINS",
        ",".join(
            [
                "https://hfddth.github.io",
                "https://sanshuiyouxi.zxiehuan898572.chatgpt.site",
                "https://sanshuiyouxi-m2ycntgf.edgeone.cool",
                "http://127.0.0.1:5500",
                "http://localhost:5500",
            ]
        ),
    ).split(",")
    if item.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    session_id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,128}$")
    message: str = ""


class ChatResponse(BaseModel):
    reply: str
    script: dict
    stage: str
    progress: dict
    loading_hint: str = ""
    next_hint: str = ""


@app.post("/chat", response_model=ChatResponse)
def chat_endpoint(req: ChatRequest):
    result = chat(req.session_id, req.message)
    return ChatResponse(
        reply=result.get("reply", ""),
        script=result.get("script", {}),
        stage=result.get("stage", ""),
        progress=result.get("progress", {}),
        loading_hint=result.get("loading_hint", ""),
        next_hint=result.get("next_hint", ""),
    )


@app.get("/session/{session_id}")
def session_state_api(session_id: str):
    return get_session_state(session_id)


@app.get("/project/{session_id}")
def get_project(session_id: str):
    state = SESSIONS.get(session_id)
    if not state or not state.get("script"):
        raise HTTPException(status_code=404, detail="项目不存在或尚未生成")
    return state["script"].model_dump(mode="json")


@app.get("/health")
def health():
    return {"status": "ok", "agent": "v4"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8000")))
