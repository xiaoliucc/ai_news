"""
测试 Agent 核心 — tool-use 主循环与端到端流程。

覆盖：
    - chat(): 未配置 LLM 时的友好提示（mock，无网络）
    - chat(): LLM 发起工具调用 → 执行工具 → 回传结果 → 最终回复（mock，无网络）
    - 完整链路：真实采集 → 注入向量库 → Agent 对话（integration，需网络 + API key）
"""

import json
import os
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from backend.agent import tools
from backend.agent.core import chat
from backend import vector_store
from src.engine import NewsEngine
from src.models import Article
from src.sources.arxiv import ArxivSource
from src.sources.hackernews import HackerNewsSource
from src.sources.papers import HuggingFacePaperSource


def make_article(
    article_id: str = "mock_1",
    title: str = "LLM 论文",
    source: str = "arxiv",
) -> Article:
    """快速创建测试用 Article。"""
    return Article(
        id=article_id,
        title=title,
        url="https://arxiv.org/abs/2401.12345",
        source=source,
        summary="关于大语言模型的研究",
        author=None,
        published_at=None,
        score=10,
        tags=["LLM"],
        language="en",
    )


@pytest.fixture
def registered_articles():
    """向向量库注入假文章，测试后清理。"""
    # 用 mock collection 避免真实 ChromaDB 初始化
    mock_col = MagicMock()
    mock_col.query.return_value = {
        "ids": [["mock_1"]],
        "metadatas": [[{
            "title": "LLM 论文", "source": "arxiv", "score": 10,
            "published_at": 1754006400.0,
            "url": "https://arxiv.org/abs/2401.12345",
        }]],
        "distances": [[0.1]],
    }
    vector_store._collection = mock_col
    vector_store.add_articles([make_article()])
    yield
    vector_store._reset()


def _tool_call(name: str, arguments: dict, call_id: str = "call_1") -> SimpleNamespace:
    """构造 OpenAI API 返回的 tool_call 对象。"""
    return SimpleNamespace(
        id=call_id,
        function=SimpleNamespace(
            name=name,
            arguments=json.dumps(arguments, ensure_ascii=False),
        ),
    )


def _replay(
    content: str | None,
    finish_reason: str = "stop",
    tool_calls: list | None = None,
) -> SimpleNamespace:
    """构造 chat.completions.create 的返回对象。"""
    return SimpleNamespace(
        choices=[
            SimpleNamespace(
                finish_reason=finish_reason,
                message=SimpleNamespace(content=content, tool_calls=tool_calls),
            )
        ]
    )


class FakeCompletions:
    """按预设响应依次返回的 completions 假实现。"""

    def __init__(self, responses: list):
        self._responses = list(responses)
        self.calls: list[dict] = []

    def create(self, **kwargs) -> SimpleNamespace:
        self.calls.append(kwargs)
        return self._responses.pop(0)


class FakeClient:
    """模拟 OpenAI 客户端的 chat.completions 调用链。"""

    def __init__(self, responses: list):
        self.chat = SimpleNamespace(completions=FakeCompletions(responses))


@pytest.mark.asyncio
async def test_chat_returns_config_hint_without_client(monkeypatch):
    """未配置 LLM 客户端时返回配置提示，不发起任何请求。"""
    monkeypatch.setattr("backend.agent.core._get_client", lambda: None)

    answer = await chat("你好")

    assert "DEEPSEEK_API_KEY" in answer


@pytest.mark.asyncio
async def test_chat_runs_tool_loop(monkeypatch, registered_articles):
    """LLM 发起工具调用时，Agent 应执行工具并把结果回传给 LLM。"""
    responses = [
        _replay(
            content=None,
            finish_reason="tool_calls",
            tool_calls=[_tool_call("search_articles", {"query": "LLM"})],
        ),
        _replay(content="找到 1 篇相关文章。"),
    ]
    fake = FakeClient(responses)
    monkeypatch.setattr("backend.agent.core._get_client", lambda: fake)
    monkeypatch.setattr("backend.agent.core._model_id", lambda: "fake-model")

    answer = await chat("帮我找 LLM 文章")

    assert answer == "找到 1 篇相关文章。"
    assert len(fake.chat.completions.calls) == 2
    second_messages = fake.chat.completions.calls[1]["messages"]
    assert any(m["role"] == "tool" for m in second_messages)


@pytest.mark.asyncio
async def test_chat_injects_reading_history_into_prompt(monkeypatch):
    """chat 收到 reading_history 时应注入 system prompt（避免重复推荐）。"""
    responses = [_replay(content="好的。")]
    fake = FakeClient(responses)
    monkeypatch.setattr("backend.agent.core._get_client", lambda: fake)
    monkeypatch.setattr("backend.agent.core._model_id", lambda: "fake-model")

    await chat("继续推荐", reading_history=["Attention Is All You Need"])

    system_prompt = fake.chat.completions.calls[0]["messages"][0]["content"]
    assert "避免重复推荐" in system_prompt
    assert "Attention Is All You Need" in system_prompt


@pytest.mark.asyncio
async def test_chat_injects_conversation_summary_into_prompt(monkeypatch):
    """chat 收到 conversation_summary 时应注入 system prompt（跨会话记忆）。"""
    responses = [_replay(content="好的。")]
    fake = FakeClient(responses)
    monkeypatch.setattr("backend.agent.core._get_client", lambda: fake)
    monkeypatch.setattr("backend.agent.core._model_id", lambda: "fake-model")

    await chat("继续", conversation_summary="用户关注推理效率，已推荐 3 篇论文。")

    system_prompt = fake.chat.completions.calls[0]["messages"][0]["content"]
    assert "跨会话对话记忆" in system_prompt
    assert "用户关注推理效率" in system_prompt


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.skipif(
    not os.getenv("DEEPSEEK_API_KEY"),
    reason="未配置 DEEPSEEK_API_KEY",
)
async def test_agent_full_flow():
    """完整链路：真实采集 3 个源 → 注入向量库 → Agent 对话。"""
    vector_store._reset()
    try:
        engine = NewsEngine(
            [HackerNewsSource(), ArxivSource(), HuggingFacePaperSource()]
        )
        result = await engine.run(limit=3)
        assert result.articles, "采集结果不应为空"

        vector_store.add_articles(result.articles)
        answer = await chat(
            "请从已采集的数据中搜索一篇关于大模型或 Agent 的文章，并用中文总结。"
        )
        assert answer, "Agent 不应返回空回答"
        assert "未配置" not in answer
    finally:
        vector_store._reset()
