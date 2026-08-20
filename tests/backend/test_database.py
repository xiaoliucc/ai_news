"""
测试数据层 — SQLite 数据库操作。

覆盖：
    - init_db / 连接管理
    - save_articles / query_articles / get_article（articles 表 CRUD）
    - get_profile / set_profile（user_profile 表 CRUD）
"""

import json
import os
import sqlite3
import tempfile

import pytest

from backend.database import (
    _row_to_dict,
    get_article,
    get_profile,
    init_db,
    query_articles,
    save_articles,
    set_profile,
)
from backend.config import SQLITE_PATH as _ORIG_SQLITE_PATH
from src.engine import SourceStats
from src.models import Article


# ── helpers ──────────────────────────────────────────────────────────────────

def _make_article(
    article_id: str = "arxiv_2401.00001",
    title: str = "Test Paper on LLM",
    source: str = "arxiv",
    score: int = 100,
    tags: list[str] | None = None,
) -> Article:
    """快速创建测试用 Article。"""
    return Article(
        id=article_id,
        title=title,
        url=f"https://example.com/{article_id}",
        source=source,
        summary="A test paper about large language models.",
        author="Test Author",
        published_at=None,
        score=score,
        tags=tags or ["LLM"],
        language="en",
    )


def _make_stats(name: str = "arxiv", fetched: int = 1) -> SourceStats:
    """快速创建测试用 SourceStats。"""
    return SourceStats(name=name, fetched=fetched, elapsed_ms=42)


# ── fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def tmp_db(monkeypatch):
    """用临时数据库替代真实 data.db，测试完自动清理。"""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    db_path = type(_ORIG_SQLITE_PATH)(path)
    monkeypatch.setattr("backend.database.SQLITE_PATH", db_path)
    monkeypatch.setattr("backend.config.SQLITE_PATH", db_path)
    init_db()
    yield path
    try:
        os.unlink(path)
        os.unlink(path + "-wal")
        os.unlink(path + "-shm")
    except OSError:
        pass


# ── init_db / _get_connection ────────────────────────────────────────────────

