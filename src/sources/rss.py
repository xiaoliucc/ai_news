"""通用 RSS 数据源 — 聚合任意 RSS/Atom feed。

用于接入 RSSHub 等聚合服务的中文源（如机器之心、知乎热榜等）。
feed 列表通过 .env 的 RSS_FEEDS 配置（逗号分隔的 URL 列表），
例如：https://rsshub.app/jiqizhixin/articles,https://rsshub.app/zhihu/hotlist

未配置任何 feed 时 fetch 返回空列表，源静默跳过，不影响其他源。
"""

import asyncio
import logging
from xml.etree import ElementTree

import httpx

from src.models import Article
from src.sources.base import SourcePlugin

logger = logging.getLogger(__name__)

_RSS_NS = "{http://www.w3.org/2005/Atom}"


class RSSSource(SourcePlugin):
    """RSS/Atom feed 聚合采集器。

    Attributes:
        name: 数据源名称 "rss"。
        feeds: 待聚合的 feed URL 列表（构造时传入）。
    """

    name = "rss"

    def __init__(self, feeds: list[str] | None = None):
        """初始化 RSS 源。

        Args:
            feeds: feed URL 列表；空或 None 表示未配置，fetch 返回空。
        """
        self.feeds = feeds or []

    async def fetch(self, limit: int = 20) -> list[Article]:
        """并发抓取所有 feed 并解析为 Article。

        Args:
            limit: 每个 feed 最多取的文章条数。

        Returns:
            list[Article]: 聚合后的文章列表；单个 feed 失败只跳过该 feed。
        """
        if not self.feeds:
            logger.info("RSS_FEEDS 未配置，RSS 源跳过")
            return []

        async with httpx.AsyncClient(timeout=10.0) as client:
            tasks = [self._fetch_feed(client, url, limit) for url in self.feeds]
            results = await asyncio.gather(*tasks)

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
        try:
            response = await client.get(url)
            response.raise_for_status()
            return self._parse_feed(response.text, url, limit)
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
