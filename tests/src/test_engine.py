"""
测试 NewsEngine — 核心调度引擎。

覆盖：
    - deduplicate: 去重逻辑（纯函数，不依赖网络）
    - run: 采集 + 去重 + 排序全流程（使用 Mock 数据源）
"""

import pytest
from src.models import Article
from src.sources.base import SourcePlugin
from src.engine import NewsEngine


# ---------------------------------------------------------------------------
# 测试辅助：Mock 数据源
# ---------------------------------------------------------------------------

class MockSource(SourcePlugin):
    """返回预设 Article 列表的假数据源，用于隔离网络依赖。"""

    def __init__(self, name: str, articles: list[Article]):
        self.name = name
        self._articles = articles

    async def fetch(self, limit: int = 20) -> list[Article]:
        _ = limit
        return self._articles


class FailingSource(SourcePlugin):
    """始终抛出异常的假数据源，用于测试容错逻辑。"""

    name = "failing"

    async def fetch(self, limit: int = 20) -> list[Article]:
        _ = limit
        raise RuntimeError("模拟网络错误")


# ---------------------------------------------------------------------------
# 测试 Article 工厂函数
# ---------------------------------------------------------------------------

def make_article(
    id: str,
    title: str,
    score: int,
    source: str = "mock",
    url: str | None = None,
) -> Article:
    """快速创建测试用 Article。"""
    return Article(
        id=id,
        title=title,
        url=url or f"https://example.com/{id}",
        source=source,
        summary=None,
        author=None,
        published_at=None,
        score=score,
        tags=[],
        language="en",
    )


# ---------------------------------------------------------------------------
# deduplicate 测试
# ---------------------------------------------------------------------------

class TestDeduplicate:
    """deduplicate() 是纯函数，直接实例化 NewsEngine 即可调用。"""

    def test_empty_list(self):
        """空列表返回空列表。"""
        engine = NewsEngine(sources=[])
        assert engine._deduplicate([]) == []

    def test_no_duplicates(self):
        """没有重复时保持不变。"""
        engine = NewsEngine(sources=[])
        articles = [
            make_article("1", "A", 10),
            make_article("2", "B", 20),
        ]
        result = engine._deduplicate(articles)
        assert len(result) == 2
        assert [a.id for a in result] == ["1", "2"]

    def test_removes_duplicates_keeps_first(self):
        """相同 id 只保留第一次出现的。"""
        engine = NewsEngine(sources=[])
        articles = [
            make_article("1", "A", 10),
            make_article("1", "A-copy", 30),
            make_article("2", "B", 20),
        ]
        result = engine._deduplicate(articles)
        assert len(result) == 2
        assert result[0].title == "A"        # 保留的是第一条
        assert result[1].title == "B"

    def test_all_duplicates(self):
        """全部重复，只留第一条。"""
        engine = NewsEngine(sources=[])
        articles = [make_article("same", "X", 10) for _ in range(5)]
        result = engine._deduplicate(articles)
        assert len(result) == 1

    def test_dedup_arxiv_and_pwc(self):
        """同一论文在 arxiv 源与 pwc 源重复时，靠 arxiv ID 指纹去重。"""
        engine = NewsEngine(sources=[])
        arxiv_article = make_article(
            "arxiv_2101.12345v2", "A", 10,
            source="arxiv",
            url="https://arxiv.org/abs/2101.12345v2",
        )
        pwc_article = make_article(
            "pwc_2101.12345", "A", 30,
            source="huggingface_papers",
            url="https://arxiv.org/abs/2101.12345",
        )
        result = engine._deduplicate([arxiv_article, pwc_article])
        assert len(result) == 1
        assert result[0].source == "arxiv"   # 保留首次出现

    def test_dedup_hackernews_linking_to_arxiv(self):
        """HN 文章链接指向 arxiv 时，与 arxiv 源那篇去重。"""
        engine = NewsEngine(sources=[])
        hn = make_article(
            "hackernews_1", "A", 50,
            source="hackernews",
            url="https://arxiv.org/abs/2101.12345",
        )
        arxiv_article = make_article(
            "arxiv_2101.12345", "A", 10,
            source="arxiv",
            url="https://arxiv.org/abs/2101.12345",
        )
        result = engine._deduplicate([hn, arxiv_article])
        assert len(result) == 1
        assert result[0].source == "hackernews"  # 保留首次出现的 HN 那条

    def test_non_arxiv_pwc_id_not_falsely_deduped(self):
        """pwc_ 前缀 + 非 arxiv 格式 id 不能走 arxiv 指纹层。"""
        engine = NewsEngine(sources=[])
        a = make_article("pwc_abc123", "A", 10, source="huggingface_papers")
        b = make_article("pwc_abc456", "B", 20, source="huggingface_papers")
        result = engine._deduplicate([a, b])
        assert len(result) == 2


