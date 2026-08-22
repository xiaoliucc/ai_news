"""
测试 Agent 工具集 — 工具实现与阅读历史记录。

覆盖：
    - _record_reading_history: 记录 / 去重 / 上限截断
    - _get_article_detail / _summarize_articles 的记录钩子
    - 工具失败路径不记录
"""

import json
import os
import tempfile

import pytest

from backend.agent import tools
from backend.database import get_profile


# ── fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def tmp_db(monkeypatch):
    """用临时数据库替代真实 data.db，测试完自动清理。"""
    from pathlib import Path
    from backend.config import SQLITE_PATH as _orig

    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    db_path = type(_orig)(path)
    monkeypatch.setattr("backend.database.SQLITE_PATH", db_path)
    monkeypatch.setattr("backend.config.SQLITE_PATH", db_path)
    from backend.database import init_db
    init_db()
    yield path
    try:
        os.unlink(path)
        os.unlink(path + "-wal")
        os.unlink(path + "-shm")
    except OSError:
        pass


# ── _record_reading_history ──────────────────────────────────────────────────

def test_record_reading_history_basic(tmp_db):
    """记录 ID 后 get_profile 能读到，新读在前。"""
    tools._record_reading_history(["a1", "a2"])
    profile = get_profile()
    assert profile["reading_history"] == ["a1", "a2"]

    tools._record_reading_history(["a3"])
    profile = get_profile()
    assert profile["reading_history"] == ["a3", "a1", "a2"]


def test_record_reading_history_dedup(tmp_db):
    """重复阅读不重复记录，已读 ID 不改变位置。"""
    tools._record_reading_history(["a1", "a2"])
    tools._record_reading_history(["a2", "a3"])
    profile = get_profile()
    assert profile["reading_history"] == ["a3", "a1", "a2"]


def test_record_reading_history_cap_50(tmp_db):
    """超过 50 条时截断。"""
    ids = [f"a{i}" for i in range(60)]
    tools._record_reading_history(ids)
    profile = get_profile()
    assert len(profile["reading_history"]) == tools.MAX_READING_HISTORY
    # 单次批量保序，前 50 条保留
    assert profile["reading_history"][0] == "a0"
    assert profile["reading_history"][-1] == "a49"


def test_record_reading_history_cap_keeps_newest_reads(tmp_db):
    """截断后新读的排在前面，最旧的被挤出。"""
    ids = [f"a{i}" for i in range(50)]
    tools._record_reading_history(ids)
    tools._record_reading_history(["a50"])
    profile = get_profile()
    assert len(profile["reading_history"]) == tools.MAX_READING_HISTORY
    assert profile["reading_history"][0] == "a50"  # 新读在前
    assert "a49" not in profile["reading_history"]  # 最旧的被挤出


def test_record_reading_history_empty_noop(tmp_db):
    """空列表不写入。"""
    tools._record_reading_history([])
    profile = get_profile()
    assert profile["reading_history"] == []


# ── 工具记录钩子 ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_article_detail_records_history(tmp_db, monkeypatch):
    """查看文章详情后自动记录阅读历史。"""
    fake_article = {"id": "arxiv_1", "title": "Test Paper"}
    monkeypatch.setattr(tools, "db_get_article", lambda aid: fake_article)

    result = await tools._get_article_detail({"article_id": "arxiv_1"})
    assert result["article"]["id"] == "arxiv_1"

    profile = get_profile()
    assert profile["reading_history"] == ["arxiv_1"]


@pytest.mark.asyncio
async def test_get_article_detail_miss_no_record(tmp_db, monkeypatch):
    """文章不存在时不记录。"""
    monkeypatch.setattr(tools, "db_get_article", lambda aid: None)
    monkeypatch.setattr(tools, "db_query_articles", lambda **kw: [])

    result = await tools._get_article_detail({"article_id": "missing"})
    assert "error" in result

    profile = get_profile()
    assert profile["reading_history"] == []


