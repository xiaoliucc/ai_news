"""GitHub 数据源 — 解析 github.com/trending 与 github.com/explore 页面。

GitHub 无官方 trending/explore API；两页均为服务端渲染的静态 HTML。
- trending 页：每个仓库一个 `<article class="Box-row">`，热度取"今日新增 star"
  （趋势最直接指标），解析失败时回退总 star 数。
- explore 页：推荐仓库区块（`article.border.rounded.color-bg-subtle` 容器），
  无 "stars today" 数据，score 置 0（避免与 trending 的 today 量纲混用霸榜），
  作为 trending 的覆盖面补充。两页结果按仓库 id 合并去重，trending 优先。

注意：github.com 在当前网络环境直连不可达，需配置代理
（.env 的 HTTPS_PROXY，由 backend.config / src.sources.base 统一读取）。

时间戳：两页均不含发布时间，但语义上榜单就是"今天"的数据——
published_at 设为采集时刻，保证卡片时间显示与排序时间衰减正确。
"""

import asyncio
import logging
import re
from datetime import datetime, timezone

import httpx
from bs4 import BeautifulSoup

from src.models import Article
from src.sources.base import PROXY_URL, SourcePlugin

logger = logging.getLogger(__name__)

TRENDING_URL = "https://github.com/trending?since=daily"
EXPLORE_URL = "https://github.com/explore"

# 静态页面需要常规浏览器 UA，避免被识别为爬虫
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/126.0.0.0 Safari/537.36"
)

# 匹配 "+123 stars today" 或 "1,234 stars today"
_STARS_TODAY_RE = re.compile(r"([\d,]+)\s*stars?\s*today", re.IGNORECASE)

# explore 页中非仓库的链接前缀（topics / collections / marketplace 等），解析时排除
_NON_REPO_PREFIXES = (
    "topics/",
    "collections/",
    "marketplace/",
    "sponsors/",
    "trending/",
    "blog/",
    "features/",
    "enterprise/",
    "pricing/",
    "about/",
    "login",
    "signup",
    "settings",
    "search",
    "orgs",
    "explore",
)


class GitHubSource(SourcePlugin):
    """GitHub 热门仓库采集器（Trending + Explore 推荐整合）。

    解析 https://github.com/trending 与 https://github.com/explore 两个页面，
    取仓库列表合并去重：trending 的"今日新增 star"仓库为主，explore 的推荐
    仓库为覆盖面补充。trending 页每页约 25 条，limit 截断取前 N。
    """

    name = "github"

    async def fetch(self, limit: int = 20) -> list[Article]:
        """并发抓取 Trending 与 Explore 页面并合并为 Article 列表。

        Args:
            limit: 最多返回的仓库条数。

        Returns:
            list[Article]: 合并去重后的仓库列表；两页均失败返回空列表。
        """
        headers = {"User-Agent": USER_AGENT}
        now = datetime.now(timezone.utc)
        async with httpx.AsyncClient(
            timeout=10.0,
            proxy=PROXY_URL,
            follow_redirects=True,
            headers=headers,
        ) as client:
            trending_html, explore_html = await asyncio.gather(
                self._safe_get(client, TRENDING_URL),
                self._safe_get(client, EXPLORE_URL),
            )

        articles: list[Article] = []
        if trending_html is not None:
            articles.extend(self._parse_html(trending_html, limit, now))
        if explore_html is not None:
            explore = self._parse_explore_html(explore_html, limit, now)
            articles = _merge_dedup(articles, explore)
        return articles[:limit]

    @staticmethod
    async def _safe_get(client: httpx.AsyncClient, url: str) -> str | None:
        """抓取页面，网络失败返回 None（单页失败不影响另一页）。

        Args:
            client: 复用的 AsyncClient。
            url: 待抓取 URL。

        Returns:
            str | None: 页面 HTML 文本；请求失败返回 None。
        """
        try:
            response = await client.get(url)
            response.raise_for_status()
            return response.text
        except httpx.HTTPError as exc:
            logger.warning("获取 %s 失败: %s", url, exc)
            return None

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

    def _parse_explore_html(
        self,
        html: str,
        limit: int,
        published_at: datetime | None = None,
    ) -> list[Article]:
        """从 explore 页面 HTML 解析推荐仓库列表（纯函数，便于单测）。

        explore 页内容混杂（topics / collections / marketplace / blog 等），
        只提取仓库链接（/owner/repo 形式且排除非仓库前缀），描述与主语言
        取自仓库卡片容器（h3 的祖先 article）。explore 无 "stars today"，
        score 置 0——避免与 trending 的 today 量纲混用导致老牌大仓库霸榜。

        Args:
            html: explore 页面 HTML 文本。
            limit: 最多返回条数。
            published_at: 发布时间（采集时刻）。

        Returns:
            list[Article]: 解析出的仓库列表；无有效仓库返回空列表。
        """
        soup = BeautifulSoup(html, "lxml")
        articles: list[Article] = []
        seen: set[str] = set()
        for h3 in soup.select("h3"):
            link = h3.select_one("a[href]")
            if link is None:
                continue
            href = (link.get("href") or "").strip()
            stripped = href.strip("/")
            parts = stripped.split("/")
            if len(parts) != 2 or not parts[0] or not parts[1]:
                continue
            if stripped.startswith(_NON_REPO_PREFIXES):
                continue
            owner, repo = parts[0], parts[1]

            article_id = f"github_{owner}/{repo}"
            if article_id in seen:
                continue
            seen.add(article_id)

            # 仓库卡片容器：h3 向上找 article（推荐卡片或 Box-row 皆可）
            card = h3.find_parent("article")
            description = None
            language = None
            if card is not None:
                desc_el = card.select_one("p")
                description = desc_el.get_text(strip=True) if desc_el else None
                lang_el = card.select_one('span[itemprop="programmingLanguage"]')
                language = lang_el.get_text(strip=True) if lang_el else None

            articles.append(
                Article(
                    id=article_id,
                    title=f"{owner}/{repo}",
                    url=f"https://github.com/{owner}/{repo}",
                    source=self.name,
                    summary=description,
                    author=owner,
                    published_at=published_at,
                    score=0,  # explore 无 today 数据，避免量纲混用
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


def _merge_dedup(primary: list[Article], secondary: list[Article]) -> list[Article]:
    """合并两页仓库列表并按 id 去重，primary（trending）优先。

    explore 与 trending 页可能存在重叠仓库（如 openai/codex），合并时保留
    primary 版本（其 score 为今日新增 star，explore 版 score=0），secondary
    仅补充 primary 中不存在的仓库。

    Args:
        primary: 主列表（trending，优先保留）。
        secondary: 补充列表（explore）。

    Returns:
        list[Article]: 合并去重后的列表，保持 primary 顺序在前。
    """
    merged: dict[str, Article] = {a.id: a for a in primary}
    for article in secondary:
        merged.setdefault(article.id, article)
    return list(merged.values())


def _parse_int(text: str) -> int | None:
    """解析带千分位逗号的数字文本。

    Args:
        text: 如 "1,234" 或 "123"。

    Returns:
        int | None: 解析出的整数；解析失败返回 None。
    """
    digits = re.sub(r"[^\d]", "", text)
    return int(digits) if digits else None
