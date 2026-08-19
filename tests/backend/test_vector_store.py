"""
测试向量存储层 — ChromaDB 向量索引。

覆盖：
    - _document / _metadata 文本 & metadata 构建
    - _get_collection 单例 + 错误降级
    - add_articles / delete_article / search / clear CRUD
    - _reset 全局缓存清理
"""

import threading
from unittest.mock import MagicMock, patch

import pytest

from backend import vector_store
from src.models import Article


# ── helpers ──────────────────────────────────────────────────────────────────

def _make_article(
    article_id: str = "arxiv_2401.00001",
    title: str = "Test Paper on LLM",
    source: str = "arxiv",
    score: int = 100,
    summary: str | None = "A test paper about large language models.",
    tags: list[str] | None = None,
    published_at: str | None = None,
) -> Article:
    """快速创建测试用 Article。"""
    from datetime import datetime

    pub = datetime.fromisoformat(published_at) if published_at else None
    return Article(
        id=article_id,
        title=title,
        url=f"https://example.com/{article_id}",
        source=source,
        summary=summary,
        author="Test Author",
        published_at=pub,
        score=score,
        tags=tags or ["LLM"],
        language="en",
    )


def _mock_collection() -> MagicMock:
    """创建一个模拟 ChromaDB collection。"""
    col = MagicMock()
    col.query.return_value = {
        "ids": [["arxiv_2401.00001", "arxiv_2401.00002"]],
        "metadatas": [[
            {"title": "Paper A", "source": "arxiv", "score": 100,
             "published_at": 1754006400.0,
             "url": "https://example.com/a"},
            {"title": "Paper B", "source": "hackernews", "score": 50,
             "published_at": 1754092800.0,
             "url": "https://example.com/b"},
        ]],
        "distances": [[0.1, 0.3]],
    }
    col.get.return_value = {"ids": ["a", "b"]}
    return col


# ── fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def mock_col():
    """注入模拟 collection 到全局缓存，测试后重置。"""
    col = _mock_collection()
    original = vector_store._collection
    vector_store._collection = col
    yield col
    vector_store._collection = original


@pytest.fixture(autouse=True)
def reset_after():
    """每个测试后清理全局状态。"""
    yield
    vector_store._reset()


# ── _document ────────────────────────────────────────────────────────────────

def test_document_full():
    """有标题、摘要和标签时拼接完整文本。"""
    a = _make_article(title="Attention Is All You Need",
                      summary="We propose Transformer.",
                      tags=["NLP", "Transformer"])
    doc = vector_store._document(a)
    assert "Attention Is All You Need" in doc
    assert "We propose Transformer." in doc
    assert "NLP Transformer" in doc


def test_document_no_summary():
    """无摘要时只含标题和标签。"""
    a = _make_article(summary=None, tags=["CV"])
    doc = vector_store._document(a)
    assert "Test Paper on LLM" in doc
    assert "CV" in doc
    assert "\n\n" not in doc  # 无多余空行


def test_document_no_tags():
    """无标签时只含标题和摘要。"""
    a = _make_article(tags=[])
    doc = vector_store._document(a)
    assert "A test paper about large language models." in doc
    assert "Test Paper on LLM" in doc


# ── _metadata ────────────────────────────────────────────────────────────────

def test_metadata_full():
    """有发布时间时存为 Unix 时间戳。"""
    a = _make_article(published_at="2026-08-01T12:00:00+00:00")
    meta = vector_store._metadata(a)
    assert meta["title"] == "Test Paper on LLM"
    assert meta["source"] == "arxiv"
    assert meta["score"] == 100
    assert isinstance(meta["published_at"], float)
    assert meta["published_at"] > 0
    assert meta["url"] == "https://example.com/arxiv_2401.00001"


def test_metadata_no_published_at():
    """无发布时间时 published_at 为 0.0。"""
    a = _make_article()
    meta = vector_store._metadata(a)
    assert meta["published_at"] == 0.0


# ── _get_collection ──────────────────────────────────────────────────────────


