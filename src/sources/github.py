"""GitHub Trending 数据源 — 解析 github.com/trending 页面。

GitHub 无官方 trending API；页面为服务端渲染的静态 HTML，
每个仓库一个 `<article class="Box-row">`。热度取"今日新增 star"（趋势
最直接指标），解析失败时回退总 star 数。

注意：github.com 在当前网络环境直连不可达，需配置代理
（.env 的 HTTPS_PROXY，由 backend.config / src.sources.base 统一读取）。

时间戳：trending 页面不含发布时间，但语义上榜单就是"今天"的数据——
published_at 设为采集时刻，保证卡片时间显示与排序时间衰减正确。
"""

import logging
import re
from datetime import datetime, timezone

import httpx
from bs4 import BeautifulSoup

from src.models import Article
from src.sources.base import PROXY_URL, SourcePlugin

logger = logging.getLogger(__name__)

TRENDING_URL = "https://github.com/trending?since=daily"

# 静态页面需要常规浏览器 UA，避免被识别为爬虫
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/126.0.0.0 Safari/537.36"
)

# 匹配 "+123 stars today" 或 "1,234 stars today"
_STARS_TODAY_RE = re.compile(r"([\d,]+)\s*stars?\s*today", re.IGNORECASE)


class GitHubSource(SourcePlugin):
    """GitHub Trending 今日热门仓库采集器。

    解析 https://github.com/trending 页面，取今日新增 star 最多的仓库
    列表。页面为静态 HTML，无分页参数（每页约 25 条），limit 截断取前 N。
    """

    name = "github"

    async def fetch(self, limit: int = 20) -> list[Article]:
        """抓取 GitHub Trending 页面并解析为 Article 列表。

        Args:
            limit: 最多返回的仓库条数。

        Returns:
            list[Article]: 解析出的仓库列表；网络错误返回空列表。
        """
        async with httpx.AsyncClient(
            timeout=10.0,
            proxy=PROXY_URL,
            follow_redirects=True,
            headers={"User-Agent": USER_AGENT},
        ) as client:
            try:
                response = await client.get(TRENDING_URL)
                response.raise_for_status()
            except httpx.HTTPError as e:
                logger.warning("获取 GitHub Trending 失败: %s", e)
                return []
        # 榜单无发布时间，语义上即"今天"——统一取采集时刻
        return self._parse_html(response.text, limit, published_at=datetime.now(timezone.utc))

    def _parse_html(
        self,
        html: str,
        limit: int,
        published_at: datetime | None = None,
    ) -> list[Article]:
        """从 trending 页面 HTML 解析仓库列表（纯函数，便于单测）。

        每个仓库一个 `<article class="Box-row">`：
            h2 a                 — 仓库链接（/owner/repo）
            p                    — 描述
            span[itemprop="programmingLanguage"] — 主语言
            "N stars today" 文本 — 今日新增 star（热度）
            a[href$="/stargazers"] — 总 star 数（回退用）

        Args:
            html: trending 页面 HTML 文本。
            limit: 最多返回条数。
            published_at: 发布时间（trending 无日期，由调用方传入采集时刻）。

        Returns:
            list[Article]: 解析出的仓库列表；无有效仓库返回空列表。
        """
        soup = BeautifulSoup(html, "lxml")
        articles: list[Article] = []
        for row in soup.select("article.Box-row"):
            link = row.select_one("h2 a")
            if link is None:
                continue
            path = (link.get("href") or "").strip().strip("/")
            parts = path.split("/")
            if len(parts) < 2 or not parts[0] or not parts[1]:
                continue
            owner, repo = parts[0], parts[1]

            desc_el = row.select_one("p")
            description = desc_el.get_text(strip=True) if desc_el else None

            lang_el = row.select_one('span[itemprop="programmingLanguage"]')
            language = lang_el.get_text(strip=True) if lang_el else None

            # 今日新增 star：优先"stars today"文本，回退总 star 数
            score = _extract_stars_today(row.get_text(" ", strip=True))
            if score is None:
                stars_el = row.select_one('a[href$="/stargazers"]')
                if stars_el is not None:
                    score = _parse_int(stars_el.get_text(strip=True))

            articles.append(
                Article(
                    id=f"github_{owner}/{repo}",
                    title=f"{owner}/{repo}",
                    url=f"https://github.com/{owner}/{repo}",
                    source=self.name,
                    summary=description,
                    author=owner,
                    published_at=published_at,
                    score=score or 0,
                    tags=[language] if language else [],
                    language="en",
                )
            )
            if len(articles) >= limit:
                break
        return articles


def _extract_stars_today(text: str) -> int | None:
    """从行文本提取今日新增 star 数。

    Args:
        text: 仓库行元素的拼接文本。

    Returns:
        int | None: 今日新增 star 数；无匹配返回 None。
    """
    match = _STARS_TODAY_RE.search(text)
    if not match:
        return None
    return _parse_int(match.group(1))


def _parse_int(text: str) -> int | None:
    """解析带千分位逗号的数字文本。

    Args:
        text: 如 "1,234" 或 "123"。

    Returns:
        int | None: 解析出的整数；解析失败返回 None。
    """
    digits = re.sub(r"[^\d]", "", text)
    return int(digits) if digits else None
