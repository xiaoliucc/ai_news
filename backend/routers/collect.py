"""手动采集路由 — 触发一次全量采集（后台执行，立即返回）。"""

import asyncio
import logging

from fastapi import APIRouter

from backend.scheduler import collect_once

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["collect"])

# 持有后台任务引用，防止 asyncio.create_task 的任务被 GC 回收后静默取消
_background_tasks: set[asyncio.Task] = set()


@router.post("/collect", status_code=202)
async def trigger_collection() -> dict:
    """手动触发一次全量采集。

    采集在后台任务中执行（LLM 过滤可能耗时数十秒），接口立即返回 202；
    前端可随后轮询 GET /api/stats 观察结果。与 Agent 的
    TRIGGER_COLLECTION 工具共用 `scheduler.collect_once()`，`_collect_lock`
    保证不会并发执行。

    Returns:
        dict: {"status": "started"}。
    """
    task = asyncio.create_task(_run_collection())
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)
    logger.info("Manual collection triggered via POST /api/collect")
    return {"status": "started"}


async def _run_collection() -> None:
    """后台执行采集；异常只记日志，不抛出（采集失败不影响接口）。"""
    try:
        await collect_once()
    except Exception:
        logger.exception("Manual collection failed")
