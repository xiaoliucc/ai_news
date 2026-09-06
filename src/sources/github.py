"""GitHub 数据源 — 解析 github.com/trending / explore / topics 页面。

GitHub 无官方 trending/explore/topics API；页面均为服务端渲染的静态 HTML。
- trending 页：每个仓库一个 `<article class="Box-row">`，热度取"今日新增 star"
  （趋势最直接指标），解析失败时回退总 star 数。
- explore 页：推荐仓库区块（`article.border.rounded.color-bg-subtle` 容器），
  无 "stars today" 数据，score 置 0（避免与 trending 的 today 量纲混用霸榜），
  作为 trending 的覆盖面补充。
- topics 页：AI 主题仓库榜（`?o=desc&s=updated` 按最近活跃排序，每天有变化），
  与 explore 同语义 score=0；行内 `relative-time[datetime]` 提供真实活跃时间，
  published_at 取其值（解析失败回退采集时刻）。
trending 为主列表，explore / topics 按仓库 id 合并去重补充，trending 优先。

注意：github.com 在当前网络环境直连不可达，需配置代理
（.env 的 HTTPS_PROXY，由 backend.config / src.sources.base 统一读取）。
"""

import asyncio
import logging
import os
import re
from datetime import datetime, timezone

import httpx
from bs4 import BeautifulSoup

from src.models import Article
from src.sources.base import PROXY_URL, SourcePlugin

logger = logging.getLogger(__name__)

TRENDING_URL = "https://github.com/trending?since=daily"
EXPLORE_URL = "https://github.com/explore"
# topics 页 URL：?o=desc&s=updated 按最近活跃排序（每天真实变化，区别于 trending 顶部稳定）
TOPIC_URL_TMPL = "https://github.com/topics/{topic}?o=desc&s=updated"

# 默认采集的 AI 相关主题（.env GITHUB_TOPICS 可覆盖，逗号分隔）
DEFAULT_TOPICS = ("llm", "machine-learning", "agent")

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


def _resolve_topics(raw: str) -> tuple[str, ...]:
    """解析 GITHUB_TOPICS 配置：逗号分隔的 topic slug 列表。

    Args:
        raw: .env GITHUB_TOPICS 原始值（如 "llm,agents,rag"）。

    Returns:
        tuple[str, ...]: 清洗后的 topic slug；配置为空时用内置默认主题。
    """
    configured = tuple(t.strip().lower() for t in raw.split(",") if t.strip())
    return configured or DEFAULT_TOPICS


# 待采集的主题列表（.env GITHUB_TOPICS 可覆盖；backend 进程由 load_dotenv 注入）
TOPICS = _resolve_topics(os.getenv("GITHUB_TOPICS", ""))


