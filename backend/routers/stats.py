"""采集统计路由 — 返回采集运行的概要统计与历史明细。"""

from fastapi import APIRouter, Query

from backend.database import get_collection_stats

router = APIRouter(prefix="/api", tags=["stats"])


@router.get("/stats")
def list_stats(limit: int = Query(default=10, ge=1, le=100, description="返回最近 N 次采集明细")):
    """返回采集运行统计：总次数、总文章数、最近采集时间、最近 N 次明细。

    Args:
        limit: 返回的最近采集运行明细条数，默认 10（1-100）。

    Returns:
        dict: {"total_runs", "total_articles", "last_collection_at", "runs": [...]}
    """
    return get_collection_stats(limit=limit)
