"""
Agent 工具集 — LLM 可调用的函数（tool-use）。

对外提供：
    TOOLS    — OpenAI function calling schema 列表，随请求传给 LLM
    EXECUTOR — {工具名: 异步实现函数}，core.py 按 LLM 返回的工具名查表执行

工具实现状态：
    Phase 2：search_articles / get_article_detail / summarize_articles /
             analyze_trend / trigger_collection 全部可用
"""

import asyncio
import json
from collections.abc import Awaitable, Callable

from backend.database import (
    get_article as db_get_article,
    get_profile as db_get_profile,
    query_articles as db_query_articles,
    set_profile as db_set_profile,
)
from backend.scheduler import collect_once
from backend.vector_store import search as vs_search
from src.pipeline.llm import _chat_json, _strip_code_fence

MAX_READING_HISTORY = 50  # 阅读历史上限（条）


def _record_reading_history(article_ids: list[str]) -> None:
    """把文章 ID 记入 user_profile.reading_history（新读在前，去重，上限截断）。

    Args:
        article_ids: 本次阅读的文章 ID 列表。
    """
    current = db_get_profile().get("reading_history") or []
    seen = set(current)
    fresh = [aid for aid in article_ids if aid not in seen]
    if not fresh:
        return
    updated = fresh + current
    db_set_profile(reading_history=updated[:MAX_READING_HISTORY])


def _keyword_fallback(query: str, days: int, source: str | None, limit: int) -> list[dict]:
    """ChromaDB 不可用时的回退检索：SQLite 查询 + 关键词匹配。

    Args:
        query: 用户查询文本。
        days: 时间范围（天）。
        source: 可选来源过滤。
        limit: 最多返回条数。

    Returns:
        list[dict]: 匹配文章列表（格式与 _search_articles 的语义命中一致）。
    """
    keywords = [w.strip().lower() for w in query.split() if len(w.strip()) >= 2]
    if not keywords:
        return []
    sources = [source] if source else None
    rows = db_query_articles(days=days, sources=sources, limit=200)
    hits = []
    for r in rows:
        text = (
            f"{r['title']} {r.get('summary') or ''} "
            f"{' '.join(r.get('tags') or [])}"
        ).lower()
        if any(kw in text for kw in keywords):
            hits.append({
                "id": r["id"],
                "title": r["title"],
                "source": r["source"],
                "score": r.get("score", 0),
                "summary": (r.get("summary") or "")[:300],
                "distance": None,
            })
    hits.sort(key=lambda x: x["score"], reverse=True)
    return hits[:limit]


