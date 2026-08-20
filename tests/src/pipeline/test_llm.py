"""
测试 LLM 语义模块 — AI 相关性判断与质量打分。

覆盖：
    - is_ai_related: LLM 优先 / 回退关键词 / 异常降级
    - score_quality: 正常打分 / clamp / 失败返回 None
    - _chat_json: 瞬时错误自动重试（网络/超时/5xx/429）/ 4xx 不重试
"""

import json
from types import SimpleNamespace

import httpx
import pytest
from openai import APIConnectionError, APIStatusError

from src.pipeline import llm
from src.models import Article


# ── helpers ──────────────────────────────────────────────────────────────────

def _make_article(
    title: str = "Attention Is All You Need: Transformer",
    summary: str | None = "A transformer-based architecture for NLP.",
) -> Article:
    """快速创建测试用 Article。"""
    return Article(
        id="test_1",
        title=title,
        url="https://example.com/1",
        source="test",
        summary=summary,
        author=None,
        published_at=None,
        score=10,
        tags=[],
        language="en",
    )


# ── is_ai_related ────────────────────────────────────────────────────────────

def test_is_ai_related_llm_says_true(monkeypatch):
    """LLM 判断相关时直接采用。"""
    monkeypatch.setattr(
        llm, "_llm_is_ai_related", lambda title, summary: True
    )
    monkeypatch.setattr(llm, "_keyword_related", lambda a: False)
    assert llm.is_ai_related(_make_article()) is True


def test_is_ai_related_llm_says_false(monkeypatch):
    """LLM 判断不相关时直接采用（不查关键词）。"""
    monkeypatch.setattr(
        llm, "_llm_is_ai_related", lambda title, summary: False
    )
    keyword_called = []
    monkeypatch.setattr(
        llm, "_keyword_related", lambda a: keyword_called.append(a) or True
    )
    assert llm.is_ai_related(_make_article()) is False
    assert keyword_called == []


def test_is_ai_related_falls_back_keyword_match(monkeypatch):
    """LLM 返回 None 时回退关键词匹配。"""
    monkeypatch.setattr(llm, "_llm_is_ai_related", lambda t, s: None)
    article = _make_article(title="Transformer 大模型研究")
    assert llm.is_ai_related(article) is True


def test_is_ai_related_falls_back_keyword_miss(monkeypatch):
    """LLM 返回 None 且关键词不命中时返回 False。"""
    monkeypatch.setattr(llm, "_llm_is_ai_related", lambda t, s: None)
    article = _make_article(title="Sonic Pi v5 released", summary="A music tool.")
    assert llm.is_ai_related(article) is False


def test_llm_is_ai_related_chat_json_none_returns_none(monkeypatch):
    """_chat_json 返回 None（LLM 不可用）时 _llm_is_ai_related 返回 None。"""
    monkeypatch.setattr(llm, "_chat_json", lambda *a, **k: None)
    assert llm._llm_is_ai_related("title", "summary") is None


def test_llm_is_ai_related_bad_json_returns_none(monkeypatch):
    """LLM 返回非法 JSON 时返回 None（触发关键词回退）。"""
    monkeypatch.setattr(llm, "_chat_json", lambda *a, **k: "not json at all")
    assert llm._llm_is_ai_related("title", "summary") is None


# ── score_quality ────────────────────────────────────────────────────────────

def test_score_quality_ok(monkeypatch):
    """正常返回打分。"""
    monkeypatch.setattr(
        llm, "_chat_json",
        lambda *a, **k: json.dumps({"quality_score": 85}),
    )
    assert llm.score_quality(_make_article()) == 85


def test_score_quality_clamped(monkeypatch):
    """分数 clamp 到 [0, 100]。"""
    monkeypatch.setattr(
        llm, "_chat_json",
        lambda *a, **k: json.dumps({"quality_score": 150}),
    )
    assert llm.score_quality(_make_article()) == 100


def test_score_quality_none_when_llm_unavailable(monkeypatch):
    """LLM 不可用时返回 None。"""
    monkeypatch.setattr(llm, "_chat_json", lambda *a, **k: None)
    assert llm.score_quality(_make_article()) is None


def test_score_quality_none_on_bad_json(monkeypatch):
    """LLM 输出解析失败返回 None。"""
    monkeypatch.setattr(llm, "_chat_json", lambda *a, **k: "garbage")
    assert llm.score_quality(_make_article()) is None


# ── _chat_json 瞬时错误重试 ──────────────────────────────────────────────────

def _fake_response_obj(content: str):
    """构造带 choices[0].message.content 的响应桩。"""
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content))]
    )


def _fake_client(responses: list):
    """构造 fake OpenAI client：按顺序消费 responses（异常则抛出）。"""
    calls = {"n": 0}

    class _Completions:
        def create(self, **kwargs):
            calls["n"] += 1
            item = responses[min(calls["n"], len(responses)) - 1]
            if isinstance(item, Exception):
                raise item
            return item

    return SimpleNamespace(chat=SimpleNamespace(completions=_Completions())), calls


def _conn_error() -> APIConnectionError:
    """构造连接错误（可重试类）。"""
    return APIConnectionError(request=httpx.Request("POST", "https://api.deepseek.com/v1/chat/completions"))


def _status_error(code: int) -> APIStatusError:
    """构造指定状态码的 API 错误。"""
    req = httpx.Request("POST", "https://api.deepseek.com/v1/chat/completions")
    resp = httpx.Response(code, request=req)
    return APIStatusError("err", response=resp, body=None)


def test_chat_json_retries_transient_then_succeeds(monkeypatch):
    """瞬时错误（连接失败）后重试成功，返回内容。"""
    client, calls = _fake_client([_conn_error(), _fake_response_obj('{"ok": true}')])
    monkeypatch.setattr(llm, "_get_client", lambda: client)
    monkeypatch.setattr(llm, "_model_id", lambda: "test-model")

    result = llm._chat_json("sys", "user", retries=2)
    assert result == '{"ok": true}'
    assert calls["n"] == 2  # 第一次失败 + 一次重试


def test_chat_json_retries_429(monkeypatch):
    """429 限流视为可重试，重试后成功。"""
    client, calls = _fake_client([_status_error(429), _fake_response_obj('{"ok": true}')])
    monkeypatch.setattr(llm, "_get_client", lambda: client)
    monkeypatch.setattr(llm, "_model_id", lambda: "test-model")

    result = llm._chat_json("sys", "user", retries=2)
    assert result == '{"ok": true}'
    assert calls["n"] == 2


def test_chat_json_no_retry_on_4xx(monkeypatch):
    """4xx 参数错误不重试，直接返回 None。"""
    client, calls = _fake_client([_status_error(400)])
    monkeypatch.setattr(llm, "_get_client", lambda: client)
    monkeypatch.setattr(llm, "_model_id", lambda: "test-model")

    result = llm._chat_json("sys", "user", retries=2)
    assert result is None
    assert calls["n"] == 1  # 未重试


def test_chat_json_all_retries_exhausted(monkeypatch):
    """重试耗尽后返回 None。"""
    client, calls = _fake_client([_conn_error(), _conn_error(), _conn_error()])
    monkeypatch.setattr(llm, "_get_client", lambda: client)
    monkeypatch.setattr(llm, "_model_id", lambda: "test-model")

    result = llm._chat_json("sys", "user", retries=2)
    assert result is None
    assert calls["n"] == 3  # 首次 + 2 次重试
