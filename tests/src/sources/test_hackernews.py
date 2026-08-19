"""
测试 HackerNewsSource — 集成测试，验证 Hacker News API 采集功能。

依赖网络连接，属于 slow / integration 测试。
"""

import pytest
from src.sources.hackernews import HackerNewsSource


@pytest.mark.integration
@pytest.mark.asyncio
async def test_fetch_hackernews():
    """采集 5 篇 HN 热门文章，验证返回类型和字段完整性。"""
    source = HackerNewsSource()
    articles = await source.fetch(limit=5)

    assert isinstance(articles, list)
    assert len(articles) > 0, "应至少返回 1 篇文章"

    for a in articles:
        assert a.id, f"文章 id 不应为空: {a.title}"
        assert a.title, "文章 title 不应为空"
        assert a.source == "hackernews"
        assert isinstance(a.score, int)