@pytest.fixture
def _mock_chroma_init(monkeypatch):
    """Mock PersistentClient + _get_embedding_fn 让 _get_collection 免网络。"""
    vector_store._reset()
    mock_ef = MagicMock()
    monkeypatch.setattr(vector_store, "_get_embedding_fn", lambda: mock_ef)
    mock_client_cls = MagicMock()
    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client
    monkeypatch.setattr(vector_store, "PersistentClient", mock_client_cls)
    return mock_client


def test_get_collection_singleton(_mock_chroma_init):
    """同一线程多次调用返回同一实例。"""
    col1 = vector_store._get_collection()
    col2 = vector_store._get_collection()
    assert col1 is col2
    assert col1 is not None


def test_get_collection_returns_none_when_chromadb_missing(monkeypatch):
    """chromadb 未安装时返回 None。"""
    vector_store._reset()
    monkeypatch.setattr(vector_store, "PersistentClient", None)
    assert vector_store._get_collection() is None


def test_get_collection_returns_none_on_init_failure(monkeypatch):
    """PersistentClient 抛异常时返回 None。"""
    vector_store._reset()
    mock_ef = MagicMock()
    monkeypatch.setattr(vector_store, "_get_embedding_fn", lambda: mock_ef)
    mock_client_cls = MagicMock(side_effect=RuntimeError("disk full"))
    monkeypatch.setattr(vector_store, "PersistentClient", mock_client_cls)
    assert vector_store._get_collection() is None


def test_get_collection_returns_none_when_embedding_fn_fails(monkeypatch):
    """嵌入函数不可用时 _get_collection 返回 None（而非创建无嵌入的 collection）。"""
    vector_store._reset()
    monkeypatch.setattr(vector_store, "_get_embedding_fn", lambda: None)
    mock_client_cls = MagicMock()
    monkeypatch.setattr(vector_store, "PersistentClient", mock_client_cls)
    assert vector_store._get_collection() is None
    # PersistentClient 被创建了，但不应调 get_or_create_collection
    mock_client_cls.return_value.get_or_create_collection.assert_not_called()


def test_get_embedding_fn_returns_none_on_failure(monkeypatch):
    """嵌入函数初始化失败时返回 None（不阻断 collection 创建）。"""
    vector_store._reset()
    monkeypatch.setattr(
        vector_store.embedding_functions,
        "SentenceTransformerEmbeddingFunction",
        MagicMock(side_effect=ImportError("no module")),
    )
    # 重置全局 _embedding_fn 以触发惰性初始化
    vector_store._embedding_fn = None
    assert vector_store._get_embedding_fn() is None


def test_get_embedding_fn_singleton(monkeypatch):
    """嵌入函数只创建一次（惰性单例）。"""
    vector_store._embedding_fn = None
    mock_ef_cls = MagicMock()
    monkeypatch.setattr(
        vector_store.embedding_functions,
        "SentenceTransformerEmbeddingFunction",
        mock_ef_cls,
    )
    ef1 = vector_store._get_embedding_fn()
    ef2 = vector_store._get_embedding_fn()
    assert ef1 is ef2
    mock_ef_cls.assert_called_once()


