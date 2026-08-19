"""
Papers With Code 数据源 — 基于 Hugging Face API。

Papers With Code 已被 Hugging Face 收购，原 paperswithcode.com/api/v1 端点已失效。
HF 官方 API:
    https://huggingface.co/api/papers
"""

from datetime import datetime
import logging

import httpx

from src.models import Article
from src.sources.base import SourcePlugin

logger = logging.getLogger(__name__)


class HuggingFacePaperSource(SourcePlugin):
    """Papers With Code 论文采集器（底层使用 Hugging Face API）。

    拉取 HF 每日论文列表，字段映射：publishedAt → datetime，
    upvotes → score，buildSummary → summary。
    """

    base_url = "https://huggingface.co/api"
    name = "huggingface_papers"

    async def fetch(self, limit: int = 20) -> list[Article]:
        """从 Hugging Face 拉取最新 AI 论文。

        Args:
            limit: 最多拉取的论文数。

        Returns:
            list[Article]: 采集到的论文列表。网络错误或数据异常返回空列表。
        """
        articles: list[Article] = []
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                response = await client.get(
                    f"{self.base_url}/papers",
                    params={"limit": limit},
                )
                response.raise_for_status()
                data = response.json()
            except httpx.HTTPError as e:
                logger.warning("获取 Papers 失败: %s", e)
                return []
            except ValueError as e:
                logger.warning("解析 Papers 失败: %s", e)
                return []

            # 检查返回数据是否为列表（API 异常时可能返回 dict）
            if not isinstance(data, list):
                logger.warning("Papers API 返回了非列表数据")
                return []

            for paper in data:
                # 发布时间：ISO 字符串 → datetime（去掉末尾 Z 时区标记）
                published_at = None
                raw_time = paper.get("publishedAt")
                if raw_time:
                    try:
                        published_at = datetime.fromisoformat(
                            raw_time.replace("Z", "+00:00")
                        )
                    except (ValueError, TypeError):
                        published_at = None

                # 作者列表
                authors = paper.get("authors", [])
                author_names = [a.get("name", "") for a in authors if a.get("name")]
                author_str = ", ".join(author_names[:5])
                if len(author_names) > 5:
                    author_str += f" 等{len(author_names)}人"

                # URL：优先 GitHub 仓库，否则 arXiv 页面
                paper_id = paper.get("id", "")
                url = (
                    paper.get("githubRepo")
                    or f"https://arxiv.org/abs/{paper_id}"
                )

                article = Article(
                    id=f"pwc_{paper_id}",
                    title=paper.get("title", "无标题"),
                    url=url,
                    source=self.name,
                    summary=paper.get("summary") or "",
                    author=author_str or None,
                    published_at=published_at,
                    score=paper.get("upvotes", 0),
                    tags=[],
                    language="en",
                )
                articles.append(article)

        return articles
