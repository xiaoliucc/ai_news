"""CSDN 热榜数据源 — 解析博客热榜 JSON API。

CSDN 热榜无公开文档，博客前端自用接口（页面结构常变而 JSON 接口稳定）：
    GET https://blog.csdn.net/phoenix/web/blog/hot-rank?page=0&pageSize=25
返回 JSON `{"code": 200, "data": [...]}`，每条含 articleTitle /
articleDetailUrl / productId / nickName / viewCount 等。数字字段
（viewCount / favorCount / hotRankScore）为**字符串**（个别还带 "w" 万
单位），解析时按纯数字提取。文章以中文技术内容为主（AI / 大模型 / 鸿蒙
等），与平台"中文源"定位一致，language="zh"。

无发布时间字段 → published_at 统一取采集时刻（与 GitHub 同法）。
直连访问（国内站），不依赖 HTTPS_PROXY 代理——墙外源才需要代理。
"""

import logging
import re
from datetime import datetime, timezone

import httpx

from src.models import Article
from src.sources.base import SourcePlugin

logger = logging.getLogger(__name__)

HOT_RANK_URL = "https://blog.csdn.net/phoenix/web/blog/hot-rank"

# 静态接口常规浏览器 UA，降低被风控的概率
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/126.0.0.0 Safari/537.36"
)

# 从文章 URL 提取数字 ID（/details/164109036），productId 缺失时回退
_DETAILS_ID_RE = re.compile(r"/details/(\d+)")


def _to_int(value: object) -> int:
    """把可能带字符串形态的数字（"2333"）解析为 int；失败返回 0。

    CSDN 接口数字字段均为字符串，个别带 "w" 万单位（如 "2.5w"）——
    只取数字部分，单位与量级差异不处理（不影响同源排序）。

    Args:
        value: 原始字段值（str / int / None）。

    Returns:
        int: 解析出的整数；无法解析返回 0。
    """
    digits = re.sub(r"[^\d]", "", str(value))
    return int(digits) if digits else 0


class CsdnSource(SourcePlugin):
    """CSDN 博客热榜采集器（中文技术社区）。

    请求 phoenix hot-rank JSON 接口（单次一页），热度取 viewCount
    （浏览量——热榜的直观度量，区分度好），标题/作者取文章字段，
    ID 取 productId（URL /details/ 提取作回退）。
    """

    name = "csdn"

    async def fetch(self, limit: int = 20) -> list[Article]:
        """抓取 CSDN 热榜并解析为 Article 列表。

        Args:
            limit: 最多返回的文章条数（接口单页上限约 25）。

        Returns:
            list[Article]: 解析出的文章列表；网络/解析失败返回空列表。
        """
        try:
            async with httpx.AsyncClient(
                timeout=10.0,
                follow_redirects=True,
                headers={"User-Agent": USER_AGENT},
            ) as client:
                # 直连（国内站）：不传 proxy，代理仅服务墙外源
                response = await client.get(
                    HOT_RANK_URL,
                    params={"page": 0, "pageSize": min(limit, 25)},
                )
                response.raise_for_status()
                data = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            logger.warning("获取 CSDN 热榜失败: %s", exc)
            return []

        # 热榜即"现在"的数据，无发布时间字段——统一取采集时刻
        return self._parse_rows(
            data.get("data") if isinstance(data, dict) else None,
            limit,
            published_at=datetime.now(timezone.utc),
        )

    def _parse_rows(
        self,
        rows: list[dict] | None,
        limit: int,
        published_at: datetime | None = None,
    ) -> list[Article]:
        """从热榜 JSON 的 data 列表解析文章（纯函数，便于单测）。

        每条约：{articleTitle, articleDetailUrl, productId, nickName,
        viewCount, ...}。ID 取 productId（纯数字字符串），缺失时从 URL
        /details/{id} 提取；两者皆无或标题为空的条目跳过。

        Args:
            rows: hot-rank 接口返回的 data 列表（可为 None）。
            limit: 最多返回条数。
            published_at: 发布时间（接口无日期，由调用方传入采集时刻）。

        Returns:
            list[Article]: 解析出的文章列表。
        """
        articles: list[Article] = []
        if not rows:
            return articles
        seen: set[str] = set()
        for row in rows:
            if not isinstance(row, dict):
                continue
            url = (row.get("articleDetailUrl") or "").strip()

            # ID：productId 字段优先（纯数字字符串），URL 提取作回退
            product_id = (row.get("productId") or "").strip()
            digits = product_id if product_id.isdigit() else None
            if digits is None:
                match = _DETAILS_ID_RE.search(url)
                if match is None:
                    continue
                digits = match.group(1)
            article_id = f"csdn_{digits}"
            if article_id in seen:
                continue
            seen.add(article_id)

            title = (row.get("articleTitle") or "").strip()
            if not title:
                continue
            author = (row.get("nickName") or "").strip() or None

            articles.append(
                Article(
                    id=article_id,
                    title=title,
                    url=url,
                    source=self.name,
                    summary=None,  # 接口不含正文摘要
                    author=author,
                    published_at=published_at,
                    score=_to_int(row.get("viewCount")),  # 浏览量作热度
                    tags=[],
                    language="zh",
                )
            )
            if len(articles) >= limit:
                break
        return articles
