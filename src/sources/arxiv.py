"""ArXiv 数据源 — 官方 API。

查询 AI 相关分类（cs.AI / cs.CL / cs.CV / cs.LG 等），按提交日期降序返回。
"""

import asyncio
import logging

import arxiv

from src.models import Article
from src.sources.base import SourcePlugin

logger = logging.getLogger(__name__)


class ArxivSource(SourcePlugin):
    """ArXiv 论文采集器。

    通过 arxiv 官方库查询 11 个 AI 相关分类的最新论文。
    同步 Client 通过 asyncio.to_thread 包装为异步。
    """

    categories = [
        "cs.AI",   # 人工智能
        "cs.CL",   # 计算语言学（自然语言处理）
        "cs.CV",   # 计算机视觉与模式识别
        "cs.IR",   # 信息检索
        "cs.LG",   # 机器学习
        "cs.MA",   # 多智能体系统
        "cs.MM",   # 多媒体
        "cs.NE",   # 神经与进化计算
        "cs.RO",   # 机器人学
        "cs.SD",   # 声音
        "cs.SY",   # 系统与控制
    ]

    name = "arxiv"

    arxiv_client = arxiv.Client(
        page_size=20,
        num_retries=3,
        delay_seconds=3,
    )

    async def fetch(self, limit: int = 20) -> list[Article]:
        """从 ArXiv 拉取最新 AI 论文。

        按提交日期降序排列，查询所有 AI 分类的 OR 组合。

        Args:
            limit: 最多拉取的论文数。

        Returns:
            list[Article]: 采集到的论文列表。网络错误返回空列表。
        """
        query = " OR ".join(f"cat:{c}" for c in self.categories)
        search = arxiv.Search(
            query=query,
            max_results=limit,
            sort_by=arxiv.SortCriterion.SubmittedDate,
            sort_order=arxiv.SortOrder.Descending,
        )
        try:
            results = await asyncio.to_thread(
                lambda: list(self.arxiv_client.results(search))
            )
        except Exception as e:
            logger.warning("[Arxiv] 获取失败: %s", e)
            return []

        articles = []
        for result in results:
            articles.append(
                Article(
                    id=f"arxiv_{result.get_short_id()}",
                    title=result.title,
                    url=result.entry_id,
                    source=self.name,
                    summary=result.summary,
                    author=", ".join(author.name for author in result.authors),
                    published_at=result.published,
                    score=0,
                    tags=[str(result.primary_category)],
                    language="en",
                )
            )

        return articles
