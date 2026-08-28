"""
测试 Agent 流式对话 — chat_stream() 事件序列与工具轮行为。

覆盖（均为 mock，无网络）：
    - chat_stream(): 未配置 LLM 时产出 error 事件
    - chat_stream(): 纯文本轮 → token 事件逐个产出 + done 事件
    - chat_stream(): 工具轮 → tool start/done 事件 + 参数分段拼接 + 最终 token 流
"""

import json
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from backend.agent.core import chat_stream
from backend import vector_store


def make_article(
    article_id: str = "mock_1",
    title: str = "LLM 论文",
    source: str = "arxiv",
):
    """快速创建测试用 Article（与 test_agent.py 保持一致）。"""
    from src.models import Article

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


def _delta_chunk(content: str | None = None, tool_calls: list | None = None):
    """构造一个流式 chunk（含 delta）。"""
    return SimpleNamespace(
        choices=[SimpleNamespace(delta=SimpleNamespace(content=content, tool_calls=tool_calls))]
    )


def _tool_chunk(idx: int, tc_id: str | None = None, name: str | None = None, args: str | None = None):
    """构造一个携带 tool_calls 增量（含 index/function 分段）的 chunk。"""
    fn = SimpleNamespace(name=name, arguments=args)
    tc = SimpleNamespace(index=idx, id=tc_id, function=fn)
    return _delta_chunk(content=None, tool_calls=[tc])


def _tool_call_chunks(name: str, arguments: dict) -> list:
    """模拟一次工具调用的完整流式增量（id/name 首块，arguments 分段）。"""
    args_json = json.dumps(arguments, ensure_ascii=False)
    mid = len(args_json) // 2
    return [
        _tool_chunk(0, tc_id="call_1", name=name),
        _tool_chunk(0, args=args_json[:mid]),
        _tool_chunk(0, args=args_json[mid:]),
    ]


class FakeStreamCompletions:
    """按预设流式响应依次返回的 completions 假实现（create 返回迭代器）。"""

    def __init__(self, streams: list):
        self._streams = list(streams)
        self.calls: list[dict] = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return iter(self._streams.pop(0))


class FakeClient:
    """模拟 OpenAI 客户端的流式调用链。"""

    def __init__(self, streams: list):
        self.chat = SimpleNamespace(completions=FakeStreamCompletions(streams))


async def _collect_events(**kwargs) -> list[dict]:
    """收集 chat_stream 产出的全部事件。"""
    return [ev async for ev in chat_stream(**kwargs)]


@pytest.mark.asyncio
async def test_stream_emits_error_without_client(monkeypatch):
    """未配置 LLM 客户端时产出 error 事件，不发起任何请求。"""
    monkeypatch.setattr("backend.agent.core._get_client", lambda: None)

    events = await _collect_events(message="你好")

    assert events == [{"type": "error", "message": "LLM 未配置，请在 .env 中设置 DEEPSEEK_API_KEY。"}]


@pytest.mark.asyncio
async def test_stream_emits_tokens_then_done(monkeypatch):
    """纯文本轮：LLM 流式增量逐个转成 token 事件，最后 done。"""
    streams = [[_delta_chunk(content="你"), _delta_chunk(content="好")]]
    fake = FakeClient(streams)
    monkeypatch.setattr("backend.agent.core._get_client", lambda: fake)
    monkeypatch.setattr("backend.agent.core._model_id", lambda: "fake-model")

    events = await _collect_events(message="你好")

    tokens = [e["text"] for e in events if e["type"] == "token"]
    assert tokens == ["你", "好"]
    assert events[-1] == {"type": "done", "answer": "你好"}
    # create 必须带 stream=True
    assert fake.chat.completions.calls[0]["stream"] is True


@pytest.mark.asyncio
async def test_stream_emits_tool_events_then_tokens(monkeypatch, registered_articles):
    """工具轮：先 tool start/done 事件，再进入答案轮 token 流。"""
    streams = [
        _tool_call_chunks("search_articles", {"query": "LLM"}),
        [_delta_chunk(content="找到 1 篇相关文章。")],
    ]
    fake = FakeClient(streams)
    monkeypatch.setattr("backend.agent.core._get_client", lambda: fake)
    monkeypatch.setattr("backend.agent.core._model_id", lambda: "fake-model")

    events = await _collect_events(message="帮我找 LLM 文章")

    kinds = [(e["type"], e.get("name"), e.get("status")) for e in events]
    assert kinds[0] == ("tool", "search_articles", "start")
    assert kinds[1] == ("tool", "search_articles", "done")
    assert kinds[-1] == ("done", None, None)
    assert events[-1]["answer"] == "找到 1 篇相关文章。"

    # 第二轮调用应携带 assistant tool_calls + tool 结果消息
    second = fake.chat.completions.calls[1]["messages"]
    assert any(m["role"] == "tool" for m in second)
    assert any(m.get("tool_calls") for m in second)
    # 参数分段拼接完整
    tool_msg = next(m for m in second if m.get("tool_calls"))
    args = tool_msg["tool_calls"][0]["function"]["arguments"]
    assert json.loads(args) == {"query": "LLM"}


@pytest.mark.asyncio
async def test_stream_tool_round_emits_no_tokens(monkeypatch, registered_articles):
    """工具轮不向客户端透出 token（模型输出的是 tool_calls JSON 而非正文）。"""
    streams = [
        _tool_call_chunks("search_articles", {"query": "LLM"}),
        [_delta_chunk(content="回"), _delta_chunk(content="答"), _delta_chunk(content="。")],
    ]
    fake = FakeClient(streams)
    monkeypatch.setattr("backend.agent.core._get_client", lambda: fake)
    monkeypatch.setattr("backend.agent.core._model_id", lambda: "fake-model")

    events = await _collect_events(message="搜索")

    tokens = [e for e in events if e["type"] == "token"]
    # 工具轮不透出 JSON 片段；答案轮 token 按块透出，拼接还原全文
    assert all(t["text"] != '{"query":' for t in tokens)
    assert "".join(t["text"] for t in tokens) == "回答。"
    assert events[-1] == {"type": "done", "answer": "回答。"}
