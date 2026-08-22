"""通用 RSS 数据源 — 聚合任意 RSS/Atom feed。

用于接入 RSSHub 等聚合服务的中文源（如机器之心、知乎热榜等）。
feed 列表通过 .env 的 RSS_FEEDS 配置（逗号分隔的 URL 列表），
例如：https://rsshub.app/jiqizhixin/articles,https://rsshub.app/zhihu/hotlist

未配置任何 feed 时 fetch 返回空列表，源静默跳过，不影响其他源。
"""

import asyncio
import logging
import time
from xml.etree import ElementTree

import httpx

from src.models import Article
from src.sources.base import PROXY_URL, SourcePlugin

logger = logging.getLogger(__name__)

_RSS_NS = "{http://www.w3.org/2005/Atom}"

# 官方免费 RSS 守则：同一凭证最多每 60 分钟请求一次、每日最多 25 次。
# 60 分钟退避下 24h 最多 24 次，自动落在每日预算内。
# 模块级状态：scheduler 每次采集都会新建 RSSSource 实例，退避必须跨实例共享。
_last_request_ts: float | None = None
# 429（限流/额度耗尽）后冷却：每日 25 次额度耗尽后任何请求都会 429，
# 冷却 6h 避免每 60 分钟白碰一次壁（额度按日重置，次日自动恢复探测）。
_last_429_ts: float | None = None
_429_COOLDOWN_SECONDS = 6 * 3600.0


