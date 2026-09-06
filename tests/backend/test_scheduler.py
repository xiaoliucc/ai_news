"""
测试 scheduler.py — 定时采集调度器。

覆盖：
    - collect_once() 调用 engine.run() → save_articles() 完整链路（mock）
    - start() 重复调用安全
    - shutdown() 正常关闭
"""

import asyncio
import os
import tempfile

import pytest

from backend import scheduler
from src.engine import EngineResult, SourceStats


# ── helpers ──────────────────────────────────────────────────────────────────

def _make_stats(name: str = "fake", fetched: int = 0) -> SourceStats:
    return SourceStats(name=name, fetched=fetched, elapsed_ms=1)


class FakeArticle:
    """模拟 Article，只提供 save_articles 需要的属性。"""

    def __init__(self, article_id: str):
        self.id = article_id
        self.title = f"Test {article_id}"
        self.url = f"http://example.com/{article_id}"
        self.source = "fake"
        self.summary = "A test article."
        self.author = None
        self.published_at = None
        self.score = 100
        self.tags = ["test"]
        self.language = "en"


class FakeEngine:
    """模拟 NewsEngine，不访问真实 API。"""

    def __init__(self, articles=None):
        self._articles = articles or []
        self.run_called = False
        self.source_classes = []

    async def run(self, limit):
        self.run_called = True
        self.run_limit = limit
        return EngineResult(
            articles=self._articles,
            source_stats=[_make_stats(fetched=len(self._articles))],
            deduped_count=0,
            total_elapsed_ms=10,
        )


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


@pytest.fixture
def no_filter(monkeypatch):
    """让 _filter_ai_related 原样返回（跳过真实 LLM 调用）。"""
    async def _identity(articles):
        return articles
    monkeypatch.setattr(scheduler, "_filter_ai_related", _identity)


# ── tests ────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_collect_once_saves_articles(monkeypatch, tmp_db, no_filter):
    """collect_once 应调用 engine.run() 并把结果写入数据库。"""
    fake_articles = [FakeArticle("a1"), FakeArticle("a2")]
    engine = FakeEngine(fake_articles)
    monkeypatch.setattr(scheduler, "NewsEngine", lambda sources: engine)

    await scheduler.collect_once()

    assert engine.run_called
    from backend.database import query_articles
    rows = query_articles(days=999)
    assert len(rows) == 2


@pytest.mark.asyncio
async def test_collect_once_empty_result_no_crash(monkeypatch, tmp_db, no_filter):
    """空采集结果不应崩。"""
    engine = FakeEngine([])
    monkeypatch.setattr(scheduler, "NewsEngine", lambda sources: engine)
    await scheduler.collect_once()  # 不抛异常即通过


@pytest.mark.asyncio
async def test_collect_once_filter_keeps_only_related(monkeypatch, tmp_db):
    """过滤后只有相关文章入库。"""
    articles = [FakeArticle("a1"), FakeArticle("a2"), FakeArticle("a3")]
    engine = FakeEngine(articles)
    monkeypatch.setattr(scheduler, "NewsEngine", lambda sources: engine)

    async def _selective(articles):
        return [a for a in articles if a.id in ("a1", "a3")]

    monkeypatch.setattr(scheduler, "_filter_ai_related", _selective)

    await scheduler.collect_once()

    from backend.database import query_articles
    rows = query_articles(days=999)
    assert {r["id"] for r in rows} == {"a1", "a3"}


@pytest.mark.asyncio
async def test_collect_once_all_filtered_no_save(monkeypatch, tmp_db):
    """全部被过滤时不写库。"""
    engine = FakeEngine([FakeArticle("a1")])
    monkeypatch.setattr(scheduler, "NewsEngine", lambda sources: engine)

    async def _none(articles):
        return []

    monkeypatch.setattr(scheduler, "_filter_ai_related", _none)
    save_calls = []
    monkeypatch.setattr(
        scheduler, "save_articles",
        lambda **kwargs: save_calls.append(kwargs) or 1,
    )

    await scheduler.collect_once()

    assert save_calls == []  # 早退，未调 save_articles


