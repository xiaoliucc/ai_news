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
         patch("backend.routers.agent.get_profile", return_value={"interests": [], "conversation_summary": ""}):
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
            conversation_summary=None,
        )


def test_agent_chat_archives_long_history():
    """history 超过阈值时：旧轮次压缩进摘要存库，chat 只收到最近 KEEP_MESSAGES 条"""
    with patch("backend.routers.agent.chat") as mock_chat, \
         patch("backend.routers.agent.get_profile") as mock_profile, \
         patch("backend.routers.agent.summarize_conversation") as mock_summarize, \
         patch("backend.routers.agent.set_profile") as mock_set_profile:
        mock_chat.return_value = "OK"
        mock_profile.return_value = {"interests": [], "conversation_summary": "旧摘要"}
        mock_summarize.return_value = "合并后的新摘要"

        history = [{"role": "user" if i % 2 == 0 else "assistant", "content": f"msg{i}"} for i in range(13)]
        resp = client.post("/api/agent/chat", json={"message": "继续", "history": history})
        assert resp.status_code == 200

        # 归档调用：旧摘要 + 最早 1 条消息 → 新摘要
        mock_summarize.assert_called_once_with("旧摘要", [history[0]])
        mock_set_profile.assert_called_once_with(conversation_summary="合并后的新摘要")
        # chat 收到最近 12 条 + 新摘要
        mock_chat.assert_called_once_with(
            message="继续",
            history=history[-12:],
            interests=[],
            reading_history=None,
            conversation_summary="合并后的新摘要",
        )


def test_agent_chat_short_history_no_archive():
    """history 未超阈值时不归档，chat 收到全量历史与 profile 摘要"""
    with patch("backend.routers.agent.chat") as mock_chat, \
         patch("backend.routers.agent.get_profile") as mock_profile, \
         patch("backend.routers.agent.summarize_conversation") as mock_summarize, \
         patch("backend.routers.agent.set_profile") as mock_set_profile:
        mock_chat.return_value = "OK"
        mock_profile.return_value = {"interests": [], "conversation_summary": "旧摘要"}

        history = [{"role": "user", "content": "hi"}] * 12
        resp = client.post("/api/agent/chat", json={"message": "hello", "history": history})
        assert resp.status_code == 200
        mock_summarize.assert_not_called()
        mock_set_profile.assert_not_called()
        mock_chat.assert_called_once_with(
            message="hello",
            history=history,
            interests=[],
            reading_history=None,
            conversation_summary="旧摘要",
        )


def test_agent_chat_archive_failure_degrades():
    """摘要生成失败时保留旧摘要不存库，对话照常（截断历史）"""
    with patch("backend.routers.agent.chat") as mock_chat, \
         patch("backend.routers.agent.get_profile") as mock_profile, \
         patch("backend.routers.agent.summarize_conversation", return_value=None) as mock_summarize, \
         patch("backend.routers.agent.set_profile") as mock_set_profile:
        mock_chat.return_value = "OK"
        mock_profile.return_value = {"interests": [], "conversation_summary": "旧摘要"}

        history = [{"role": "user", "content": "hi"}] * 13
        resp = client.post("/api/agent/chat", json={"message": "hello", "history": history})
        assert resp.status_code == 200
        mock_summarize.assert_called_once()
        mock_set_profile.assert_not_called()  # 未存库
        mock_chat.assert_called_once_with(
            message="hello",
            history=history[-12:],
            interests=[],
            reading_history=None,
            conversation_summary="旧摘要",  # 注入旧摘要兜底
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
            conversation_summary=None,
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
            conversation_summary=None,
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
            conversation_summary=None,
        )
