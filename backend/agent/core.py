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
import queue
from types import SimpleNamespace

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

    for turn in range(MAX_TOOL_CALLS):
        replay = await asyncio.to_thread(
            client.chat.completions.create,
            model=_model_id(),
            messages=messages,
            tools=tools.TOOLS,
        )
        if not _has_tool_calls(replay):
            content = replay.choices[0].message.content or "暂无内容。"
            logger.info("Agent 完成: %d 轮工具循环, 回复 %d 字", turn, len(content))
            return content

        tool_calls = replay.choices[0].message.tool_calls
        if not tool_calls:
            content = replay.choices[0].message.content or "暂无内容。"
            logger.info("Agent 完成: %d 轮工具循环, 回复 %d 字", turn, len(content))
            return content

        logger.info(
            "Agent 第 %d 轮调用工具: %s",
            turn + 1,
            ", ".join(c.function.name for c in tool_calls),
        )

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

    logger.warning("Agent 工具循环超过 %d 轮上限", MAX_TOOL_CALLS)
    return "LLM 调用工具次数过多，请简化问题后重试。"


# ==================== 流式版本（SSE 真流式） ====================
# 事件协议（yield dict，路由层序列化为 SSE）：
#   {"type": "tool", "name": "<工具名>", "status": "start"|"done"}
#   {"type": "token", "text": "<LLM 流式增量>"}
#   {"type": "done", "answer": "<完整答案>"}
#   {"type": "error", "message": "<错误描述>"}
# 工具调用轮次的 LLM 响应不向客户端透出 token（模型输出的是 tool_calls JSON），
# 只发 tool start/done 事件；最终答案轮边收边发 token —— 首 token 延迟大幅下降。


def _build_messages(
    message: str,
    history: list[dict] | None,
    interests: list[str] | None,
    reading_history: list[str] | None,
    conversation_summary: str | None,
) -> list[dict]:
    """构建 Agent 消息列表（system prompt + history + 用户消息）。

    Args:
        message: 用户输入文本。
        history: 对话历史。
        interests: 用户关注方向。
        reading_history: 阅读历史标题。
        conversation_summary: 跨会话摘要。

    Returns:
        list[dict]: 完整的 chat completion 消息列表。
    """
    system_prompt = prompts.build_system_prompt(
        interests=interests,
        reading_history=reading_history,
        conversation_summary=conversation_summary,
    )
    messages: list[dict] = [{"role": "system", "content": system_prompt}]
    if history:
        messages.extend(history)
    messages.append({"role": "user", "content": message})
    return messages


def _accumulate_stream_chunks(stream) -> tuple[list[str], dict[int, dict]]:
    """消费同步的 LLM 流式迭代器，累积文本增量与 tool_calls 分段。

    工具调用参数（arguments）可能被拆成多个 delta，按 index 拼接。
    返回 (文本增量列表, {index: {"id","name","arguments"}})。

    Args:
        stream: client.chat.completions.create(stream=True) 返回的迭代器。

    Returns:
        tuple[list[str], dict[int, dict]]: 文本片段列表与工具调用累积结构。
    """
    text_parts: list[str] = []
    tool_acc: dict[int, dict] = {}
    for chunk in stream:
        if not getattr(chunk, "choices", None):
            continue
        delta = chunk.choices[0].delta
        if delta is None:
            continue
        tool_deltas = getattr(delta, "tool_calls", None)
        if tool_deltas:
            for tc in tool_deltas:
                idx = tc.index if tc.index is not None else 0
                entry = tool_acc.setdefault(idx, {"id": "", "name": "", "arguments": ""})
                if getattr(tc, "id", None):
                    entry["id"] = tc.id
                fn = getattr(tc, "function", None)
                if fn is not None:
                    if getattr(fn, "name", None):
                        entry["name"] = fn.name
                    if getattr(fn, "arguments", None):
                        entry["arguments"] += fn.arguments
            continue
        content = getattr(delta, "content", None)
        if content:
            text_parts.append(content)
    return text_parts, tool_acc


async def _iter_chunks(stream):
    """异步逐块迭代同步的 LLM 流式迭代器（后台线程桥接）。

    OpenAI SDK 的流式迭代是同步阻塞的（等待网络 chunk），直接 in-loop
    迭代会卡死 FastAPI 事件循环。通过线程 + 队列把 chunk 逐块送进
    事件循环，让生成器可以边收边 yield（真流式的关键）。

    Args:
        stream: 同步的流式 chunk 迭代器。

    Yields:
        chunk: 原始流式 chunk（带 choices[0].delta）。
    """
    loop = asyncio.get_running_loop()
    q: queue.Queue = queue.Queue()

    def _fill() -> None:
        try:
            for chunk in stream:
                q.put(chunk)
        finally:
            q.put(None)

    task = loop.run_in_executor(None, _fill)
    try:
        while True:
            chunk = await loop.run_in_executor(None, q.get)
            if chunk is None:
                return
            yield chunk
    finally:
        await task


