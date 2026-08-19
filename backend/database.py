import json
import sqlite3
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from .config import SQLITE_PATH
from src.engine import SourceStats
from src.models import Article

logger = logging.getLogger(__name__)
SCHEMA = """
CREATE TABLE IF NOT EXISTS articles (
    id            TEXT PRIMARY KEY,
    title         TEXT NOT NULL,
    url           TEXT NOT NULL,
    source        TEXT NOT NULL,
    summary       TEXT,
    author        TEXT,
    published_at  TEXT,
    score         INTEGER NOT NULL DEFAULT 0,
    tags          TEXT NOT NULL DEFAULT '[]',
    language      TEXT NOT NULL DEFAULT 'en',
    collected_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS collection_runs (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at     TEXT NOT NULL,
    finished_at    TEXT,
    status         TEXT NOT NULL DEFAULT 'running',
    total_articles INTEGER NOT NULL DEFAULT 0,
    deduped_count  INTEGER NOT NULL DEFAULT 0,
    source_stats   TEXT,
    error          TEXT
);

CREATE TABLE IF NOT EXISTS user_profile (
    id              INTEGER PRIMARY KEY CHECK (id = 1),
    interests       TEXT NOT NULL DEFAULT '[]',
    reading_history TEXT NOT NULL DEFAULT '[]',
    selected_sources TEXT NOT NULL DEFAULT '[]',
    language        TEXT NOT NULL DEFAULT 'zh',
    updated_at      TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_articles_source ON articles(source);
CREATE INDEX IF NOT EXISTS idx_articles_published_at ON articles(published_at);
"""


def _migrate_user_profile(conn: sqlite3.Connection) -> None:
    """为已存在的 user_profile 表补 selected_sources 列。

    旧库的 user_profile 表在 SCHEMA 增加该列之前创建，CREATE TABLE IF NOT EXISTS
    不会补列，需用 ALTER TABLE 迁移，否则 get_profile 会因列不存在报错。

    Args:
        conn: 已打开的数据库连接。
    """
    columns = {
        row["name"]
        for row in conn.execute("PRAGMA table_info(user_profile)").fetchall()
    }
    if "selected_sources" not in columns:
        conn.execute(
            "ALTER TABLE user_profile "
            "ADD COLUMN selected_sources TEXT NOT NULL DEFAULT '[]'"
        )
        logger.info("Migrated user_profile: added selected_sources column")


