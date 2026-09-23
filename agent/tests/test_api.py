from fastapi.testclient import TestClient

import main
from agent import SESSIONS


client = TestClient(main.app)


def setup_function():
    SESSIONS.clear()


def test_root_identifies_service():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"service": "sanshui-agent", "status": "ok"}


def test_health_is_ready_when_key_and_knowledge_exist(monkeypatch):
    monkeypatch.setattr(main, "DEEPSEEK_API_KEY", "test-key")
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_rejects_missing_key(monkeypatch):
    monkeypatch.setattr(main, "DEEPSEEK_API_KEY", None)
    response = client.get("/health")
    assert response.status_code == 503
    assert "model_api_key" in response.json()["detail"]["missing"]


def test_chat_starts_without_calling_the_model():
    response = client.post(
        "/chat",
        json={"session_id": "ci_session", "message": ""},
    )
    body = response.json()
    assert response.status_code == 200
    assert body["stage"] == "ask_user"
    assert body["reply"]
    assert body["script"] == {}


def test_chat_rejects_unsafe_session_id():
    response = client.post(
        "/chat",
        json={"session_id": "../bad", "message": ""},
    )
    assert response.status_code == 422


def test_github_pages_origin_is_allowed():
    response = client.options(
        "/chat",
        headers={
            "Origin": "https://hfddth.github.io",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "https://hfddth.github.io"