def _tool_calls_to_messages(acc: dict[int, dict]) -> tuple[list[dict], list]:
    """把累积的工具调用结构转为 assistant 消息 + 可执行对象列表。

    Args:
        acc: {index: {"id","name","arguments"}}，来自流式累积。

    Returns:
        tuple[list[dict], list]: (assistant 消息列表, 工具执行对象列表)。
    """
    ordered = [acc[i] for i in sorted(acc)]
    assistant_msg = {
        "role": "assistant",
        "content": None,
        "tool_calls": [
            {
                "id": tc["id"] or f"call_{i}",
                "type": "function",
                "function": {"name": tc["name"], "arguments": tc["arguments"] or "{}"},
            }
            for i, tc in enumerate(ordered)
        ],
    }
    calls = [
        SimpleNamespace(
            id=tc["id"] or f"call_{i}",
            function=SimpleNamespace(
                name=tc["name"], arguments=tc["arguments"] or "{}"
            ),
        )
        for i, tc in enumerate(ordered)
    ]
    return [assistant_msg], calls


async def chat_stream(
    message: str,
    history: list[dict] | None = None,
    interests: list[str] | None = None,
    reading_history: list[str] | None = None,
    conversation_summary: str | None = None,
):
    """执行一轮 Agent 对话并流式产出事件（SSE 真流式）。

    与 chat() 的差异：每轮 LLM 调用使用 stream=True——
      - 工具轮：LLM 输出 tool_calls 增量，执行工具，发 tool start/done 事件；
      - 答案轮：LLM 文本增量边收边发 token 事件。
    独立工具仍并发执行。

    Args:
        message: 用户输入文本。
        history: 对话历史。
        interests: 用户关注方向。
        reading_history: 阅读历史标题。
        conversation_summary: 跨会话摘要。

    Yields:
        dict: 事件（tool / token / done / error）。
    """
    client = _get_client()
    if client is None:
        yield {"type": "error", "message": "LLM 未配置，请在 .env 中设置 DEEPSEEK_API_KEY。"}
        return

    messages = _build_messages(
        message, history, interests, reading_history, conversation_summary
    )

    try:
        for turn in range(MAX_TOOL_CALLS):
            stream = await asyncio.to_thread(
                client.chat.completions.create,
                model=_model_id(),
                messages=messages,
                tools=tools.TOOLS,
                stream=True,
            )
            # 答案轮边收边发 token；工具轮累积 tool_calls（不向客户端透出 JSON）
            text_parts: list[str] = []
            tool_acc: dict[int, dict] = {}
            async for chunk in _iter_chunks(stream):
                if not getattr(chunk, "choices", None):
                    continue
                delta = chunk.choices[0].delta
                if delta is None:
                    continue
                tool_deltas = getattr(delta, "tool_calls", None)
                if tool_deltas:
                    for tc in tool_deltas:
                        idx = tc.index if tc.index is not None else 0
                        entry = tool_acc.setdefault(
                            idx, {"id": "", "name": "", "arguments": ""}
                        )
                        if getattr(tc, "id", None):
                            entry["id"] = tc.id
                        fn = getattr(tc, "function", None)
                        if fn is not None:
                            if getattr(fn, "name", None):
                                entry["name"] = fn.name
                            if getattr(fn, "arguments", None):
                                entry["arguments"] += fn.arguments
                    continue
                content = getattr(delta, "content", None)
                if content:
                    text_parts.append(content)
                    yield {"type": "token", "text": content}

            if not tool_acc:
                # 答案轮：完整文本 = 已流式转发的增量之和（保持一致）
                answer = "".join(text_parts) or "暂无内容。"
                logger.info(
                    "Agent 流式完成: %d 轮工具循环, 回复 %d 字", turn, len(answer)
                )
                yield {"type": "done", "answer": answer}
                return

            assistant_msgs, calls = _tool_calls_to_messages(tool_acc)
            names = [c.function.name for c in calls]
            logger.info("Agent 第 %d 轮调用工具: %s", turn + 1, ", ".join(names))

            # 真实工具事件：开始 → 并发执行 → 全部完成
            for name in names:
                yield {"type": "tool", "name": name, "status": "start"}

            messages.extend(assistant_msgs)
            results = await asyncio.gather(*[_execute_tool(c) for c in calls])
            for c, result in zip(calls, results):
                messages.append({
                    "role": "tool",
                    "tool_call_id": c.id,
                    "content": result,
                })

            for name in names:
                yield {"type": "tool", "name": name, "status": "done"}

        logger.warning("Agent 工具循环超过 %d 轮上限", MAX_TOOL_CALLS)
        yield {"type": "error", "message": "LLM 调用工具次数过多，请简化问题后重试。"}
    except Exception as exc:  # noqa: BLE001 — 流中异常以 error 事件告知前端
        logger.exception("Agent 流式对话失败")
        yield {"type": "error", "message": f"Agent 调用失败: {exc}"}
