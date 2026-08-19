from fastapi import APIRouter, Query

from backend.database import query_articles

router = APIRouter(prefix="/api", tags=["articles"],responses={404: {"description": "Not found"}})


@router.get("/articles")
def get_articles(
    days: int = Query(default=7, ge=1, le=365, description="时间范围（天）"),
    sources: str | None = Query(default=None, description="源名称列表，逗号分隔"),
    limit: int = Query(default=20, ge=1, le=200, description="最多返回条数"),
):
    """按采集时间查询最近 N 天文章，可选按源筛选。

    Args:
        days: 时间范围（天），默认 7 天，范围 1-365。
        sources: 源名称列表，如 "arxiv,hackernews"；None 表示全选。
        limit: 最多返回条数，默认 20，范围 1-200。

    Returns:
        dict: {"total": int, "articles": list[dict]}。
    """
    source_list = [s.strip() for s in sources.split(",")] if sources else None
    articles = query_articles(days=days, sources=source_list, limit=limit)
    return {"total": len(articles), "articles": articles}