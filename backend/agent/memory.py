"""
对话摘要记忆（P2）— 跨会话压缩对话结论。

机制：滚动摘要窗口。对话轮次超过阈值时，把「旧摘要 + 待归档轮次」
增量合并成一条新摘要（LLM），存 user_profile.conversation_summary；
请求只携带最近 N 轮，避免全量历史无限膨胀。

摘要生成失败返回 None，调用方保留旧摘要不更新（优雅降级）。
"""

import json
import logging

from src.pipeline.llm import _chat_json, _strip_code_fence

logger = logging.getLogger(__name__)

# 摘要上限：注入 system prompt 的正文长度约束
MAX_SUMMARY_CHARS = 300

_SUMMARY_SYSTEM = (
    "你是对话记忆管理员。把已有的对话摘要与新增对话轮次合并成一条新的摘要，"
    f"总长不超过 {MAX_SUMMARY_CHARS} 字。保留：用户偏好与兴趣、已给出的结论与推荐、"
    "待办事项与用户要求的后续任务；丢弃寒暄与重复内容。只输出 JSON。"
)

_EXAMPLE = '\n\n{"summary": "合并后的摘要文本"}'


def summarize_conversation(
    old_summary: str | None,
    rounds: list[dict],
    *,
    max_tokens: int = 512,
) -> str | None:
    """增量合并对话摘要。

    Args:
        old_summary: 已有的跨会话摘要；None 或空串表示首次归档。
        rounds: 待归档的对话轮次列表，格式
            [{"role": "user"/"assistant", "content": str}, ...]。
        max_tokens: LLM 输出预算（推理模型需留足 reasoning 空间）。

    Returns:
        str | None: 合并后的新摘要；LLM 不可用、调用失败或解析失败时
            返回 None（调用方应保留旧摘要不更新）。
    """
    if not rounds:
        return old_summary or None

    user_payload = json.dumps(
        {
            "old_summary": old_summary or "",
            "new_rounds": rounds,
        },
        ensure_ascii=False,
    )
    content = _chat_json(_SUMMARY_SYSTEM, user_payload + _EXAMPLE, max_tokens=max_tokens)
    if content is None:
        logger.warning("对话摘要合并失败：LLM 调用不可用")
        return None
    try:
        data = json.loads(_strip_code_fence(content))
        summary = str(data["summary"]).strip()
        if not summary:
            return None
        return summary[: MAX_SUMMARY_CHARS * 2]  # 保险截断，防极端超长
    except Exception:  # noqa: BLE001 — 解析失败视为未归档
        logger.warning("对话摘要合并输出无法解析: %r", content[:200])
        return None