def _get_connection() -> sqlite3.Connection:
    """
    Get a connection to the database.
    """
    SQLITE_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(SQLITE_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db() -> None:
    """初始化数据库：建表 + 迁移旧库。"""
    with _get_connection() as conn:
        conn.executescript(SCHEMA)
        _migrate_user_profile(conn)
    logger.info(f"Database initialized at {SQLITE_PATH}")

# 首次导入时自动建表
init_db()

def _row_to_dict(row: sqlite3.Row) -> dict:
    """将 sqlite3.Row 转为普通 dict，并还原 JSON 列（tags 等）。

    Args:
        row: sqlite3.Row 查询结果。

    Returns:
        dict: 转换后的字典，tags 已还原为 list。
    """
    d = dict(row)
    try:
        d["tags"] = json.loads(d["tags"])
    except (json.JSONDecodeError, TypeError):
        d["tags"] = []
    return d


def save_articles(
        articles: list[Article],
        source_stats: list[SourceStats],
        deduped_count: int,
) -> Optional[int]:
    """批量保存文章到数据库，并记录一次采集运行。

    Args:
        articles: 待保存的文章列表。
        source_stats: 各数据源采集统计。
        deduped_count: 本次被去重消除的条数。

    Returns:
        Optional[int]: 采集运行 ID；保存失败或文章列表为空时返回 None。
    """
    logger.info(f"Saving {len(articles)} articles to database...")
    if not articles:
        logger.warning("No articles to save")
        return None

    now_time = datetime.now(timezone.utc).isoformat()
    run_id = None
    try:
        with _get_connection() as conn:
            logger.debug("Inserting collection run record...")
            cur = conn.execute(
                "INSERT INTO collection_runs (started_at, finished_at, status, total_articles, deduped_count, source_stats, error) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    now_time,
                    now_time,
                    "finished",
                    len(articles),
                    deduped_count,
                    SourceStats.list_to_json(source_stats),
                    None,
                )
            )
            run_id = cur.lastrowid
            rows = []
            for a in articles:
                rows.append((
                    a.id,
                    a.title,
                    a.url,
                    a.source,
                    a.summary,
                    a.author,
                    a.published_at.isoformat() if a.published_at else None,
                    a.score,
                    json.dumps(a.tags),
                    a.language,
                    now_time,
                ))
            conn.executemany(
                """INSERT OR REPLACE INTO articles
                   (id, title, url, source, summary, author,
                    published_at, score, tags, language, collected_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                rows,
            )
    except Exception as e:
        logger.error("Failed to save articles: %s", e)
        return None
    logger.info("Saved %d articles, run_id=%d", len(articles), run_id)
    return run_id

def query_articles(
    days: int = 7,
    sources: list[str] | None = None,
    limit: int = 20,
) -> list[dict]:
    """按采集时间查询最近 N 天文章，可选按源筛选。

    Args:
        days: 时间范围（天），默认 7 天。
        sources: 源名称列表，如 ["arxiv", "hackernews"]；None 表示全选。
        limit: 最多返回条数。

    Returns:
        list[dict]: 文章字典列表，tags 已还原为 list，按 collected_at DESC, score DESC 排序。
    """
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    sql = "SELECT * FROM articles WHERE collected_at >= ?"
    params: list = [cutoff]

    if sources:
        placeholders = ", ".join(["?"] * len(sources))
        sql += f" AND source IN ({placeholders})"
        params.extend(sources)

    sql += " ORDER BY collected_at DESC, score DESC LIMIT ?"
    params.append(limit)

    with _get_connection() as conn:
        rows = conn.execute(sql, params).fetchall()

    results = [_row_to_dict(row) for row in rows]
    logger.debug("Query articles: days=%d, sources=%s, found %d", days, sources, len(results))
    return results

def get_article(article_id: str) -> dict | None:
    """按 ID 查询单篇文章。

    Args:
        article_id: 文章 ID（如 "arxiv_2401.12345"）。

    Returns:
        dict | None: 文章字典，不存在返回 None。tags 已还原为 list。
    """
    logger.debug("Querying article by ID: %s", article_id)
    try:
        with _get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM articles WHERE id = ?",
                (article_id,)
            ).fetchone()
            if not row:
                logger.debug("Article not found: %s", article_id)
                return None
            return _row_to_dict(row)
    except Exception as e:
        logger.error("Failed to query article %s: %s", article_id, e)
        return None

def get_profile() -> dict:
    """读取用户画像（不存在时自动初始化为默认值）。

    Returns:
        dict: 含 interests / reading_history / language / updated_at 的字典，
            JSON 字段已反序列化为 list。
    """
    logger.debug("Querying user profile...")
    with _get_connection() as conn:
        conn.execute(
            """INSERT OR IGNORE INTO user_profile (id, interests, reading_history, language, updated_at)
               VALUES (1, '[]', '[]', 'zh', ?)""",
            (datetime.now(timezone.utc).isoformat(),)
        )
        row = conn.execute("SELECT * FROM user_profile WHERE id = 1").fetchone()
    result = dict(row)
    for field in ("interests", "reading_history", "selected_sources"):
        try:
            result[field] = json.loads(result[field])
        except (json.JSONDecodeError, TypeError):
            result[field] = []
    return result

def set_profile(
        interests: list[str] | None = None,
        reading_history: list[str] | None = None,
        selected_sources: list[str] | None = None,
        language: str | None = None,
) -> None:
    """部分更新用户画像，只更新传入的非 None 字段。

    Args:
        interests: 用户关注方向列表。
        reading_history: 阅读历史文章 ID 列表（全量覆盖）。
        selected_sources: 启用的数据源列表；空列表表示全选（全量覆盖）。
        language: 回复语言（zh / en）。
    """
    logger.debug("Updating user profile...")
    updates = []
    params = []
    if interests is not None:
        updates.append("interests = ?")
        params.append(json.dumps(interests))
    if reading_history is not None:
        updates.append("reading_history = ?")
        params.append(json.dumps(reading_history))
    if selected_sources is not None:
        updates.append("selected_sources = ?")
        params.append(json.dumps(selected_sources))
    if language is not None:
        updates.append("language = ?")
        params.append(language)
    if not updates:
        return
    updates.append("updated_at = ?")
    params.append(datetime.now(timezone.utc).isoformat())
    params.append(1)

    with _get_connection() as conn:
        # 确保单行存在（直接调用 set_profile 而未先 get_profile 时）
        conn.execute(
            """INSERT OR IGNORE INTO user_profile
               (id, interests, reading_history, selected_sources, language, updated_at)
               VALUES (1, '[]', '[]', '[]', 'zh', ?)""",
            (datetime.now(timezone.utc).isoformat(),),
        )
        conn.execute(
            f"UPDATE user_profile SET {', '.join(updates)} WHERE id = ?",
            params,
        )


def get_source_stats() -> dict[str, int]:
    """按数据源统计文章数量。

    Returns:
        dict[str, int]: {source_name: article_count}，无数据时返回空 dict。
    """
    with _get_connection() as conn:
        rows = conn.execute(
            "SELECT source, COUNT(*) as cnt FROM articles GROUP BY source"
        ).fetchall()
    return {row["source"]: row["cnt"] for row in rows}

def get_collection_stats(limit: int = 10) -> dict:
    """返回采集运行统计：总次数、总文章数、最近采集时间、最近 N 次明细。

    Args:
        limit: 返回的最近采集运行明细条数，默认 10。

    Returns:
        dict: {"total_runs", "total_articles", "last_collection_at", "runs": [...]}
    """
    with _get_connection() as conn:
        total_runs = conn.execute(
            "SELECT COUNT(*) FROM collection_runs"
        ).fetchone()[0]
        total_articles = conn.execute(
            "SELECT SUM(total_articles) FROM collection_runs"
        ).fetchone()[0] or 0
        last_run_time = conn.execute(
            "SELECT finished_at FROM collection_runs ORDER BY finished_at DESC LIMIT 1"
        ).fetchone()
        rows = conn.execute(
            "SELECT * FROM collection_runs ORDER BY started_at DESC LIMIT ?",
            (limit,)
        ).fetchall()

    runs = []
    for row in rows:
        d = dict(row)
        if d["source_stats"]:
            try:
                d["source_stats"] = [
                    s.to_dict() for s in SourceStats.list_from_json(d["source_stats"])
                ]
            except (json.JSONDecodeError, TypeError):
                d["source_stats"] = []
        else:
            d["source_stats"] = []
        runs.append(d)

    return {
        "total_runs": total_runs,
        "total_articles": total_articles,
        "last_collection_at": last_run_time["finished_at"] if last_run_time else None,
        "runs": runs,
    }
