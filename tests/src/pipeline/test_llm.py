"""
测试 LLM 语义模块 — AI 相关性判断与质量打分。

覆盖：
    - is_ai_related: LLM 优先 / 回退关键词 / 异常降级
    - score_quality: 正常打分 / clamp / 失败返回 None
"""

import json

import pytest

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