class RSSSource(SourcePlugin):
    """RSS/Atom feed 聚合采集器。

    Attributes:
        name: 数据源名称 "rss"。
        feeds: 待聚合的 feed URL 列表（构造时传入）。
        min_interval: 两次请求的最小间隔（秒），默认 3600（官方免费额度）；
            传入 0 可禁用退避（测试用）。
    """

    name = "rss"

    def __init__(self, feeds: list[str] | None = None, min_interval: float = 3600.0):
        """初始化 RSS 源。

        Args:
            feeds: feed URL 列表；空或 None 表示未配置，fetch 返回空。
            min_interval: 请求最小间隔秒数，默认 3600（官方免费额度 60 分钟/次）。
        """
        self.feeds = feeds or []
        self.min_interval = min_interval

    async def fetch(self, limit: int = 20) -> list[Article]:
        """并发抓取所有 feed 并解析为 Article。

        遵守官方免费 RSS 频率限制：距上次请求不足 min_interval 时跳过
        （不打请求），避免 429 与每日配额耗尽。

        Args:
            limit: 每个 feed 最多取的文章条数。

        Returns:
            list[Article]: 聚合后的文章列表；退避中、未配置或单个 feed
            失败时返回空列表。
        """
        global _last_request_ts

        if not self.feeds:
            logger.info("RSS_FEEDS 未配置，RSS 源跳过")
            return []

        now = time.monotonic()
        # 429 冷却：额度耗尽后任何请求都会 429，冷却期内直接跳过
        if _last_429_ts is not None and now - _last_429_ts < _429_COOLDOWN_SECONDS:
            logger.info(
                "RSS 源 429 冷却中：%.0f 分钟后重试",
                (_429_COOLDOWN_SECONDS - (now - _last_429_ts)) / 60,
            )
            return []

        if _backoff_active(now, _last_request_ts, self.min_interval):
            logger.info(
                "RSS 源退避中：距上次请求 %.0fs（下限 %.0fs），跳过本轮",
                now - (_last_request_ts or 0),
                self.min_interval,
            )
            return []

        async with httpx.AsyncClient(timeout=10.0, proxy=PROXY_URL) as client:
            tasks = [self._fetch_feed(client, url, limit) for url in self.feeds]
            results = await asyncio.gather(*tasks)

        # 无论成败都记录请求时间（429/5xx 同样消耗配额窗口）
        _last_request_ts = time.monotonic()

        merged: list[Article] = []
        for articles in results:
            merged.extend(articles)
        return merged[:limit]

    async def _fetch_feed(
        self, client: httpx.AsyncClient, url: str, limit: int
    ) -> list[Article]:
        """抓取并解析单个 feed。

        Args:
            client: 共享的 httpx.AsyncClient 实例。
            url: feed URL。
            limit: 最多返回条数。

        Returns:
            list[Article]: 解析出的文章列表；失败返回空列表。
        """
        global _last_429_ts
        try:
            response = await client.get(url)
            response.raise_for_status()
            return self._parse_feed(response.text, url, limit)
        except httpx.HTTPStatusError as exc:
            if exc.response is not None and exc.response.status_code == 429:
                # 限流/额度耗尽：进入长冷却，后续请求直接跳过
                _last_429_ts = time.monotonic()
            logger.warning("RSS feed 抓取失败 %s: %s", url, exc)
            return []
        except (httpx.HTTPError, ValueError) as exc:
            logger.warning("RSS feed 抓取失败 %s: %s", url, exc)
            return []

    def _parse_feed(self, xml_text: str, feed_url: str, limit: int) -> list[Article]:
        """从 RSS/Atom XML 解析文章（纯函数，便于单测）。

        兼容 RSS 2.0（<item><title>/<link>/<description>/<guid>）与
        Atom（<entry><title>/<link href>/<summary>/<id>）两种格式。

        Args:
            xml_text: feed 的 XML 文本。
            feed_url: 来源 feed URL（用于生成文章 URL 回退）。
            limit: 最多返回条数。

        Returns:
            list[Article]: 解析出的文章列表。
        """
        try:
            root = ElementTree.fromstring(xml_text)
        except ElementTree.ParseError as exc:
            logger.warning("RSS feed XML 解析失败 %s: %s", feed_url, exc)
            return []

        # 同时收集 RSS 2.0 item 与 Atom entry
        items = list(root.iter("item")) + list(root.iter(f"{_RSS_NS}entry"))
        articles: list[Article] = []
        seen: set[str] = set()

        for item in items:
            title = _first_text(item, "title", _RSS_NS + "title")
            if not title:
                continue

            url = _link_href(item, _RSS_NS)
            if not url:
                url = _first_text(item, "link", _RSS_NS + "link")
            url = url or feed_url

            article_id = _first_text(item, "guid", _RSS_NS + "id") or url
            if article_id in seen:
                continue
            seen.add(article_id)

            summary = _first_text(item, "description", _RSS_NS + "summary")

            articles.append(
                Article(
                    id=f"rss_{article_id[:64]}",
                    title=title,
                    url=url,
                    source=self.name,
                    summary=summary,
                    author=None,
                    published_at=None,
                    score=0,
                    tags=[],
                    language="zh",
                )
            )
            if len(articles) >= limit:
                break

        return articles


def _backoff_active(now: float, last_ts: float | None, min_interval: float) -> bool:
    """判断当前是否处于请求退避期。

    Args:
        now: 当前单调时钟（time.monotonic()）。
        last_ts: 上次请求的单调时钟；None 表示从未请求过。
        min_interval: 最小请求间隔（秒）；<=0 表示禁用退避。

    Returns:
        bool: 距上次请求不足 min_interval 返回 True（应跳过本轮请求）。
    """
    if min_interval <= 0 or last_ts is None:
        return False
    return now - last_ts < min_interval


def _first_text(element: ElementTree.Element, *tags: str) -> str | None:
    """取第一个命中的标签文本（去除空白）。

    Args:
        element: 父元素。
        *tags: 待匹配的标签名（无命名空间 / 带命名空间）。

    Returns:
        str | None: 文本内容，无匹配返回 None。
    """
    for tag in tags:
        child = element.find(tag)
        if child is not None and child.text:
            return child.text.strip()
    return None


def _link_href(element: ElementTree.Element, atom_ns: str) -> str | None:
    """取 Atom entry 中 <link href="..."> 的地址。

    Args:
        element: 父元素。
        atom_ns: Atom 命名空间前缀。

    Returns:
        str | None: href 值，无匹配返回 None。
    """
    link = element.find(f"{atom_ns}link")
    if link is not None:
        return link.get("href")
    return None
