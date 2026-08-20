"""
测试对话摘要记忆（P2）— 增量合并跨会话摘要。

覆盖：
    - 正常合并：返回 LLM 摘要文本
    - 空轮次：返回旧摘要不调用 LLM
    - LLM 不可用 / 输出解析失败：返回 None（调用方保留旧摘要）
"""

import json

from backend.agent import memory


def _rounds(n: int = 3) -> list[dict]:
    """构造 n 轮对话消息。"""
    out = []
    for i in range(n):
        out.append({"role": "user", "content": f"问题 {i}"})
        out.append({"role": "assistant", "content": f"回答 {i}"})
    return out


def test_summarize_success(monkeypatch):
    """LLM 正常返回摘要。"""
    monkeypatch.setattr(
        memory,
        "_chat_json",
        lambda *a, **k: json.dumps({"summary": "用户关注推理效率，已推荐 3 篇论文。"}),
    )
    result = memory.summarize_conversation("旧摘要", _rounds())
    assert result == "用户关注推理效率，已推荐 3 篇论文。"


def test_summarize_empty_rounds_returns_old(monkeypatch):
    """空轮次不调用 LLM，直接返回旧摘要。"""
    called = {"n": 0}
    monkeypatch.setattr(
        memory, "_chat_json", lambda *a, **k: called.__setitem__("n", called["n"] + 1) or '{"summary":"x"}'
    )
    assert memory.summarize_conversation("旧摘要", []) == "旧摘要"
    assert called["n"] == 0  # 未调用 LLM


def test_summarize_none_when_llm_unavailable(monkeypatch):
    """LLM 调用不可用（返回 None）→ 返回 None，调用方保留旧摘要。"""
    monkeypatch.setattr(memory, "_chat_json", lambda *a, **k: None)
    assert memory.summarize_conversation("旧摘要", _rounds()) is None


def test_summarize_none_on_bad_json(monkeypatch):
    """LLM 输出非 JSON → 返回 None。"""
    monkeypatch.setattr(memory, "_chat_json", lambda *a, **k: "garbage")
    assert memory.summarize_conversation(None, _rounds()) is None


def test_summarize_none_on_empty_summary(monkeypatch):
    """LLM 返回空摘要文本 → 返回 None。"""
    monkeypatch.setattr(memory, "_chat_json", lambda *a, **k: json.dumps({"summary": "  "}))
    assert memory.summarize_conversation("旧摘要", _rounds()) is None
