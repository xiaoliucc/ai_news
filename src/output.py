"""
文章输出模块

将 Article 列表以不同格式输出，方便终端查看或管道给其他工具。

职责：
    - 纯文本格式 — 一行一条，快速浏览
    - JSON 格式 — 完整字段，方便管道 / 存文件
    - Markdown 格式 — 适合生成日报
    - Rich 表格 — 终端美观展示（后续扩展）

依赖：
    src/models.py — Article 数据类
"""

import json
from datetime import datetime

from src.models import Article


def _format_time(article: Article) -> str:
    """将文章发布时间转为可读字符串。

    Args:
        article: 待格式化的 Article 对象。

    Returns:
        str: "YYYY-MM-DD HH:MM:SS" 格式的时间字符串，无时间戳返回 "未知"。
    """
    if article.published_at:
        return article.published_at.strftime("%Y-%m-%d %H:%M:%S")
    return "未知"


def output_text(articles: list[Article]) -> str:
    """将文章列表输出为纯文本格式。

    包含来源、分数、时间、标题和链接，适合终端快速浏览。

    Args:
        articles: 待输出的文章列表。

    Returns:
        str: 格式化后的文本（含标题头和分隔线）。
    """
    if not articles:
        return "暂无文章"

    lines = []
    for a in articles:
        lines.append(
            f"[{a.source:<12} ↑{a.score:<5} {_format_time(a)}]  {a.title}\n"
            f"{a.url}\n"
        )
    header = (
        f"{len(articles)} 条文章，更新于 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        + "-" * 80
        + "\n"
    )
    return header + "\n\n".join(lines)


def output_json(articles: list[Article]) -> str:
    """将文章列表输出为 JSON 格式。

    完整输出所有字段，datetime 转为 ISO 8601 字符串。

    Args:
        articles: 待输出的文章列表。

    Returns:
        str: 缩进 2 空格的 JSON 字符串。
    """

    def to_dict(a: Article) -> dict:
        """将单个 Article 转为可 JSON 序列化的字典。

        Args:
            a: Article 对象。

        Returns:
            dict: 包含所有字段的字典，published_at 转为 ISO 8601 或 null。
        """
        return {
            "id": a.id,
            "title": a.title,
            "url": a.url,
            "source": a.source,
            "summary": a.summary,
            "author": a.author,
            "published_at": a.published_at.isoformat() if a.published_at else None,
            "score": a.score,
            "tags": a.tags,
            "language": a.language,
        }

    return json.dumps([to_dict(a) for a in articles], ensure_ascii=False, indent=2)


def output_markdown(articles: list[Article]) -> str:
    """将文章列表输出为 Markdown 格式。

    每条文章以三级标题呈现，含来源、热度、时间和链接。

    Args:
        articles: 待输出的文章列表。

    Returns:
        str: Markdown 格式的文本。
    """
    if not articles:
        return "暂无文章"

    lines = [f"## 共 {len(articles)} 条\n"]
    for a in articles:
        lines.append(
            f"### {a.title}\n"
            f"- **来源**: {a.source} | **热度**: {a.score} | **时间**: {_format_time(a)}\n"
            f"- **链接**: {a.url}"
        )

    return "\n\n".join(lines)
