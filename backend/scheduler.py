import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Type

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from .config import COLLECTION_HOURS, COLLECTION_LIMIT, PROXY_URL, RSS_FEEDS
from .database import get_profile, save_articles
from .vector_store import add_articles
from src.engine import NewsEngine
from src.models import Article
from src.pipeline import llm
from src.sources.arxiv import ArxivSource
from src.sources.base import SourcePlugin
from src.sources.github import GitHubSource
from src.sources.hackernews import HackerNewsSource
from src.sources.papers import HuggingFacePaperSource
from src.sources.rss import RSSSource

logger = logging.getLogger(__name__)

_FILTER_WORKERS = 4  # LLM 过滤并发线程数
_collect_lock = asyncio.Lock()  # 防止定时任务与 trigger_collection 工具并发采集

# 数据源注册表：scheduler 按 user_profile.selected_sources 选择实例化。
# 值为类或工厂函数（rss 需传入 RSS_FEEDS 配置）。
SOURCE_REGISTRY: dict[str, object] = {
    "hackernews": HackerNewsSource,
    "arxiv": ArxivSource,
    "huggingface_papers": HuggingFacePaperSource,
    "rss": lambda: RSSSource(RSS_FEEDS),
    "github": GitHubSource,
}


def _instantiate_source(entry: object) -> SourcePlugin:
    """实例化注册表条目（类或工厂函数均可调用）。

    Args:
        entry: SOURCE_REGISTRY 中的值（源类或返回源实例的工厂）。

    Returns:
        SourcePlugin: 实例化后的数据源插件。
    """
    return entry()


async def _filter_ai_related(articles: list[Article]) -> list[Article]:
    """用 LLM 语义判断过滤 AI 相关文章。

    llm.is_ai_related 是同步阻塞调用（内部走 HTTP），放入有界线程池
    并发执行，避免阻塞 event loop。LLM 不可用或失败时 is_ai_related
    内部自动回退 src.filters 的关键词匹配。

    Args:
        articles: 待过滤的 Article 列表。

    Returns:
        list[Article]: 通过 AI 相关性判断的文章列表（保持原顺序）。
    """
    loop = asyncio.get_running_loop()
    with ThreadPoolExecutor(max_workers=_FILTER_WORKERS) as pool:
        verdicts = await asyncio.gather(
            *(loop.run_in_executor(pool, llm.is_ai_related, a) for a in articles)
        )
    kept = [a for a, ok in zip(articles, verdicts) if ok]
    return kept


def _log_filter_stats(all_articles: list[Article], kept: list[Article]) -> None:
    """按源打印过滤前后数量（沿用 CLI 的逐源统计模式）。

    Args:
        all_articles: 过滤前的文章列表。
        kept: 过滤后保留的文章列表。
    """
    from collections import Counter

    total = Counter(a.source for a in all_articles)
    kept_counter = Counter(a.source for a in kept)
    for name, count in total.items():
        logger.info("[%s] 过滤后保留 %d/%d 条", name, kept_counter.get(name, 0), count)


async def collect_once():
    # 加锁防止定时任务与 trigger_collection 工具并发执行
    async with _collect_lock:
        # 按用户选中的源实例化；空列表=全选
        selected = get_profile().get("selected_sources") or []
        names = list(selected) if selected else list(SOURCE_REGISTRY)
        plugins = [
            _instantiate_source(SOURCE_REGISTRY[name])
            for name in names
            if name in SOURCE_REGISTRY
        ]
        engine = NewsEngine(plugins)
        result = await engine.run(limit=COLLECTION_LIMIT)

        if not result.articles:
            logger.warning("No articles collected this run")
            return

        # AI 相关性过滤（LLM 语义判断优先，失败回退关键词）
        kept = await _filter_ai_related(result.articles)
        if not kept:
            logger.warning("所有文章均未通过 AI 相关性过滤，本轮不入库")
            return
        _log_filter_stats(result.articles, kept)

        run_id = save_articles(
            articles=kept,
            source_stats=result.source_stats,
            deduped_count=result.deduped_count,
        )
        # 同步写入 ChromaDB（to_thread 避免嵌入模型初始化阻塞 event loop）
        indexed = await asyncio.to_thread(add_articles, kept)
        logger.info(
            "Collected %d articles (deduped %d), run_id=%d, chromadb_indexed=%d",
            len(kept),
            result.deduped_count,
            run_id,
            indexed,
        )


_scheduler: AsyncIOScheduler | None = None

def start():
    """启动定时采集调度器。

    立即执行一次采集，之后按 COLLECTION_HOURS 间隔重复。
    重复调用安全——已启动则直接返回。
    """
    global _scheduler
    if _scheduler is not None:
        return

    _scheduler = AsyncIOScheduler()
    _scheduler.add_job(
        collect_once,
        "interval",
        hours=COLLECTION_HOURS,
        id="collect",
        replace_existing=True,
    )
    _scheduler.start()
    logger.info(
        "Scheduler started, interval=%dh, network=%s",
        COLLECTION_HOURS,
        f"proxy {PROXY_URL}" if PROXY_URL else "direct",
    )

    # 启动后立即采集一次，不等第一轮间隔
    asyncio.ensure_future(_collect_now())


async def _collect_now():
    """调度器刚启动时的即时采集，不影响定时周期。"""
    try:
        await collect_once()
    except Exception as exc:
        logger.error("Initial collection failed: %s", exc)


def shutdown():
    """关闭调度器，不再触发新任务。"""
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
        logger.info("Scheduler shut down")


