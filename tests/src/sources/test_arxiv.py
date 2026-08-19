"""
测试 ArxivSource — 集成测试，验证 ArXiv API 采集功能。

依赖网络连接，属于 integration 测试。
"""

import pytest
from src.sources.arxiv import ArxivSource


@pytest.mark.integration
@pytest.mark.asyncio
async def test_fetch_arxiv():
    """采集 5 篇 ArXiv 最新论文，验证返回类型和字段完整性。"""
    source = ArxivSource()
    articles = await source.fetch(limit=5)

    assert isinstance(articles, list)
    assert len(articles) > 0, "应至少返回 1 篇论文"

    for a in articles:
        assert a.id, f"文章 id 不应为空: {a.title}"
        assert a.id.startswith("arxiv_"), f"id 应以 arxiv_ 开头: {a.id}"
        assert a.title, "标题不应为空"
        assert a.url, f"url 不应为空: {a.title}"
        assert a.source == "arxiv", f"source 应为 arxiv: {a.source}"
        assert a.language == "en"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_fetch_arxiv_returns_correct_limit():
    """指定 limit 时应返回不超过该数量的结果。"""
    source = ArxivSource()
    articles = await source.fetch(limit=3)

    assert len(articles) <= 3, f"应返回 ≤3 篇，实际 {len(articles)} 篇"