# ── _resolve_article：LLM 把标题当 ID 传时的标题回退 ─────────────────────────

def test_resolve_article_by_id(tmp_db, monkeypatch):
    """按 ID 命中直接返回，不触发标题回退。"""
    fake = {"id": "github_owner/repo", "title": "owner/repo"}
    monkeypatch.setattr(tools, "db_get_article", lambda aid: fake)
    assert tools._resolve_article("github_owner/repo") is fake


@pytest.mark.asyncio
async def test_get_article_detail_title_fallback(tmp_db, monkeypatch):
    """LLM 传标题（如 GitHub owner/repo）而非 ID 时，按标题精确匹配回退。"""
    fake = {"id": "github_AprilNEA/OpenLogi", "title": "AprilNEA/OpenLogi"}
    monkeypatch.setattr(tools, "db_get_article", lambda aid: None)
    monkeypatch.setattr(
        tools, "db_query_articles",
        lambda **kw: [{"id": "arxiv_1", "title": "其他文章"}, fake],
    )

    result = await tools._get_article_detail({"article_id": "AprilNEA/OpenLogi"})
    assert result["article"]["id"] == "github_AprilNEA/OpenLogi"
    # 标题回退命中后仍记录阅读历史（记录真实 ID 而非传入的标题）
    assert get_profile()["reading_history"] == ["github_AprilNEA/OpenLogi"]


@pytest.mark.asyncio
async def test_summarize_articles_title_fallback(tmp_db, monkeypatch):
    """summarize 的 article_ids 传标题时同样按标题回退。"""
    fake = {"id": "github_owner/repo", "title": "owner/repo", "summary": "desc"}
    monkeypatch.setattr(tools, "db_get_article", lambda aid: None)
    monkeypatch.setattr(
        tools, "db_query_articles",
        lambda **kw: [fake],
    )
    monkeypatch.setattr(
        tools, "_chat_json",
        lambda *a, **k: json.dumps({"summaries": [{"id": "github_owner/repo", "summary": "s"}]}),
    )

    result = await tools._summarize_articles({"article_ids": ["owner/repo"]})
    assert "summaries" in result
    assert get_profile()["reading_history"] == ["github_owner/repo"]


@pytest.mark.asyncio
async def test_summarize_articles_records_history(tmp_db, monkeypatch):
    """概括文章后自动记录全部 ID。"""
    articles = [
        {"id": "arxiv_1", "title": "P1", "summary": "s1"},
        {"id": "arxiv_2", "title": "P2", "summary": "s2"},
    ]
    monkeypatch.setattr(
        tools, "db_get_article", lambda aid: next((a for a in articles if a["id"] == aid), None)
    )
    monkeypatch.setattr(
        tools, "_chat_json",
        lambda *a, **k: json.dumps({"summaries": [{"id": "arxiv_1", "summary": "s"}]}),
    )

    result = await tools._summarize_articles({"article_ids": ["arxiv_1", "arxiv_2"]})
    assert "summaries" in result

    profile = get_profile()
    assert profile["reading_history"] == ["arxiv_1", "arxiv_2"]


@pytest.mark.asyncio
async def test_summarize_articles_no_match_no_record(tmp_db, monkeypatch):
    """无匹配文章时不记录。"""
    monkeypatch.setattr(tools, "db_get_article", lambda aid: None)

    result = await tools._summarize_articles({"article_ids": ["missing"]})
    assert "error" in result

    profile = get_profile()
    assert profile["reading_history"] == []


# ── _keyword_fallback（M5: ChromaDB 不可用时的 SQLite 回退检索） ─────────────

