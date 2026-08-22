"""Hacker News 数据源 — Firebase API。

API 端点：
    /v0/topstories.json   — 热门故事 ID 列表
    /v0/newstories.json   — 最新故事 ID 列表
    /v0/beststories.json  — 最佳故事 ID 列表
    /v0/item/{id}.json    — 单条故事详情
"""

from datetime import datetime
import logging

import asyncio
import httpx

from src.models import Article
from src.sources.base import PROXY_URL, SourcePlugin

logger = logging.getLogger(__name__)


class HackerNewsSource(SourcePlugin):
    """Hacker News 热门故事采集器。

    先拉取 topstories ID 列表，再并发拉取单条详情。
    """

    name = "hackernews"
    base_url = "https://hacker-news.firebaseio.com/v0/"

    async def fetch(self, limit: int = 20) -> list[Article]:
        """从 Hacker News 采集热门故事。

        并发获取 story IDs 后，使用 asyncio.gather 并发拉取每条详情，
        单条失败只跳过该条，不中断整体采集。

        Args:
            limit: 最多拉取的条数。

        Returns:
            list[Article]: 采集到的文章列表（失败条被过滤）。
        """
        async with httpx.AsyncClient(timeout=10.0, proxy=PROXY_URL) as client:
            try:
                response = await client.get(f"{self.base_url}topstories.json")
                response.raise_for_status()
                story_ids = response.json()[:limit]
            except (httpx.HTTPError, ValueError) as e:
                logger.warning("获取HN ID 失败: %s", e)
                return []

            # 并发拉取单条详情，任一失败只跳过该条
            item_tasks = [self._fetch_item(client, story_id) for story_id in story_ids]
            results = await asyncio.gather(*item_tasks)
            return [a for a in results if a is not None]

    async def _fetch_item(
        self, client: httpx.AsyncClient, story_id: int
    ) -> Article | None:
        """拉取单条 HN 详情并转为 Article。

        Args:
            client: 共享的 httpx.AsyncClient 实例。
            story_id: HN story ID。

        Returns:
            Article | None: 成功返回 Article；网络错误或数据异常返回 None。
        """
        try:
            response = await client.get(f"{self.base_url}item/{story_id}.json")
            response.raise_for_status()
            story_data = response.json()
        except (httpx.HTTPError, ValueError) as e:
            # 异常可能无消息文本（如超时），%r 显示类型便于诊断
            logger.warning("获取HN文章 %s 失败: %r", story_id, e)
            return None

        return Article(
            id=f"hackernews_{story_data.get('id')}",
            title=story_data.get("title"),
            url=story_data.get("url")
            or f"https://news.ycombinator.com/item?id={story_id}",
            source=self.name,
            summary=None,
            author=story_data.get("by"),
            published_at=(
                datetime.fromtimestamp(story_data.get("time"))
                if story_data.get("time")
                else None
            ),
            score=story_data.get("score", 0),
            tags=[],
            language="en",
        )
