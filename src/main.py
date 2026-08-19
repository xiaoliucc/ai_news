"""
CLI 入口 — 从终端采集 AI 新闻并格式化输出。

用法：
    python -m src.main fetch --limit 20
    python -m src.main fetch -s hackernews -o json -f result.json
"""

import sys
from pathlib import Path

# 添加项目根目录到 Python 路径（必须在其他导入之前）
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

import asyncio
import logging

import click

from src.engine import NewsEngine
from src.filters import filter_ai_articles
from src.output import output_json, output_markdown, output_text
from src.sources.hackernews import HackerNewsSource
from src.sources.arxiv import ArxivSource
from src.sources.papers import HuggingFacePaperSource

logger = logging.getLogger(__name__)

# 可用数据源（存类，用到时再实例化）
SOURCES = {
    "hackernews": HackerNewsSource,
    "arxiv": ArxivSource,
    "huggingface_papers": HuggingFacePaperSource,
}

# 输出格式
OUTPUTS = {
    "text": output_text,
    "json": output_json,
    "markdown": output_markdown,
}


@click.group()
def cli():
    """AI Research Intelligence Platform — 聚合 AI 新闻与论文。"""
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    # httpx 默认在 INFO 打印每个请求，压到 WARNING 避免刷屏
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)


@cli.command()
@click.option(
    "--sources", "-s",
    default="hackernews",
    help=f"数据源，逗号分隔。可用: {', '.join(SOURCES)}",
)
@click.option(
    "--limit", "-n",
    default=20,
    type=int,
    help="每源采集条数",
)
@click.option(
    "--output", "-o",
    default="text",
    type=click.Choice(["text", "json", "markdown"]),
    help="输出格式",
)
@click.option(
    "--output-file", "-f",
    default=None,
    type=click.Path(),
    help="写入文件（默认输出到终端）",
)
def fetch(sources: str, limit: int, output: str, output_file: str | None) -> None:
    """从多个数据源采集 AI 新闻，过滤、排序后输出。

    Args:
        sources: 逗号分隔的数据源名称。
        limit: 每源采集条数。
        output: 输出格式（text / json / markdown）。
        output_file: 输出文件路径，None 则输出到终端。
    """
    # 1. 选择数据源
    source_names = [s.strip() for s in sources.split(",")]
    plugins = []
    for name in source_names:
        if name not in SOURCES:
            raise click.ClickException(f"未知数据源: {name}")
        plugins.append(SOURCES[name]())

    # 2. 运行引擎（并发拉取）
    engine = NewsEngine(plugins)
    engine_result = asyncio.run(engine.run(limit=limit))

    # 3. 统计各数据源采集数量
    for stats in engine_result.source_stats:
        if stats.failed:
            logger.error("[%s] 采集失败: %s", stats.name, stats.error)
        else:
            logger.info("[%s] 采集 %s 条，耗时 %sms", stats.name, stats.fetched, stats.elapsed_ms)
    if engine_result.deduped_count:
        logger.info("去重消除 %s 条", engine_result.deduped_count)

    # 4. 过滤
    articles = filter_ai_articles(engine_result.articles)

    # 5. 统计过滤后各数据源保留数量
    logger.info("--- 过滤后 ---")
    for stats in engine_result.source_stats:
        count = sum(1 for a in articles if a.source == stats.name)
        logger.info("[%s] 保留 %s 条", stats.name, count)

    # 6. 格式化
    formatter = OUTPUTS[output]
    result = formatter(articles)

    # 7. 输出
    if output_file:
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(result)
        logger.info("已写入 %s", output_file)
    else:
        click.echo(result)


if __name__ == "__main__":
    cli()
