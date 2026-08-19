"""
测试 HuggingFacePaperSource — 集成测试，验证 Papers With Code（Hugging Face API）采集功能。

依赖网络连接，属于 integration 测试。
"""

import json

import pytest
from src.output import output_json
from src.sources.papers import HuggingFacePaperSource


@pytest.mark.integration
@pytest.mark.asyncio
async def test_fetch_papers():
    """采集 Papers With Code 论文，验证返回类型和字段完整性。"""
    source = HuggingFacePaperSource()
    articles = await source.fetch(limit=5)

    assert isinstance(articles, list)
    assert len(articles) > 0, "应至少返回 1 篇论文"

    for a in articles:
        assert a.id, f"文章 id 不应为空: {a.title}"
        assert a.id.startswith("pwc_"), f"id 应以 pwc_ 开头: {a.id}"
        assert a.title, "标题不应为空"
        assert a.url, f"url 不应为空: {a.title}"
        assert a.source == "huggingface_papers", f"source 应为 huggingface_papers: {a.source}"
        assert a.language == "en"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_fetch_papers_returns_correct_limit():
    """指定 limit 时应返回不超过该数量的结果。"""
    source = HuggingFacePaperSource()
    articles = await source.fetch(limit=3)

    assert len(articles) <= 3, f"应返回 ≤3 篇，实际 {len(articles)} 篇"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_fetch_papers_json_output():
    """前 3 条数据应能正确序列化为 JSON 格式。"""
    source = HuggingFacePaperSource()
    articles = await source.fetch(limit=3)

    result = output_json(articles)
    parsed = json.loads(result)

    assert isinstance(parsed, list)
    assert len(parsed) == 3, f"应序列化 3 条，实际 {len(parsed)} 条"

    # 逐条验证 JSON 字段完整
    for item in parsed:
        assert item["id"].startswith("pwc_")
        assert item["title"]
        assert item["url"]
        assert item["source"] == "huggingface_papers"
        assert item["language"] == "en"
        assert isinstance(item["score"], int)
        assert isinstance(item["tags"], list)
