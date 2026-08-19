"""数据源路由 — 返回可用数据源列表、启用状态及开关切换。"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.database import get_profile, get_source_stats, set_profile

router = APIRouter(prefix="/api", tags=["sources"])

# 预定义的源元数据（与 src/sources/ 中的插件一一对应）
# category 为英文枚举（tech_community/academic/chinese_media），展示文本由前端 i18n 映射
SOURCE_META = [
    {
        "name": "hackernews",
        "label": "Hacker News",
        "description": "热门 AI 相关帖子与讨论",
        "category": "tech_community",
    },
    {
        "name": "arxiv",
        "label": "ArXiv",
        "description": "AI 论文（cs.AI / cs.CL / cs.CV 等 11 个分类）",
        "category": "academic",
    },
    {
        "name": "huggingface_papers",
        "label": "HuggingFace Papers",
        "description": "每日 AI 论文 + 代码实现",
        "category": "academic",
    },
    {
        "name": "rss",
        "label": "RSS 聚合",
        "description": "中文源聚合（RSS_FEEDS 配置，当前含机器之心官方 RSS）",
        "category": "chinese_media",
    },
]

SOURCE_NAMES = [m["name"] for m in SOURCE_META]


class SourceToggleRequest(BaseModel):
    enabled: bool


def _selected_names() -> list[str]:
    """读取用户选中的源；空列表表示全选。"""
    return get_profile().get("selected_sources") or []


def _is_enabled(name: str) -> bool:
    """判断某源是否启用（空列表 = 全选 = 全部启用）。"""
    selected = _selected_names()
    return (not selected) or (name in selected)


def _normalize(selected: list[str]) -> list[str]:
    """若选中集等于全部源，规范化存回空列表（全选态）。"""
    if set(selected) == set(SOURCE_NAMES):
        return []
    return selected


@router.get("/sources")
def list_sources():
    """返回可用数据源列表，含各源已采集文章数与启用状态。

    Returns:
        dict: {"sources": [{"name", "label", "description", "category",
            "article_count", "enabled"}, ...]}
    """
    counts = get_source_stats()
    sources = []
    for meta in SOURCE_META:
        item = dict(meta)
        item["article_count"] = counts.get(meta["name"], 0)
        item["enabled"] = _is_enabled(meta["name"])
        sources.append(item)
    return {"sources": sources}


@router.put("/sources/{name}")
def toggle_source(name: str, req: SourceToggleRequest) -> dict:
    """切换单个数据源的启用状态。

    Args:
        name: 数据源名称。
        req: {"enabled": bool}。

    Returns:
        dict: {"name", "enabled", "selected_sources"}。

    Raises:
        HTTPException 404: 未知数据源。
        HTTPException 400: 关闭最后一个启用的源。
    """
    if name not in SOURCE_NAMES:
        raise HTTPException(status_code=404, detail=f"未知数据源: {name}")

    current = _selected_names()
    base = list(SOURCE_NAMES) if not current else current

    if req.enabled:
        if name not in base:
            base.append(name)
    else:
        if name not in base:
            return {"name": name, "enabled": False, "selected_sources": current}
        remaining = [n for n in base if n != name]
        if not remaining:
            raise HTTPException(status_code=400, detail="至少保留一个数据源")
        base = remaining

    normalized = _normalize(base)
    set_profile(selected_sources=normalized)
    return {
        "name": name,
        "enabled": req.enabled,
        "selected_sources": normalized,
    }
