"""
复合排序模块 — 替代 engine.run() 中的单一 sort(key=score)。

排序公式：
    final_score = normalized_score × time_decay × source_weight

    - normalized_score — 同源内 min-max 归一化到 [0, 1]，解决跨源量纲差异
    - time_decay        — 指数衰减 e^(-λ·hours_ago)，半衰期 48h
    - source_weight     — 源的可信度/活跃度基准分

v2 预留：纳入 pipeline/llm.py 的质量分作为额外因子。
"""

import math
from datetime import datetime, timezone

from src.models import Article

# 源权重：跨源比较的基准分
SOURCE_WEIGHTS = {
    "hackernews": 1.0,
    "arxiv": 0.6,
    "huggingface_papers": 0.8,
    "rss": 0.7,
    "github": 0.9,
    "csdn": 0.7,
}

# 时间衰减半衰期（小时）
HALF_LIFE_HOURS = 48.0
# 无时间戳文章的回退衰减因子
DEFAULT_DECAY = 0.5


def _to_utc(dt: datetime) -> datetime:
    """统一 datetime 为 aware UTC。

    避免 naive/aware datetime 相减时抛出 TypeError。naive datetime
    假定为 UTC 并附加时区；aware datetime 转换为 UTC。

    Args:
        dt: 原始 datetime 对象（可能 naive 或 aware）。

    Returns:
        datetime: 统一后的 UTC aware datetime。
    """
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _normalize_scores(articles: list[Article]) -> dict[str, float]:
    """将各源 score 归一化到 [0, 1]（同源内 min-max）。

    按 source 分组后各自归一化，解决不同源的量纲差异（如 ArXiv 常为 0，
    HN 可达数百）。

    Args:
        articles: 待归一化的文章列表。

    Returns:
        dict[str, float]: {article.id: 归一化后的 score（0.0~1.0）}。
            同源所有 score 相同时返回 0.5。
    """
    by_source: dict[str, list[Article]] = {}
    for a in articles:
        by_source.setdefault(a.source, []).append(a)

    normalized: dict[str, float] = {}
    for items in by_source.values():
        scores = [a.score for a in items]
        lo, hi = min(scores), max(scores)
        if hi > lo:
            for a in items:
                normalized[a.id] = (a.score - lo) / (hi - lo)
        else:
            # 该源所有 score 相同（常见于全 0），给中间值 0.5
            for a in items:
                normalized[a.id] = 0.5
    return normalized


def _time_decay(published_at: datetime | None, now: datetime) -> float:
    """计算指数时间衰减因子。

    e^(-ln2 × hours_ago / 48h)，半衰期 48 小时：48 小时前的文章权重减半。
    无时间戳时返回默认值 0.5。

    Args:
        published_at: 文章发布时间（可为 None）。
        now: 当前参考时间（UTC aware）。

    Returns:
        float: 衰减因子（0~1），越新越高。
    """
    if published_at is None:
        return DEFAULT_DECAY
    hours = max(0.0, (now - _to_utc(published_at)).total_seconds() / 3600.0)
    return math.exp(-math.log(2) * hours / HALF_LIFE_HOURS)


def rank(articles: list[Article]) -> list[Article]:
    """按复合分降序排序。

    排序公式（v2）：final_score = normalized_score × time_decay × source_weight
    × quality_factor，其中 normalized_score 为同源 min-max 归一化值，time_decay
    为指数衰减，source_weight 为源可信度权重，quality_factor 为 LLM 质量分修正
    （0.7 + 0.3 × quality/100，未评分 = 1.0 回退 v1）。

    Args:
        articles: 待排序的文章列表。

    Returns:
        list[Article]: 按复合分降序排列的新列表。空列表返回空。
    """
    if not articles:
        return []

    normalized = _normalize_scores(articles)
    now = datetime.now(timezone.utc)

    def final_score(a: Article) -> float:
        decay = _time_decay(a.published_at, now)
        weight = SOURCE_WEIGHTS.get(a.source, 1.0)  # 未知源给默认权重
        # v2 质量因子：LLM 质量分 0-100 → 修正系数 0.7~1.0
        quality_factor = 1.0 if a.quality is None else 0.7 + 0.3 * a.quality / 100
        return normalized[a.id] * decay * weight * quality_factor

    return sorted(articles, key=final_score, reverse=True)