TOOLS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "search_articles",
            "description": "语义检索已采集的文章，按主题/关键词/时间范围查询。回答用户关于已采集内容的问题时使用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "自然语言查询，如：最近关于多模态的论文",
                    },
                    "days": {
                        "type": "integer",
                        "description": "时间范围（天），默认 7",
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_article_detail",
            "description": "获取单篇文章的完整内容（标题/摘要/链接/标签）。",
            "parameters": {
                "type": "object",
                "properties": {
                    "article_id": {
                        "type": "string",
                        "description": "文章 ID，如 arxiv_2401.12345",
                    },
                },
                "required": ["article_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "summarize_articles",
            "description": "用 LLM 概括总结一批文章的核心内容，返回每篇的中文摘要。",
            "parameters": {
                "type": "object",
                "properties": {
                    "article_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "文章 ID 列表",
                    }
                },
                "required": ["article_ids"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "analyze_trend",
            "description": "分析某个领域在时间范围内的研究趋势，聚合多篇文章识别热点方向。",
            "parameters": {
                "type": "object",
                "properties": {
                    "topic": {
                        "type": "string",
                        "description": "领域/主题，如 多模态、RAG",
                    },
                    "days": {
                        "type": "integer",
                        "description": "时间范围（天），默认 7",
                    },
                },
                "required": ["topic"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "trigger_collection",
            "description": "手动触发一次数据采集，立即拉取各源最新内容入库。",
            "parameters": {"type": "object", "properties": {}},
        },
    },
]


async def _search_articles(args: dict) -> dict:
    """语义检索文章（ChromaDB 向量检索）。

    Args:
        args: {"query": str, "days"?: int, "limit"?: int, "source"?: str}。

    Returns:
        dict: {"articles": [hit, ...], "total": int, "days_queried": int}。
    """
    query: str = (args.get("query") or "").strip()
    days: int = args.get("days", 7)
    limit: int = args.get("limit", 20)
    source: str | None = args.get("source")

    if not query:
        return {"error": "query 不能为空", "articles": []}

    # to_thread：ChromaDB 首次初始化可能触发嵌入模型下载（阻塞 I/O），
    # 不能让 event loop 卡住
    hits = await asyncio.to_thread(
        vs_search, query=query, days=days, limit=limit, source=source
    )
    # ChromaDB 不可用或无命中时回退 SQLite 关键词检索，数据仍在库里可答
    if not hits:
        fallback = await asyncio.to_thread(
            _keyword_fallback, query, days, source, limit
        )
        return {
            "articles": fallback,
            "total": len(fallback),
            "days_queried": days,
            "fallback": "keyword",
        }
    articles = []
    for h in hits:
        # 从 SQLite 回填摘要——ChromaDB metadata 不存 summary 以节省空间
        detail = db_get_article(h["id"])
        summary = ""
        if detail:
            summary = (detail.get("summary") or "")[:300]
        articles.append({
            "id": h["id"],
            "title": h["title"],
            "source": h["source"],
            "score": h["score"],
            "summary": summary,
            "distance": h.get("distance"),
        })
    return {"articles": articles, "total": len(articles), "days_queried": days}


async def _get_article_detail(args: dict) -> dict:
    """获取文章详情（从 SQLite 查询）。

    Args:
        args: {"article_id": str}，文章 ID。

    Returns:
        dict: {"article": {...}} 或 {"error": str, "article": None}。
    """
    article_id: str = args.get("article_id") or ""
    if not article_id:
        return {"error": "article_id 不能为空", "article": None}
    a = db_get_article(article_id)
    if a is None:
        return {"error": f"文章 ID {article_id} 不存在", "article": None}
    # 用户查看详情 = 已读，隐式记录阅读历史
    _record_reading_history([article_id])
    return {"article": a}


async def _summarize_articles(args: dict) -> dict:
    """用 LLM 概括文章核心内容（从 SQLite 查询文章数据）。

    按 article_ids 从数据库取出文章标题和摘要，调用 LLM 逐篇生成
    中文概括。标题保留原文不翻译。

    Args:
        args: {"article_ids": list[str]}，文章 ID 列表。

    Returns:
        dict: {"summaries": [{"id": str, "summary": str}, ...]} 或含 error 的 dict。
    """
    article_ids = args.get("article_ids") or []
    articles = []
    for aid in article_ids:
        a = db_get_article(aid)
        if a is not None:
            articles.append(a)
    if not articles:
        return {"error": "未找到匹配的文章 ID", "summaries": []}

    # 用户要求概括 = 已读，隐式记录阅读历史
    _record_reading_history([a["id"] for a in articles])

    payload = [
        {"id": a["id"], "title": a["title"], "summary": a.get("summary") or ""}
        for a in articles
    ]
    content = await asyncio.to_thread(
        _chat_json,
        "你是一个 AI 内容摘要助手，用简洁中文逐篇概括文章核心内容，标题保留原文。只输出 JSON。",
        json.dumps(payload, ensure_ascii=False)
        + '\n\n{"summaries": [{"id": "文章ID", "summary": "中文概括"}]}',
        max_tokens=1600,
    )
    if content is None:
        return {"error": "LLM 调用失败", "summaries": []}
    try:
        data = json.loads(_strip_code_fence(content))
        return {"summaries": data.get("summaries", [])}
    except Exception:  # noqa: BLE001 — 解析失败返回可读错误
        return {"error": "LLM 输出解析失败", "raw": content[:200], "summaries": []}


async def _analyze_trend(args: dict) -> dict:
    """分析研究趋势：语义检索相关文章 → LLM 识别热点方向。

    Args:
        args: {"topic": str, "days"?: int}。

    Returns:
        dict: {"trends": [...], "topic": str, "days": int} 或含 error。
    """
    topic: str = (args.get("topic") or "").strip()
    days: int = args.get("days", 7)

    if not topic:
        return {"error": "topic 不能为空", "trends": []}

    # 1. 语义检索相关文章（to_thread 避免阻塞 event loop）
    hits = await asyncio.to_thread(vs_search, query=topic, days=days, limit=30)
    if not hits:
        return {"trends": [], "topic": topic, "days": days,
                "message": f"最近 {days} 天没有找到与「{topic}」相关的文章。"}

    # 2. 构造给 LLM 的趋势分析 prompt
    articles_text = "\n".join(
        f"- [{h['title']}] ({h['source']}, score={h['score']})" for h in hits
    )
    content = await asyncio.to_thread(
        _chat_json,
        "你是 AI 研究趋势分析师。根据提供的文章列表，识别 3-5 个热点方向，"
        "每个方向用一两句话概括。只输出 JSON。",
        json.dumps({"topic": topic, "articles": articles_text}, ensure_ascii=False)
        + '\n\n{"trends": [{"direction": "方向名称", "summary": "概括", "article_count": N}]}',
        max_tokens=1200,
    )

    if content is None:
        return {"error": "LLM 调用失败", "trends": []}

    try:
        data = json.loads(_strip_code_fence(content))
        return {"trends": data.get("trends", []), "topic": topic, "days": days}
    except Exception:
        return {"error": "LLM 输出解析失败", "trends": []}


async def _trigger_collection(_args: dict) -> dict:
    """手动触发一次数据采集。

    Args:
        _args: 工具参数（无参数）。

    Returns:
        dict: {"status": str, "message": str}。
    """
    try:
        await collect_once()
        return {"status": "ok", "message": "数据采集已触发，请稍后查询新数据。"}
    except Exception as e:
        return {"status": "error", "message": f"采集失败: {e}"}


EXECUTOR: dict[str, Callable[[dict], Awaitable[dict]]] = {
    "search_articles": _search_articles,
    "get_article_detail": _get_article_detail,
    "summarize_articles": _summarize_articles,
    "analyze_trend": _analyze_trend,
    "trigger_collection": _trigger_collection,
}
