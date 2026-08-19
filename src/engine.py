"""
核心调度引擎 — 编排数据采集流水线。

职责：
    1. 管理多个数据源插件（注册、遍历）
    2. 并发/串行调度各数据源的 fetch() 方法
    3. 汇总所有数据源返回的 Article 列表
    4. 作为后续流水线（去重 → 过滤 → 排序 → 输出）的入口

依赖：
    src/models.py     — Article 数据类
    src/sources/      — SourcePlugin 子类（hackernews / arxiv / huggingface_papers）
"""

import asyncio
import json
import logging
import re
import time
from dataclasses import asdict, dataclass, field
from typing import List

from src.models import Article
from src.pipeline.ranking import rank
from src.sources.base import SourcePlugin

logger = logging.getLogger(__name__)

_ARXIV_URL_RE = re.compile(
    r"arxiv\.org/(?:abs|pdf)/(?P<arxiv_id>[^/?#]+?)(?:v\d+)?/?(?:[?#].*)?$"
)
_ARXIV_ID_RE = re.compile(r"\d{4}\.\d{4,5}")


def _strip_arxiv_version(arxiv_id: str) -> str:
    """去掉 arxiv ID 的版本号后缀。

    Args:
        arxiv_id: arxiv ID 字符串（如 "2401.12345v2"）。

    Returns:
        str: 无版本号的 ID（如 "2401.12345"）。
    """
    return re.sub(r"v\d+$", "", arxiv_id)


def _extract_arxiv_id(article: Article) -> str | None:
    """从 Article 中提取 arxiv ID（去版本号）。

    优先从 URL 提取（覆盖 abs 页和 pdf 页），其次依据 id 前缀
    （"arxiv_" / "pwc_"）解析。pwc_ 前缀即使 URL 是 GitHub 也能识别。

    Args:
        article: 待提取的 Article 对象。

    Returns:
        str | None: arxiv ID（如 "2401.12345"），提取失败返回 None。
    """
    if article.url:
        match = _ARXIV_URL_RE.search(article.url)
        if match:
            return _strip_arxiv_version(match.group("arxiv_id"))
    for prefix in ("arxiv_", "pwc_"):
        if article.id.startswith(prefix):
            candidate = _strip_arxiv_version(article.id[len(prefix):])
            if _ARXIV_ID_RE.fullmatch(candidate):
                return candidate
    return None


def _dedup_key(article: Article) -> str:
    """计算去重键。

    对于 arxiv 论文（含跨源重复），返回统一的 arxiv 指纹键；
    非 arxiv 文章回退到原始 id。

    Args:
        article: 待计算的 Article 对象。

    Returns:
        str: 去重用的唯一键。
    """
    arxiv_id = _extract_arxiv_id(article)
    if arxiv_id:
        return f"arxiv:{arxiv_id}"
    return article.id


@dataclass
class SourceStats:
    """单个数据源的采集统计。

    Attributes:
        name: 数据源名称。
        fetched: 采集到的条数。
        failed: 数据源是否失败。
        error: 失败时的错误信息。
        elapsed_ms: 采集耗时（毫秒）。
    """

    name: str
    fetched: int = 0
    failed: bool = False
    error: str | None = None
    elapsed_ms: int = 0
    def to_dict(self) -> dict:
        """转换为字典。"""
        return asdict(self)

    def to_json(self) -> str:
        """转换为 JSON 字符串。"""
        return json.dumps(self.to_dict())

    @classmethod
    def from_dict(cls, data: dict) -> "SourceStats":
        """从字典创建实例。"""
        return cls(**data)

    @classmethod
    def from_json(cls, json_str: str) -> "SourceStats":
        """从 JSON 字符串创建实例。"""
        return cls.from_dict(json.loads(json_str))

    @staticmethod
    def list_to_json(stats: List["SourceStats"]) -> str:
        """将列表转换为 JSON 字符串。"""
        return json.dumps([asdict(s) for s in stats])

    @staticmethod
    def list_from_json(json_str: str) -> List["SourceStats"]:
        """从 JSON 字符串恢复列表。"""
        data = json.loads(json_str)
        return [SourceStats.from_dict(item) for item in data]

@dataclass
class EngineResult:
    """一次 run() 的完整结果：文章列表 + 采集统计。

    Attributes:
        articles: 去重排序后的文章列表。
        source_stats: 各源采集统计。
        deduped_count: 被去重消除的条数。
        total_elapsed_ms: 总耗时（毫秒）。
    """

    articles: list[Article]
    source_stats: list[SourceStats] = field(default_factory=list)
    deduped_count: int = 0
    total_elapsed_ms: int = 0


class NewsEngine:
    """新闻采集引擎。

    接收一组 SourcePlugin 实例，并发调用各源的 fetch() 采集数据，
    经过去重、排序后返回统一的 EngineResult。

    Attributes:
        sources: 已注册的数据源插件列表。
    """

    def __init__(self, sources: list[SourcePlugin]):
        """初始化引擎。

        Args:
            sources: 已注册的 SourcePlugin 实例列表。
        """
        self.sources = sources

    async def _fetch_timed(self, source: SourcePlugin, limit: int) -> tuple:
        """采集单个源并计时。

        Args:
            source: 数据源插件实例。
            limit: 采集条数上限。

        Returns:
            tuple: (结果列表, 错误信息或 None, 耗时秒数)。
        """
        started = time.monotonic()
        try:
            result = await source.fetch(limit=limit)
            error = None
        except Exception as exc:  # noqa: BLE001 — 聚合所有源错误供上层统计
            result = []
            error = exc
        elapsed = time.monotonic() - started
        return result, error, elapsed

    async def run(self, limit: int = 20) -> EngineResult:
        """执行数据采集流水线：并发拉取 → 去重 → 排序。

        使用 asyncio.gather 并发调用各数据源，单个源失败不影响其他源。

        Args:
            limit: 每个数据源采集的条数。

        Returns:
            EngineResult: 包含去重排序后的文章列表和各源统计信息。
        """
        started = time.monotonic()
        tasks = [self._fetch_timed(source, limit=limit) for source in self.sources]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        articles: list[Article] = []
        source_stats: list[SourceStats] = []
        for source, result in zip(self.sources, results):
            stats = SourceStats(name=source.name)
            fetched, error, elapsed = result
            stats.elapsed_ms = int(elapsed * 1000)
            if error is not None:
                stats.failed = True
                stats.error = str(error)
                logger.error("数据源 %s 采集失败: %s", source.name, error)
            else:
                stats.fetched = len(fetched)
                articles.extend(fetched)
            source_stats.append(stats)

        deduplicated = self._deduplicate(articles)
        deduped_count = len(articles) - len(deduplicated)
        articles = rank(deduplicated)

        return EngineResult(
            articles=articles,
            source_stats=source_stats,
            deduped_count=deduped_count,
            total_elapsed_ms=int((time.monotonic() - started) * 1000),
        )

    def _deduplicate(self, articles: list[Article]) -> list[Article]:
        """去重：按 arxiv 指纹优先、id 回退的策略消除重复。

        同一条 arxiv 论文可能被多个源采集（如 arxiv + pwc），
        按 arxiv ID 指纹去重可正确合并。非 arxiv 文章按原始 id 去重。

        Args:
            articles: 待去重的文章列表。

        Returns:
            list[Article]: 去重后的文章列表（保留首次出现）。
        """
        seen: set[str] = set()
        result: list[Article] = []
        for article in articles:
            key = _dedup_key(article)
            if key in seen:
                continue
            seen.add(key)
            result.append(article)
        return result