def test_get_collection_thread_safety():
    """并发访问验证锁存在且可用。"""
    vector_store._reset()
    # 直接验证锁对象存在且可并发 acquire
    assert vector_store._collection_lock is not None
    acquired = vector_store._collection_lock.acquire(blocking=False)
    assert acquired
    vector_store._collection_lock.release()

    results = []

    def _use_lock():
        with vector_store._collection_lock:
            results.append(1)

    threads = [threading.Thread(target=_use_lock) for _ in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(results) == 10


# ── add_articles ─────────────────────────────────────────────────────────────

def test_add_articles_success(mock_col):
    """正常写入调用 collection.upsert 并返回条数。"""
    articles = [_make_article(f"arxiv_2401.{i:05d}") for i in range(3)]
    count = vector_store.add_articles(articles)
    assert count == 3
    assert mock_col.upsert.called


def test_add_articles_collection_none(monkeypatch):
    """collection 不可用时返回 0，不抛异常。"""
    monkeypatch.setattr(vector_store, "_collection", None)
    articles = [_make_article()]
    assert vector_store.add_articles(articles) == 0


def test_add_articles_empty_list(mock_col):
    """空列表时返回 0，不调 upsert。"""
    assert vector_store.add_articles([]) == 0
    mock_col.upsert.assert_not_called()


def test_add_articles_upsert_exception(mock_col):
    """upsert 失败时返回 0，不抛异常。"""
    mock_col.upsert.side_effect = RuntimeError("write error")
    assert vector_store.add_articles([_make_article()]) == 0


# ── delete_article ───────────────────────────────────────────────────────────

def test_delete_article_success(mock_col):
    """正常删除调用 collection.delete。"""
    vector_store.delete_article("arxiv_2401.00001")
    mock_col.delete.assert_called_once_with(ids=["arxiv_2401.00001"])


def test_delete_article_collection_none(monkeypatch):
    """collection 不可用时静默返回。"""
    monkeypatch.setattr(vector_store, "_collection", None)
    # 不应抛异常
    vector_store.delete_article("arxiv_2401.00001")


def test_delete_article_exception(mock_col):
    """delete 失败时静默返回。"""
    mock_col.delete.side_effect = RuntimeError("delete error")
    vector_store.delete_article("arxiv_2401.00001")  # 不抛异常


# ── search ───────────────────────────────────────────────────────────────────

def test_search_basic(mock_col):
    """基本语义搜索返回命中列表。"""
    hits = vector_store.search("multi-modal learning", limit=5)
    assert len(hits) == 2
    assert hits[0]["id"] == "arxiv_2401.00001"
    assert hits[0]["title"] == "Paper A"
    assert hits[0]["distance"] == 0.1
    # 验证传给 ChromaDB 的参数
    mock_col.query.assert_called_once()
    call_kwargs = mock_col.query.call_args.kwargs
    assert call_kwargs["query_texts"] == ["multi-modal learning"]
    assert call_kwargs["n_results"] == 5


def test_search_with_source_filter(mock_col):
    """按 source 过滤。"""
    vector_store.search("test", source="arxiv")
    call_kwargs = mock_col.query.call_args.kwargs
    assert call_kwargs["where"] == {"source": "arxiv"}


def test_search_with_days_filter(mock_col):
    """按 days 时间范围过滤。"""
    vector_store.search("test", days=7)
    call_kwargs = mock_col.query.call_args.kwargs
    where = call_kwargs["where"]
    assert "published_at" in where
    assert "$gte" in where["published_at"]


def test_search_with_both_filters(mock_col):
    """同时按 source + days 过滤时使用 $and。"""
    vector_store.search("test", source="arxiv", days=7)
    call_kwargs = mock_col.query.call_args.kwargs
    where = call_kwargs["where"]
    assert "$and" in where
    assert len(where["$and"]) == 2


def test_search_empty_query(mock_col):
    """空查询返回空列表，不调 ChromaDB。"""
    hits = vector_store.search("   ", limit=5)
    assert hits == []
    mock_col.query.assert_not_called()


def test_search_collection_none(monkeypatch):
    """collection 不可用时返回空列表。"""
    monkeypatch.setattr(vector_store, "_collection", None)
    assert vector_store.search("test") == []


def test_search_exception(mock_col):
    """ChromaDB query 失败时返回空列表。"""
    mock_col.query.side_effect = RuntimeError("index corrupt")
    assert vector_store.search("test") == []


# ── clear ────────────────────────────────────────────────────────────────────

def test_clear_success(mock_col):
    """清空后返回删除条数。"""
    count = vector_store.clear()
    assert count == 2
    mock_col.delete.assert_called_once_with(ids=["a", "b"])


def test_clear_no_ids(mock_col):
    """无文章时返回 0。"""
    mock_col.get.return_value = {"ids": []}
    assert vector_store.clear() == 0
    mock_col.delete.assert_not_called()


def test_clear_collection_none(monkeypatch):
    """collection 不可用时返回 0。"""
    monkeypatch.setattr(vector_store, "_collection", None)
    assert vector_store.clear() == 0


def test_clear_exception(mock_col):
    """delete 失败时返回 0。"""
    mock_col.delete.side_effect = RuntimeError("delete error")
    assert vector_store.clear() == 0


# ── _reset ───────────────────────────────────────────────────────────────────

def test_reset_clears_collection():
    """_reset 后全局 collection 恢复为 None。"""
    vector_store._collection = MagicMock()
    vector_store._reset()
    assert vector_store._collection is None