# ---------------------------------------------------------------------------
# run 测试（异步）
# ---------------------------------------------------------------------------

class TestRun:
    """测试 run() 的全流程：采集 → 去重 → 排序。"""

    @pytest.mark.asyncio
    async def test_collects_from_multiple_sources(self):
        """多个数据源的数据被汇总。"""
        source_a = MockSource("a", [
            make_article("a1", "A1", 10, "a"),
        ])
        source_b = MockSource("b", [
            make_article("b1", "B1", 20, "b"),
        ])
        engine = NewsEngine(sources=[source_a, source_b])
        result = await engine.run()

        assert len(result.articles) == 2

    @pytest.mark.asyncio
    async def test_deduplicates_across_sources(self):
        """不同数据源出现相同 id 的文章时去重。"""
        source_a = MockSource("a", [
            make_article("shared", "From A", 10, "a"),
        ])
        source_b = MockSource("b", [
            make_article("shared", "From B", 30, "b"),
        ])
        engine = NewsEngine(sources=[source_a, source_b])
        result = await engine.run()

        assert len(result.articles) == 1

    @pytest.mark.asyncio
    async def test_sorts_by_score_descending(self):
        """按热度降序排列。"""
        engine = NewsEngine(sources=[
            MockSource("x", [
                make_article("low", "Low", 5),
                make_article("mid", "Mid", 50),
                make_article("high", "High", 100),
            ])
        ])
        result = await engine.run()

        scores = [a.score for a in result.articles]
        assert scores == [100, 50, 5]

    @pytest.mark.asyncio
    async def test_failing_source_does_not_block_others(self):
        """某个数据源失败时，其他源的数据仍正常返回。"""
        good = MockSource("good", [make_article("g1", "OK", 10)])
        bad = FailingSource()
        engine = NewsEngine(sources=[bad, good])
        result = await engine.run()

        assert len(result.articles) == 1
        assert result.articles[0].id == "g1"

    @pytest.mark.asyncio
    async def test_source_stats_ok_and_failed(self):
        """成功源记录采集数，失败源记录失败状态和错误。"""
        good = MockSource("good", [make_article("g1", "OK", 10)])
        bad = FailingSource()
        engine = NewsEngine(sources=[bad, good])
        result = await engine.run()

        assert len(result.source_stats) == 2
        by_name = {s.name: s for s in result.source_stats}
        assert by_name["good"].fetched == 1
        assert by_name["good"].failed is False
        assert by_name["good"].error is None
        assert by_name["good"].elapsed_ms >= 0
        assert by_name["failing"].fetched == 0
        assert by_name["failing"].failed is True
        assert by_name["failing"].error == "模拟网络错误"
        assert by_name["failing"].elapsed_ms >= 0

    @pytest.mark.asyncio
    async def test_deduped_count(self):
        """deduped_count 记录被去重消除的条数。"""
        engine = NewsEngine(sources=[
            MockSource("a", [
                make_article("arxiv_2101.12345", "A", 10, "arxiv",
                             url="https://arxiv.org/abs/2101.12345"),
            ]),
            MockSource("b", [
                make_article("pwc_2101.12345", "A", 30, "huggingface_papers",
                             url="https://arxiv.org/abs/2101.12345"),
            ]),
        ])
        result = await engine.run()

        assert result.deduped_count == 1
        assert len(result.articles) == 1
        assert result.total_elapsed_ms >= 0