def _seed_articles():
    """向临时库写入几篇测试文章。"""
    from src.models import Article
    from backend.database import save_articles
    from src.engine import SourceStats

    articles = [
        Article(
            id="arxiv_1", title="Transformer 大模型研究", url="https://x/1",
            source="arxiv", summary="关于大语言模型的研究", author=None,
            published_at=None, score=50, tags=["LLM"], language="zh",
        ),
        Article(
            id="hn_1", title="Sonic Pi v5", url="https://x/2",
            source="hackernews", summary="A music tool.", author=None,
            published_at=None, score=100, tags=[], language="en",
        ),
        Article(
            id="arxiv_2", title="多模态学习综述", url="https://x/3",
            source="arxiv", summary="多模态模型综述", author=None,
            published_at=None, score=30, tags=["CV"], language="zh",
        ),
        Article(
            id="github_AprilNEA/OpenLogi", title="AprilNEA/OpenLogi", url="https://github.com/AprilNEA/OpenLogi",
            source="github", summary="开源日志工具", author="AprilNEA",
            published_at=None, score=500, tags=["Go"], language="en",
        ),
    ]
    save_articles(articles, [SourceStats(name="x")], 0)


def test_keyword_fallback_matches_keywords(tmp_db):
    """按关键词匹配标题/摘要，按 score 降序。"""
    _seed_articles()
    hits = tools._keyword_fallback("大模型", days=30, source=None, limit=10)
    assert len(hits) == 1
    assert hits[0]["id"] == "arxiv_1"
    assert hits[0]["summary"]


def test_keyword_fallback_with_source_filter(tmp_db):
    """支持来源过滤。"""
    _seed_articles()
    hits = tools._keyword_fallback("多模态", days=30, source="arxiv", limit=10)
    assert len(hits) == 1
    assert hits[0]["id"] == "arxiv_2"


def test_keyword_fallback_no_match(tmp_db):
    """无匹配返回空列表。"""
    _seed_articles()
    hits = tools._keyword_fallback("quantum", days=30, source=None, limit=10)
    assert hits == []


@pytest.mark.asyncio
async def test_search_articles_falls_back_when_chroma_empty(tmp_db, monkeypatch):
    """ChromaDB 检索为空时回退 SQLite 关键词检索。"""
    _seed_articles()
    monkeypatch.setattr(tools, "vs_search", lambda **kw: [])

    result = await tools._search_articles({"query": "大模型", "days": 30})
    assert result["total"] == 1
    assert result["articles"][0]["id"] == "arxiv_1"
    assert result.get("fallback") == "keyword"


@pytest.mark.asyncio
async def test_search_articles_exact_match_by_title(tmp_db, monkeypatch):
    """无空格专有名词 query（如 GitHub 标题）直接精确解析，不走语义检索。"""
    _seed_articles()
    # 即使 ChromaDB 本可返回内容，精确匹配也应优先
    monkeypatch.setattr(tools, "vs_search", lambda **kw: [{"id": "other", "title": "x"}])

    result = await tools._search_articles({"query": "AprilNEA/OpenLogi", "days": 30})
    assert result["total"] == 1
    assert result["articles"][0]["id"] == "github_AprilNEA/OpenLogi"
    assert result.get("exact_match") is True


@pytest.mark.asyncio
async def test_search_articles_exact_match_by_id(tmp_db, monkeypatch):
    """无空格 query 是文章 ID 时直接精确解析。"""
    _seed_articles()

    result = await tools._search_articles({"query": "github_AprilNEA/OpenLogi", "days": 30})
    assert result["total"] == 1
    assert result["articles"][0]["id"] == "github_AprilNEA/OpenLogi"
    assert result.get("exact_match") is True


@pytest.mark.asyncio
async def test_search_articles_exact_miss_goes_semantic(tmp_db, monkeypatch):
    """精确解析未命中时走正常语义检索（不回退出错）。"""
    _seed_articles()
    monkeypatch.setattr(tools, "vs_search", lambda **kw: [])
    monkeypatch.setattr(
        tools, "_keyword_fallback",
        lambda *a, **kw: [{"id": "arxiv_1", "title": "Transformer 大模型研究"}],
    )

    result = await tools._search_articles({"query": "大模型 论文", "days": 30})
    assert result["total"] == 1
    assert result.get("fallback") == "keyword"
