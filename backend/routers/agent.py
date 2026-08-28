
import asyncio
import json
import logging

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, field_validator

from backend.agent.core import chat_stream
from backend.agent.memory import summarize_conversation
from backend.database import get_article, get_profile, set_profile

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["agent"])

# P2 对话归档：history 超过该条数时，最早部分压缩进摘要，请求只带最近 KEEP_MESSAGES 条
# （ChatRequest.history 上限 20 条，前端恒传最近 20 条；阈值 12 → 每次归档 8 条滚动生效）
ARCHIVE_THRESHOLD = 12
KEEP_MESSAGES = 12


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000, description="用户消息")
    history: list[dict] | None = Field(
        default=None, max_length=20, description="对话历史，最多 20 轮"
    )
    interests: list[str] | None = Field(default=None, description="用户关注方向")

    @field_validator("history")
    @classmethod
    def _check_history_size(cls, v: list[dict] | None) -> list[dict] | None:
        """限制历史内容总量，防止 token 溢出。"""
        if v is None:
            return v
        total = sum(len(str(item.get("content", ""))) for item in v if isinstance(item, dict))
        if total > 20000:
            raise ValueError("history 内容过长（总计超过 20000 字符）")
        return v


class ChatResponse(BaseModel):
    answer: str


def _resolve_titles(article_ids: list[str]) -> list[str] | None:
    """把阅读历史的文章 ID 列表解析为标题列表（prompt 注入用）。

    Args:
        article_ids: 文章 ID 列表（来自 user_profile.reading_history）。

    Returns:
        list[str] | None: 标题列表；空列表或全部失效时返回 None。
    """
    titles = []
    for aid in article_ids:
        a = get_article(aid)
        if a is not None:
            titles.append(a["title"])
    return titles or None


@router.post("/agent/chat")
async def agent_chat(req: ChatRequest) -> StreamingResponse:
    """Agent 对话接口（SSE 真流式）。

    ChromaDB 索引由 scheduler 采集时同步维护，Agent 直接检索即可。
    无需每次请求重建索引。响应为 text/event-stream，事件协议：
      data: {"type":"tool","name":"...","status":"start"|"done"}  — 真实工具执行
      data: {"type":"token","text":"..."}                          — LLM 流式增量
      data: {"type":"done","answer":"..."}                         — 完成
      data: {"type":"error","message":"..."}                       — 错误

    Args:
        req: ChatRequest（message 必填，history / interests 可选）。

    Returns:
        StreamingResponse: SSE 事件流。

    Raises:
        HTTPException 400: message 为空字符串。
    """
    if not req.message.strip():
        raise HTTPException(status_code=400, detail="message 不能为空")

    # 前端没传 interests 时，从 user_profile 读用户偏好；
    # reading_history 恒从 profile 读取（ID → 标题），避免重复推荐
    interests = req.interests
    profile = get_profile()
    if interests is None:
        interests = profile.get("interests") or []
    reading_history = _resolve_titles(profile.get("reading_history") or [])

    logger.info(
        "Agent 对话(流式): message=%r history=%d 条 interests=%s reading_history=%d 条",
        req.message,
        len(req.history) if req.history else 0,
        interests,
        len(reading_history or []),
    )

    # P2 对话归档：history 超过阈值时，最早部分增量合并进摘要存库，
    # 请求只带最近 KEEP_MESSAGES 条（全量历史不再无限膨胀）
    summary = profile.get("conversation_summary") or None
    history_for_chat = req.history
    if req.history and len(req.history) > ARCHIVE_THRESHOLD:
        archive_msgs = req.history[:-KEEP_MESSAGES]
        history_for_chat = req.history[-KEEP_MESSAGES:]
        new_summary = await asyncio.to_thread(
            summarize_conversation, summary, archive_msgs
        )
        if new_summary:
            set_profile(conversation_summary=new_summary)
            summary = new_summary
            logger.info(
                "对话归档: 压缩 %d 条历史消息进摘要（%d 字）",
                len(archive_msgs),
                len(new_summary),
            )
        else:
            logger.warning("对话归档: 摘要生成失败，保留旧摘要仅截断历史")

    async def event_gen():
        """把 chat_stream 的事件 dict 序列化为 SSE data 行。"""
        try:
            async for ev in chat_stream(
                message=req.message,
                history=history_for_chat,
                interests=interests,
                reading_history=reading_history,
                conversation_summary=summary,
            ):
                payload = json.dumps(ev, ensure_ascii=False)
                logger.info("SSE 事件: %s", payload[:120])
                yield f"data: {payload}\n\n"
        except Exception as exc:  # noqa: BLE001 — 流中异常以 error 事件兜底
            logger.exception("Agent 流式对话路由异常")
            payload = json.dumps(
                {"type": "error", "message": f"Agent 调用失败: {exc}"},
                ensure_ascii=False,
            )
            yield f"data: {payload}\n\n"

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # 提示 nginx 等反代不要缓冲 SSE
        },
    )