@pytest.mark.asyncio
async def test_collect_once_filter_before_save(monkeypatch, tmp_db):
    """过滤发生在 save 之前：save 收到的是过滤后的列表。"""
    engine = FakeEngine([FakeArticle("a1"), FakeArticle("a2")])
    monkeypatch.setattr(scheduler, "NewsEngine", lambda sources: engine)

    async def _half(articles):
        return articles[:1]

    monkeypatch.setattr(scheduler, "_filter_ai_related", _half)
    captured = {}
    monkeypatch.setattr(
        scheduler, "save_articles",
        lambda articles, **kwargs: captured.update(articles=[a.id for a in articles]) or 1,
    )
    monkeypatch.setattr(
        scheduler, "add_articles",
        lambda articles: len(articles),
    )

    await scheduler.collect_once()

    assert captured["articles"] == ["a1"]


# ── 源选择（selected_sources） ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_collect_once_uses_all_sources_when_none_selected(monkeypatch, tmp_db):
    """selected_sources 为空时实例化全部注册源。"""
    captured = []
    monkeypatch.setattr(
        scheduler, "NewsEngine",
        lambda sources: captured.append([type(s).__name__ for s in sources]) or FakeEngine(),
    )
    await scheduler.collect_once()
    assert captured
    assert len(captured[0]) == len(scheduler.SOURCE_REGISTRY)


@pytest.mark.asyncio
async def test_collect_once_only_selected_sources(monkeypatch, tmp_db):
    """selected_sources 只包含 arxiv 时只实例化 ArxivSource。"""
    from backend.database import set_profile
    set_profile(selected_sources=["arxiv"])

    captured = []
    monkeypatch.setattr(
        scheduler, "NewsEngine",
        lambda sources: captured.append([type(s).__name__ for s in sources]) or FakeEngine(),
    )
    await scheduler.collect_once()
    assert captured[0] == ["ArxivSource"]


@pytest.mark.asyncio
async def test_collect_once_skips_unknown_source_names(monkeypatch, tmp_db):
    """selected_sources 含未知名时静默跳过，不崩。"""
    from backend.database import set_profile
    set_profile(selected_sources=["arxiv", "nonexistent"])

    captured = []
    monkeypatch.setattr(
        scheduler, "NewsEngine",
        lambda sources: captured.append([type(s).__name__ for s in sources]) or FakeEngine(),
    )
    await scheduler.collect_once()
    assert captured[0] == ["ArxivSource"]


@pytest.mark.asyncio
async def test_start_idempotent(monkeypatch):
    """重复调用 start() 不应创建多个调度器。"""
    # Mock AsyncIOScheduler 的 add_job 接受关键字参数
    monkeypatch.setattr(
        scheduler.AsyncIOScheduler,
        "add_job",
        lambda self, func, trigger=None, **kwargs: None,
    )
    monkeypatch.setattr(scheduler.AsyncIOScheduler, "start", lambda self: None)
    monkeypatch.setattr(scheduler.AsyncIOScheduler, "shutdown", lambda self, wait: None)

    scheduler.start()
    s1 = scheduler._scheduler
    scheduler.start()
    s2 = scheduler._scheduler
    assert s1 is s2

    scheduler._scheduler = None  # cleanup without real shutdown


def test_shutdown_cleans_up():
    """shutdown() 后 _scheduler 应为 None。"""
    shutdown_called = False

    class FakeScheduler:
        def shutdown(self, wait):
            nonlocal shutdown_called
            shutdown_called = True

    scheduler._scheduler = FakeScheduler()
    scheduler.shutdown()
    assert shutdown_called
    assert scheduler._scheduler is None


def test_shutdown_noop_when_not_started():
    """未启动时调用 shutdown 不应报错。"""
    scheduler._scheduler = None
    scheduler.shutdown()  # 不抛异常


# ── ranking v2：judge_article 过滤 + quality 写回 ─────────────────────────────

@pytest.mark.asyncio
async def test_filter_ai_related_writes_quality(monkeypatch):
    """过滤保留的文章带上 LLM 质量分（ranking v2 入库数据）。"""
    from backend.scheduler import _filter_ai_related
    from src.models import Article

    arts = []
    for i, ok in enumerate([True, False, True]):
        arts.append(Article(
            id=f"v{i}", title="AI 相关" if ok else "not ai",
            url=f"https://x/{i}", source="mock", summary=None,
            author=None, published_at=None, score=1, tags=[], language="en",
        ))
    verdicts = iter([(True, 80), (False, 20), (True, None)])
    monkeypatch.setattr(scheduler.llm, "judge_article", lambda a: next(verdicts))

    kept = await _filter_ai_related(arts)
    assert [a.id for a in kept] == ["v0", "v2"]
    assert kept[0].quality == 80
    assert kept[1].quality is None  # 判相关但 LLM 未给质量分