class GitHubSource(SourcePlugin):
    """GitHub 热门仓库采集器（Trending + Explore + Topics 整合）。

    解析 trending / explore / 各 topic 页面取仓库列表合并去重：
    trending 的"今日新增 star"仓库为主，explore 推荐与 topics 活跃仓库
    为覆盖面补充。trending 页每页约 25 条；coverage 页返回数量受
    fetch 总配额（limit + 1/3 limit）控制，保证覆盖面有可见贡献。
    """

    name = "github"

    async def fetch(self, limit: int = 20) -> list[Article]:
        """并发抓取 Trending / Explore / Topics 页面并合并为 Article 列表。

        Args:
            limit: 主列表（trending）的条数上限；coverage 页配额为 limit//3。

        Returns:
            list[Article]: 合并去重后的仓库列表；全部页面失败返回空列表。
        """
        headers = {"User-Agent": USER_AGENT}
        now = datetime.now(timezone.utc)
        urls = [TRENDING_URL, EXPLORE_URL] + [
            TOPIC_URL_TMPL.format(topic=t) for t in TOPICS
        ]
        async with httpx.AsyncClient(
            timeout=10.0,
            proxy=PROXY_URL,
            follow_redirects=True,
            headers=headers,
        ) as client:
            pages = await asyncio.gather(
                *[self._safe_get(client, url) for url in urls]
            )

        articles: list[Article] = []
        # 主列表（trending）截 limit；coverage 页（explore + topics）各截 limit//3
        if pages[0] is not None:
            articles.extend(self._parse_html(pages[0], limit, now))
        cov_limit = max(limit // 3, 3)
        if pages[1] is not None:
            # explore 推荐页：无活跃时间，回退采集时刻
            articles = _merge_dedup(
                articles,
                self._parse_repo_page_html(pages[1], cov_limit, now, use_updated=False),
            )
        for page in pages[2:]:
            if page is None:
                continue
            # topics 活跃榜：行内 relative-time 提供真实活跃时间
            articles = _merge_dedup(
                articles,
                self._parse_repo_page_html(page, cov_limit, now, use_updated=True),
            )
        # 总配额 = limit + coverage 单页配额——保证补充页在 trending 满量时仍有可见贡献
        return articles[: limit + cov_limit]

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

    def _parse_repo_page_html(
        self,
        html: str,
        limit: int,
        published_at: datetime | None = None,
        use_updated: bool = False,
    ) -> list[Article]:
        """从仓库列表页 HTML 解析仓库列表（explore 推荐 / topics 活跃榜通用）。

        explore 页内容混杂（topics / collections / marketplace / blog 等），
        topics 页每行一个仓库卡片——两页的仓库链接都在 h3 内。两页均无
        "stars today"，score 置 0——避免与 trending 的 today 量纲混用导致
        老牌大仓库霸榜。use_updated=True 时（topics 页）取行内
        `relative-time[datetime]` 的真实活跃时间作为 published_at，
        保证 1d/3d/7d 时间窗口与时间衰减反映"最近活跃"而非采集时刻。

        Args:
            html: 列表页 HTML 文本。
            limit: 最多返回条数。
            published_at: 回退发布时间（explore 无日期，用采集时刻）。
            use_updated: True 时优先取行内 relative-time 的活跃时间。

        Returns:
            list[Article]: 解析出的仓库列表；无有效仓库返回空列表。
        """
        soup = BeautifulSoup(html, "lxml")
        articles: list[Article] = []
        seen: set[str] = set()
        for h3 in soup.select("h3"):
            repo = self._repo_article_from_h3(h3, published_at, use_updated)
            if repo is None or repo.id in seen:
                continue
            seen.add(repo.id)
            articles.append(repo)
            if len(articles) >= limit:
                break
        return articles

    def _repo_article_from_h3(
        self,
        h3,
        published_at: datetime | None,
        use_updated: bool,
    ) -> Article | None:
        """从含仓库链接的 h3 元素构造 Article（纯函数，便于单测）。

        h3 内可能含多个链接（owner 用户页 + 仓库页，如 topics 行），
        取第一个符合 owner/repo 两段形式的仓库链接；描述/主语言/活跃时间
        从 h3 向上的 article 卡片容器提取。

        Args:
            h3: BeautifulSoup 的 h3 元素。
            published_at: 回退发布时间（采集时刻）。
            use_updated: True 时优先取行内 relative-time 的活跃时间。

        Returns:
            Article | None: 构造的仓库文章；h3 无有效仓库链接返回 None。
        """
        for link in h3.select("a[href]"):
            href = (link.get("href") or "").strip()
            stripped = href.strip("/")
            parts = stripped.split("/")
            if len(parts) != 2 or not parts[0] or not parts[1]:
                continue
            if stripped.startswith(_NON_REPO_PREFIXES):
                continue
            owner, repo = parts[0], parts[1]

            card = h3.find_parent("article")
            description = None
            language = None
            updated_at = published_at
            if card is not None:
                desc_el = card.select_one("p")
                description = desc_el.get_text(strip=True) if desc_el else None
                lang_el = card.select_one('span[itemprop="programmingLanguage"]')
                language = lang_el.get_text(strip=True) if lang_el else None
                if use_updated:
                    rel = card.select_one("relative-time[datetime]")
                    if rel is not None:
                        raw = (rel.get("datetime") or "").replace("Z", "+00:00")
                        try:
                            updated_at = datetime.fromisoformat(raw)
                        except ValueError:
                            pass  # 日期格式异常时回退采集时刻

            return Article(
                id=f"github_{owner}/{repo}",
                title=f"{owner}/{repo}",
                url=f"https://github.com/{owner}/{repo}",
                source=self.name,
                summary=description,
                author=owner,
                published_at=updated_at,
                score=0,  # 无 today 数据，避免量纲混用
                tags=[language] if language else [],
                language="en",
            )
        return None


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
