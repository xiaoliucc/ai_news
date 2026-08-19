import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from unittest.mock import patch

from backend.routers.agent import router

app = FastAPI()
app.include_router(router)
client = TestClient(app)


# ---------- agent_chat 集成测试 ----------

def test_agent_chat_success():
    """正常对话返回"""
    with patch("backend.routers.agent.chat") as mock_chat, \
         patch("backend.routers.agent.get_profile") as mock_profile:
        mock_chat.return_value = "找到 3 篇多模态论文"
        mock_profile.return_value = {"interests": []}

        resp = client.post("/api/agent/chat", json={"message": "多模态论文有哪些？"})
        assert resp.status_code == 200
        assert resp.json()["answer"] == "找到 3 篇多模态论文"


def test_agent_chat_empty_message():
    """空消息应 400"""
    resp = client.post("/api/agent/chat", json={"message": "   "})
    assert resp.status_code == 400


def test_agent_chat_message_too_short():
    """message 为空字符串应被 Field(min_length=1) 拦截（422）"""
    resp = client.post("/api/agent/chat", json={"message": ""})
    assert resp.status_code == 422


def test_agent_chat_history_too_many_turns():
    """history 超过 20 轮应 422"""
    history = [{"role": "user", "content": "hi"}] * 21
    resp = client.post("/api/agent/chat", json={"message": "hello", "history": history})
    assert resp.status_code == 422


def test_agent_chat_history_content_too_long():
    """history 内容总量超过 20000 字符应 422"""
    history = [
        {"role": "user", "content": "x" * 11000},
        {"role": "assistant", "content": "y" * 11000},
    ]
    resp = client.post("/api/agent/chat", json={"message": "hello", "history": history})
    assert resp.status_code == 422


def test_agent_chat_with_history_and_interests():
    """传递 history 和 interests 给 chat"""
    with patch("backend.routers.agent.chat") as mock_chat, \
         patch("backend.routers.agent.get_profile"):
        mock_chat.return_value = "OK"

        history = [{"role": "user", "content": "你好"}, {"role": "assistant", "content": "你好！"}]
        resp = client.post("/api/agent/chat", json={
            "message": "继续说",
            "history": history,
            "interests": ["多模态", "RAG"],
        })
        assert resp.status_code == 200
        mock_chat.assert_called_once_with(
            message="继续说",
            history=history,
            interests=["多模态", "RAG"],
            reading_history=None,
        )


def test_agent_chat_falls_back_to_profile_interests():
    """不传 interests 时从 user_profile 读取"""
    with patch("backend.routers.agent.chat") as mock_chat, \
         patch("backend.routers.agent.get_profile") as mock_profile:
        mock_chat.return_value = "OK"
        mock_profile.return_value = {"interests": ["CV", "NLP"]}

        resp = client.post("/api/agent/chat", json={"message": "hello"})
        assert resp.status_code == 200
        mock_chat.assert_called_once_with(
            message="hello",
            history=None,
            interests=["CV", "NLP"],
            reading_history=None,
        )


def test_agent_chat_exception_returns_500():
    """chat 异常时返回 500"""
    with patch("backend.routers.agent.chat") as mock_chat, \
         patch("backend.routers.agent.get_profile") as mock_profile:
        mock_chat.side_effect = RuntimeError("LLM 超时")
        mock_profile.return_value = {"interests": []}

        resp = client.post("/api/agent/chat", json={"message": "test"})
        assert resp.status_code == 500


def test_agent_chat_passes_resolved_reading_history():
    """profile 有阅读历史时，chat 收到解析后的标题列表"""
    with patch("backend.routers.agent.chat") as mock_chat, \
         patch("backend.routers.agent.get_profile") as mock_profile, \
         patch("backend.routers.agent.get_article") as mock_get_article:
        mock_chat.return_value = "OK"
        mock_profile.return_value = {
            "interests": [],
            "reading_history": ["arxiv_1", "arxiv_2"],
        }
        mock_get_article.side_effect = [
            {"title": "Paper One", "id": "arxiv_1"},
            {"title": "Paper Two", "id": "arxiv_2"},
        ]

        resp = client.post("/api/agent/chat", json={"message": "hello"})
        assert resp.status_code == 200
        mock_chat.assert_called_once_with(
            message="hello",
            history=None,
            interests=[],
            reading_history=["Paper One", "Paper Two"],
        )


def test_agent_chat_reading_history_all_invalid_passes_none():
    """阅读历史 ID 全部失效时，chat 收到 None（不注入空段）"""
    with patch("backend.routers.agent.chat") as mock_chat, \
         patch("backend.routers.agent.get_profile") as mock_profile, \
         patch("backend.routers.agent.get_article", return_value=None):
        mock_chat.return_value = "OK"
        mock_profile.return_value = {
            "interests": [],
            "reading_history": ["gone_1"],
        }

        resp = client.post("/api/agent/chat", json={"message": "hello"})
        assert resp.status_code == 200
        mock_chat.assert_called_once_with(
            message="hello",
            history=None,
            interests=[],
            reading_history=None,
        )
