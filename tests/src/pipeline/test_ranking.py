"""
测试 pipeline/ranking.py — 复合排序模块。
"""

from datetime import datetime, timedelta, timezone

import pytest

from src.models import Article
from src.pipeline.ranking import rank


def make_article(
    id: str,
    title: str,
    score: int,
    source: str = "mock",
    published_at: datetime | None = None,
) -> Article:
    """快速创建测试用 Article。"""
    return Article(
        id=id,
        title=title,
        url=f"https://example.com/{id}",
        source=source,
        summary=None,
        author=None,
        published_at=published_at,
        score=score,
        tags=[],
        language="en",
    )


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class TestRank:
    def test_empty_list(self):
        """空列表返回空列表。"""
        assert rank([]) == []

    def test_same_score_newer_first(self):
        """相同 score 时，新文章排前面。"""
        now = utc_now()
        old = make_article("old", "Old", 50, published_at=now - timedelta(hours=48))
        new = make_article("new", "New", 50, published_at=now)
        result = rank([old, new])
        assert [a.id for a in result] == ["new", "old"]

    def test_arxiv_score_zero_not_all_bottom(self):
        """ArXiv 全 0 分，靠时间衰减和权重仍能排到较高位置。"""
        now = utc_now()
        old_hn = make_article(
            "hn_old", "Old HN", 100, source="hackernews",
            published_at=now - timedelta(hours=120),
        )
        fresh_arxiv = make_article(
            "arxiv_new", "New Paper", 0, source="arxiv",
            published_at=now,
        )
        result = rank([old_hn, fresh_arxiv])
        # 新鲜论文的时间衰减远高于 5 天前的 HN，应排前面
        assert result[0].id == "arxiv_new"

    def test_arxiv_vs_hn_score_dominates_when_similar_age(self):
        """同时段的 HN（高分为 1.0）应排 ArXiv（无原生热度）前面。"""
        now = utc_now()
        hn = make_article(
            "hn_1", "HN Hot", 500, source="hackernews",
            published_at=now - timedelta(hours=1),
        )
        arxiv = make_article(
            "arxiv_1", "New Paper", 0, source="arxiv",
            published_at=now - timedelta(hours=1),
        )
        result = rank([arxiv, hn])
        assert result[0].id == "hn_1"

    def test_unknown_source_gets_default_weight(self):
        """未知源使用默认权重 1.0，不崩溃。"""
        now = utc_now()
        a = make_article("a", "A", 10, source="weird", published_at=now)
        b = make_article("b", "B", 20, source="weird", published_at=now)
        result = rank([a, b])
        assert [x.id for x in result] == ["b", "a"]

    def test_no_published_at_uses_default_decay(self):
        """无时间戳的文章用默认衰减，不崩溃。"""
        a = make_article("a", "A", 10)
        b = make_article("b", "B", 20)
        result = rank([a, b])
        assert [x.id for x in result] == ["b", "a"]

    def test_same_source_normalization_scales(self):
        """同源内 score 归一化后，高低分仍正确排序。"""
        now = utc_now()
        low = make_article("l", "Low", 10, source="arxiv", published_at=now)
        high = make_article("h", "High", 1000, source="arxiv", published_at=now)
        result = rank([low, high])
        assert [x.id for x in result] == ["h", "l"]

    def test_mixed_sources_no_time_no_score(self):
        """无时间、同源 score 全部相同时（全 0），返回原顺序。"""
        a = make_article("a", "A", 0, source="arxiv")
        b = make_article("b", "B", 0, source="arxiv")
        result = rank([a, b])
        assert len(result) == 2


# ── ranking v2：LLM 质量因子 ─────────────────────────────────────────────────

def test_quality_factor_prefers_higher_quality():
    """同分同源同时间：quality 高者排序靠前。"""
    now = utc_now()
    low = make_article("low", "Low", 50, published_at=now)
    low.quality = 40
    high = make_article("high", "High", 50, published_at=now)
    high.quality = 95

    result = rank([low, high])
    assert result[0].id == "high"  # quality 95 的修正系数更高


def test_quality_none_falls_back_v1():
    """quality 为 None（未评分）时因子 = 1.0，回退 v1 排序。"""
    now = utc_now()
    a = make_article("a", "A", 60, published_at=now)          # quality None
    b = make_article("b", "B", 50, published_at=now)
    b.quality = 50  # 因子 0.85——与 v1 相比被打折

    result = rank([b, a])
    # a(60×1.0) vs b(50×0.85=42.5)：None 不受罚，仍按 v1 分序
    assert result[0].id == "a"
    assert result[1].id == "b"


def test_quality_zero_sinks():
    """quality=0 因子 0.7 最低修正，沉到同分文章之后。"""
    now = utc_now()
    bad = make_article("bad", "Bad", 50, published_at=now)
    bad.quality = 0
    normal = make_article("n", "N", 50, published_at=now)  # quality None

    result = rank([normal, bad])
    assert result[0].id == "n"
    assert result[1].id == "bad"
