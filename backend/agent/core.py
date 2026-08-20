"""
Agent 主循环 — LLM + tool-use 模式（非 LangChain）。

工作流程：
    1. 接收用户消息（含对话历史）
    2. 调用 LLM（带 tools 定义 + system prompt）
    3. 若 LLM 返回 tool_calls → 执行对应工具 → 把结果回传给 LLM → 重复
    4. 否则直接返回文本回复

依赖：
    openai SDK（OpenAI 兼容端点，DeepSeek）— 通过 src/pipeline/llm.py 的 _get_client
    backend/agent/prompts.py — build_system_prompt
    backend/agent/tools.py  — TOOLS / EXECUTOR
"""

import asyncio
import json
import logging

from . import prompts, tools
from src.pipeline.llm import _get_client, _model_id

logger = logging.getLogger(__name__)

MAX_TOOL_CALLS = 5  # 单次对话最多连续调用工具的次数，防止死循环


def _json(data: dict) -> str:
    """将 dict 转为 JSON 字符串。

    ensure_ascii=False 保持中文可读，紧凑分隔符节省 token。

    Args:
        data: 待序列化的字典。

    Returns:
        str: JSON 字符串（无缩进，无 ASCII 转义）。
    """
    return json.dumps(data, ensure_ascii=False, separators=(",", ":"))


def _tool_call_messages(replay) -> list[dict]:
    """从 LLM 响应中提取 assistant 消息（含 tool_calls）。

    将 OpenAI API 返回的 tool_calls 转换为符合 chat completion API
    要求的 assistant role 消息格式。

    Args:
        replay: OpenAI API 的 chat.completions.create 返回值。

    Returns:
        list[dict]: 包含一条 assistant 消息的列表。
    """
    assistant_msg = {
        "role": "assistant",
        "content": replay.choices[0].message.content,
        "tool_calls": [
            {
                "id": tc.id,
                "type": "function",
                "function": {
                    "name": tc.function.name,
                    "arguments": tc.function.arguments,
                },
            }
            for tc in replay.choices[0].message.tool_calls
        ],
    }
    return [assistant_msg]


def _has_tool_calls(replay) -> bool:
    """判断 LLM 响应是否要求调用工具。

    Args:
        replay: OpenAI API 的 chat.completions.create 返回值。

    Returns:
        bool: 有 tool_calls 返回 True，纯文本回复返回 False。
    """
    choice = replay.choices[0]
    return (
        choice.finish_reason == "tool_calls"
        or getattr(choice.message, "tool_calls", None)
    )


async def _execute_tool(call, retry_count: int = 1) -> str:
    """执行单个工具调用，返回 JSON 字符串。

    从 EXECUTOR 查表获取实现函数，解析 arguments 后执行。
    失败自动重试一次。

    Args:
        call: OpenAI API 返回的 tool_call 对象（含 function.name 和 function.arguments）。
        retry_count: 失败重试次数，默认 1 次（即最多执行 2 次）。

    Returns:
        str: 工具执行结果的 JSON 字符串，或错误描述。
    """
    name = call.function.name
    fn = tools.EXECUTOR.get(name)
    if fn is None:
        return _json({"error": f"工具 {name} 不存在。"})

    try:
        args = json.loads(call.function.arguments or "{}")
    except json.JSONDecodeError as exc:
        logger.warning("工具 %s 参数解析失败: %s", name, exc)
        return _json({"error": "工具参数不是合法 JSON"})

    last_error: Exception | None = None
    for attempt in range(retry_count + 1):
        try:
            result = await fn(args)
            return result if isinstance(result, str) else _json(result)
        except Exception as exc:  # noqa: BLE001 — 单工具失败不中断对话
            last_error = exc
            logger.warning("工具 %s 执行失败（第 %s 次）: %s", name, attempt + 1, exc)

    return _json({"error": f"工具执行失败: {last_error}"})


async def chat(
    message: str,
    history: list[dict] | None = None,
    interests: list[str] | None = None,
    reading_history: list[str] | None = None,
    conversation_summary: str | None = None,
) -> str:
    """执行一轮 Agent 对话（非流式）。

    流程：构建消息列表（system prompt + history + user message）
    → 调用 LLM（带 tools）→ 有 tool_calls 则并发执行工具并回传结果
    → 重复（最多 MAX_TOOL_CALLS 轮）。独立工具之间并发执行。

    Args:
        message: 用户输入文本。
        history: 对话历史，格式 [{"role": "user"/"assistant", "content": "..."}, ...]。
        interests: 用户关注方向，注入 system prompt 用于排序和筛选。
        reading_history: 用户最近读过的文章标题列表，注入 prompt 避免重复推荐。
        conversation_summary: 跨会话对话摘要（P2），注入 prompt 提供历史结论。

    Returns:
        str: LLM 最终回复文本。LLM 未配置时返回配置提示。
    """
    client = _get_client()
    if client is None:
        return "LLM 未配置，请在 .env 中设置 DEEPSEEK_API_KEY。"

    system_prompt = prompts.build_system_prompt(
        interests=interests,
        reading_history=reading_history,
        conversation_summary=conversation_summary,
    )
    messages: list[dict] = [{"role": "system", "content": system_prompt}]
    if history:
        messages.extend(history)
    messages.append({"role": "user", "content": message})

    for _ in range(MAX_TOOL_CALLS):
        replay = await asyncio.to_thread(
            client.chat.completions.create,
            model=_model_id(),
            messages=messages,
            tools=tools.TOOLS,
        )
        if not _has_tool_calls(replay):
            return replay.choices[0].message.content or "暂无内容。"

        tool_calls = replay.choices[0].message.tool_calls
        if not tool_calls:
            return replay.choices[0].message.content or "暂无内容。"

        # 追加 assistant 消息（含 tool_calls）
        messages.extend(_tool_call_messages(replay))

        # 并发执行所有独立工具，结果逐条追加
        tool_results = await asyncio.gather(
            *[_execute_tool(call) for call in tool_calls]
        )
        for call, result in zip(tool_calls, tool_results):
            messages.append({
                "role": "tool",
                "tool_call_id": call.id,
                "content": result,
            })

    return "LLM 调用工具次数过多，请简化问题后重试。"