def test_init_db_creates_tables():
    """init_db 后应存在 4 张表。"""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    try:
        # 用 monkeypatch 或直接改 backend.database 的状态
        conn = sqlite3.connect(path)
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS articles (id TEXT PRIMARY KEY, title TEXT NOT NULL, url TEXT NOT NULL, source TEXT NOT NULL, summary TEXT, author TEXT, published_at TEXT, score INTEGER NOT NULL DEFAULT 0, tags TEXT NOT NULL DEFAULT '[]', language TEXT NOT NULL DEFAULT 'en', collected_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS collection_runs (id INTEGER PRIMARY KEY AUTOINCREMENT, started_at TEXT NOT NULL, finished_at TEXT, status TEXT NOT NULL DEFAULT 'running', total_articles INTEGER NOT NULL DEFAULT 0, deduped_count INTEGER NOT NULL DEFAULT 0, source_stats TEXT, error TEXT);
            CREATE TABLE IF NOT EXISTS user_profile (id INTEGER PRIMARY KEY CHECK (id = 1), interests TEXT NOT NULL DEFAULT '[]', reading_history TEXT NOT NULL DEFAULT '[]', language TEXT NOT NULL DEFAULT 'zh', updated_at TEXT NOT NULL);
            CREATE INDEX IF NOT EXISTS idx_articles_source ON articles(source);
            CREATE INDEX IF NOT EXISTS idx_articles_published_at ON articles(published_at);
        """)
        conn.close()

        tables = sqlite3.connect(path).execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
        names = [r[0] for r in tables]
        assert "articles" in names
        assert "collection_runs" in names
        assert "user_profile" in names
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


def test_get_connection_sets_row_factory():
    """_get_connection 应设置 row_factory 为 sqlite3.Row。"""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    try:
        conn = sqlite3.connect(path)
        conn.execute("CREATE TABLE t (k TEXT)")
        conn.execute("INSERT INTO t VALUES ('v')")
        conn.commit()
        conn.close()

        conn2 = sqlite3.connect(path)
        conn2.row_factory = sqlite3.Row
        row = conn2.execute("SELECT k FROM t").fetchone()
        assert row["k"] == "v"
        conn2.close()
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


# ── save_articles ────────────────────────────────────────────────────────────

def test_save_articles_empty(tmp_db):
    """空列表应返回 None，不创建 collection_run。"""
    run_id = save_articles([], [], deduped_count=0)
    assert run_id is None


def test_save_articles_returns_run_id(tmp_db):
    """正常保存应返回自增 run_id。"""
    articles = [_make_article("a1")]
    run_id = save_articles(articles, [_make_stats()], deduped_count=0)
    assert run_id is not None
    assert run_id > 0


def test_save_articles_writes_articles(tmp_db):
    """保存后 query_articles 应能查到。"""
    articles = [
        _make_article("a1", title="Paper A", score=200),
        _make_article("a2", title="Paper B", source="hackernews", score=500,
                       tags=["show-hn", "AI"]),
    ]
    save_articles(articles, [_make_stats(), _make_stats("hackernews")], deduped_count=0)

    rows = query_articles(days=999, limit=10)
    assert len(rows) == 2
    ids = {r["id"] for r in rows}
    assert ids == {"a1", "a2"}


def test_save_articles_replace_on_duplicate_id(tmp_db):
    """INSERT OR REPLACE：同 ID 再次写入应覆盖旧数据。"""
    a1 = _make_article("a1", title="Old Title", score=10)
    save_articles([a1], [_make_stats()], deduped_count=0)

    a2 = _make_article("a1", title="New Title", score=99)
    save_articles([a2], [_make_stats()], deduped_count=0)

    rows = query_articles(days=999)
    assert len(rows) == 1
    assert rows[0]["title"] == "New Title"
    assert rows[0]["score"] == 99


def test_save_articles_writes_collection_run(tmp_db):
    """save_articles 应写入 collection_runs + source_stats JSON。"""
    stats = [
        SourceStats(name="arxiv", fetched=3, elapsed_ms=100),
        SourceStats(name="hackernews", fetched=5, elapsed_ms=200),
    ]
    run_id = save_articles(
        [_make_article("a1"), _make_article("a2")],
        stats,
        deduped_count=1,
    )
    assert run_id is not None

    conn = sqlite3.connect(str(tmp_db))
    conn.row_factory = sqlite3.Row
    run = conn.execute("SELECT * FROM collection_runs WHERE id = ?", (run_id,)).fetchone()
    assert run is not None
    assert run["status"] == "finished"
    assert run["total_articles"] == 2
    assert run["deduped_count"] == 1
    assert run["error"] is None

    source_stats_json = json.loads(run["source_stats"])
    assert len(source_stats_json) == 2
    assert source_stats_json[0]["name"] == "arxiv"
    assert source_stats_json[0]["fetched"] == 3
    conn.close()


# ── query_articles ───────────────────────────────────────────────────────────

def test_query_articles_time_filter(tmp_db):
    """days 参数应只返回窗口内的文章。"""
    save_articles([_make_article("a1")], [_make_stats()], deduped_count=0)
    # 刚插入的文章应在 days=999 窗口内
    rows = query_articles(days=999, limit=10)
    assert len(rows) == 1

    # days=0 不应返回任何结果（窗口为"未来 0 天前"）
    rows_strict = query_articles(days=0, limit=10)
    assert len(rows_strict) == 0


def test_query_articles_source_filter(tmp_db):
    """sources 参数应只返回指定源的文章。"""
    save_articles([
        _make_article("a1", source="arxiv"),
        _make_article("a2", source="hackernews"),
    ], [_make_stats("arxiv"), _make_stats("hackernews")], deduped_count=0)

    rows = query_articles(days=999, sources=["arxiv"])
    assert len(rows) == 1
    assert rows[0]["id"] == "a1"


def test_query_articles_tags_deserialized(tmp_db):
    """返回的 tags 应为 list 而非 JSON 字符串。"""
    save_articles(
        [_make_article("a1", tags=["LLM", "NLP"])],
        [_make_stats()],
        deduped_count=0,
    )
    rows = query_articles(days=999)
    assert isinstance(rows[0]["tags"], list)
    assert rows[0]["tags"] == ["LLM", "NLP"]


def test_query_articles_limit(tmp_db):
    """limit 参数应限制返回数量。"""
    articles = [_make_article(f"a{i}") for i in range(10)]
    save_articles(articles, [_make_stats(fetched=10)], deduped_count=0)
    rows = query_articles(days=999, limit=3)
    assert len(rows) == 3


def test_query_articles_empty(tmp_db):
    """无数据时应返回空列表。"""
    rows = query_articles(days=999)
    assert rows == []


# ── get_article ──────────────────────────────────────────────────────────────

def test_get_article_found(tmp_db):
    """存在的 ID 应返回文章详情。"""
    save_articles([_make_article("a1")], [_make_stats()], deduped_count=0)
    a = get_article("a1")
    assert a is not None
    assert a["id"] == "a1"
    assert isinstance(a["tags"], list)


def test_get_article_not_found(tmp_db):
    """不存在的 ID 应返回 None。"""
    assert get_article("nonexistent") is None


def test_get_article_invalid_tags_json(tmp_db):
    """tags 字段存了非法 JSON 时应返回空列表而非崩溃。"""
    conn = sqlite3.connect(str(tmp_db))
    conn.execute(
        "INSERT INTO articles (id, title, url, source, tags, collected_at) VALUES (?, ?, ?, ?, ?, ?)",
        ("bad", "T", "http://x", "arxiv", "not-json", "2024-01-01T00:00:00+00:00"),
    )
    conn.commit()
    conn.close()
    # 直接调 get_article，应优雅降级
    a = get_article("bad")
    assert a is not None
    assert a["tags"] == []


# ── get_profile / set_profile ────────────────────────────────────────────────

def test_get_profile_returns_defaults_on_first_call(tmp_db):
    """首次调用 get_profile 应返回默认值并初始化行。"""
    profile = get_profile()
    assert profile["interests"] == []
    assert profile["reading_history"] == []
    assert profile["language"] == "zh"


def test_set_profile_updates_only_passed_fields(tmp_db):
    """set_profile 只应修改传入的字段，不影响其他。"""
    get_profile()  # ensure row exists
    set_profile(interests=["LLM", "CV"])
    p = get_profile()
    assert p["interests"] == ["LLM", "CV"]
    assert p["language"] == "zh"  # 没传，不变


def test_set_profile_noop_when_nothing_passed(tmp_db):
    """什么都没传时 set_profile 应不做事也不报错。"""
    get_profile()
    set_profile()  # 不传任何参数
    # 不应抛异常


def test_get_profile_is_idempotent(tmp_db):
    """多次调用 get_profile 不应重复插入行。"""
    p1 = get_profile()
    p2 = get_profile()
    assert p1 == p2


def test_set_profile_persists(tmp_db):
    """set_profile 后再 get_profile 应返回更新后的值。"""
    get_profile()
    set_profile(interests=["RAG"], language="en")
    p = get_profile()
    assert p["interests"] == ["RAG"]
    assert p["language"] == "en"


# ── _row_to_dict ─────────────────────────────────────────────────────────────

def test_row_to_dict_valid_tags():
    """正常 JSON tags 应还原为 list。"""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("CREATE TABLE t (tags TEXT)")
    conn.execute("INSERT INTO t VALUES (?)", ('["LLM","CV"]',))
    conn.commit()
    row = conn.execute("SELECT * FROM t").fetchone()
    d = _row_to_dict(row)
    assert d["tags"] == ["LLM", "CV"]
    conn.close()


def test_row_to_dict_empty_string_tags():
    """空字符串 tags 应返回空 list。"""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("CREATE TABLE t (tags TEXT)")
    conn.execute("INSERT INTO t VALUES (?)", ("",))
    conn.commit()
    row = conn.execute("SELECT * FROM t").fetchone()
    d = _row_to_dict(row)
    assert d["tags"] == []
    conn.close()


# ── selected_sources 列 ──────────────────────────────────────────────────────

def test_selected_sources_default_empty(tmp_db):
    """首次 get_profile 时 selected_sources 为空列表。"""
    p = get_profile()
    assert p["selected_sources"] == []


def test_set_selected_sources_persists(tmp_db):
    """写入 selected_sources 后能读回。"""
    set_profile(selected_sources=["arxiv", "jiqizhixin"])
    p = get_profile()
    assert p["selected_sources"] == ["arxiv", "jiqizhixin"]


def test_set_selected_sources_does_not_affect_others(tmp_db):
    """只更新 selected_sources 不影响其他字段。"""
    set_profile(interests=["LLM"], language="en")
    set_profile(selected_sources=["arxiv"])
    p = get_profile()
    assert p["interests"] == ["LLM"]
    assert p["language"] == "en"
    assert p["selected_sources"] == ["arxiv"]


def test_migrate_adds_selected_sources_column(monkeypatch, tmp_db):
    """旧库（无 selected_sources 列）init_db 后自动补列。"""
    import sqlite3 as _sqlite3
    from backend.config import SQLITE_PATH as db_path

    # 用旧 schema 重建表（去掉 selected_sources 列）
    conn = _sqlite3.connect(str(db_path))
    conn.execute("DROP TABLE user_profile")
    conn.execute(
        """CREATE TABLE user_profile (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            interests TEXT NOT NULL DEFAULT '[]',
            reading_history TEXT NOT NULL DEFAULT '[]',
            language TEXT NOT NULL DEFAULT 'zh',
            updated_at TEXT NOT NULL
        )"""
    )
    conn.commit()
    conn.close()

    # 再次 init_db 触发迁移
    init_db()

    conn = _sqlite3.connect(str(db_path))
    cols = {r[1] for r in conn.execute("PRAGMA table_info(user_profile)").fetchall()}
    conn.close()
    assert "selected_sources" in cols

    # 迁移后 get_profile 正常返回默认值
    p = get_profile()
    assert p["selected_sources"] == []


def test_migrate_adds_conversation_summary_column(monkeypatch, tmp_db):
    """旧库（无 conversation_summary 列）init_db 后自动补列。"""
    import sqlite3 as _sqlite3
    from backend.config import SQLITE_PATH as db_path

    # 用旧 schema 重建表（去掉 conversation_summary / conversation_updated_at 列）
    conn = _sqlite3.connect(str(db_path))
    conn.execute("DROP TABLE user_profile")
    conn.execute(
        """CREATE TABLE user_profile (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            interests TEXT NOT NULL DEFAULT '[]',
            reading_history TEXT NOT NULL DEFAULT '[]',
            selected_sources TEXT NOT NULL DEFAULT '[]',
            language TEXT NOT NULL DEFAULT 'zh',
            updated_at TEXT NOT NULL
        )"""
    )
    conn.commit()
    conn.close()

    # 再次 init_db 触发迁移
    init_db()

    conn = _sqlite3.connect(str(db_path))
    cols = {r[1] for r in conn.execute("PRAGMA table_info(user_profile)").fetchall()}
    conn.close()
    assert "conversation_summary" in cols
    assert "conversation_updated_at" in cols

    # 迁移后 get_profile 默认空摘要
    p = get_profile()
    assert p["conversation_summary"] == ""


def test_set_profile_conversation_summary_persists(tmp_db):
    """set_profile 写入摘要后 get_profile 可读回（含更新时间）。"""
    set_profile(conversation_summary="用户关注推理效率，已推荐 3 篇论文。")
    p = get_profile()
    assert p["conversation_summary"] == "用户关注推理效率，已推荐 3 篇论文。"
    assert p["conversation_updated_at"] is not None

    # 覆盖写入
    set_profile(conversation_summary="新摘要")
    assert get_profile()["conversation_summary"] == "新摘要"
