"""
测试 Agent 端到端链路（integration）。

说明：`chat()`（非流式副本）已于 2026-11-01 删除——`chat_stream()` 成为唯一循环。
单元行为（事件序列、工具轮、prompt 注入）见 tests/backend/agent/test_core_stream.py；
此文件只保留需要真实网络 + API key 的完整链路。
"""

import os

import pytest

from backend.agent.core import chat_stream
from backend import vector_store
from src.engine import NewsEngine
from src.sources.arxiv import ArxivSource
from src.sources.hackernews import HackerNewsSource
from src.sources.papers import HuggingFacePaperSource


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.skipif(
    not os.getenv("DEEPSEEK_API_KEY"),
    reason="未配置 DEEPSEEK_API_KEY",
)
async def test_agent_full_flow():
    """完整链路：真实采集 3 个源 → 注入向量库 → Agent 流式对话产出 done。"""
    vector_store._reset()
    try:
        engine = NewsEngine(
            [HackerNewsSource(), ArxivSource(), HuggingFacePaperSource()]
        )
        result = await engine.run(limit=3)
        assert result.articles, "采集结果不应为空"

        vector_store.add_articles(result.articles)
        events = [
            ev
            async for ev in chat_stream(
                "请从已采集的数据中搜索一篇关于大模型或 Agent 的文章，并用中文总结。"
            )
        ]

        done = [e for e in events if e["type"] == "done"]
        assert done, f"应产出 done 事件，实际事件序列: {events}"
        answer = done[-1]["answer"]
        assert answer, "Agent 不应返回空回答"
        assert "未配置" not in answer
    finally:
        vector_store._reset()
