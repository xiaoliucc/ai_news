"""POST /api/collect 路由测试 — 手动触发采集（后台执行，202 立即返回）。"""

import asyncio

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from unittest.mock import AsyncMock, patch

from backend.routers.collect import _background_tasks, router

# 创建测试用 app
app = FastAPI()
app.include_router(router)


@pytest.fixture
def mock_collect_once():
    with patch("backend.routers.collect.collect_once", new_callable=AsyncMock) as mock:
        yield mock


@pytest.fixture(autouse=True)
def clear_background_tasks():
    """每个用例结束后清理后台任务，避免跨用例串扰。"""
    yield
    for t in list(_background_tasks):
        if not t.done():
            t.cancel()
    _background_tasks.clear()


@pytest.mark.asyncio
async def test_trigger_collection_returns_202_and_runs(mock_collect_once):
    """接口 202 + started，后台任务被调度并完成，collect_once 被调用。"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.post("/api/collect")

    assert response.status_code == 202
    assert response.json() == {"status": "started"}

    # 后台任务与测试同 loop（AsyncClient 在同一事件循环），可确定性等待
    assert len(_background_tasks) == 1
    task = next(iter(_background_tasks))
    await asyncio.wait_for(task, timeout=5)
    mock_collect_once.assert_awaited_once()


@pytest.mark.asyncio
async def test_collection_exception_does_not_crash_endpoint(mock_collect_once):
    """后台采集抛异常时接口不受影响，任务正常结束（异常被 _run_collection 吞掉）。"""
    mock_collect_once.side_effect = RuntimeError("boom")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.post("/api/collect")

    assert response.status_code == 202
    task = next(iter(_background_tasks))
    await asyncio.wait_for(task, timeout=5)
    assert task.done()
    assert not task.cancelled()
