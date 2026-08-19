
import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, field_validator

from backend.agent.core import chat
from backend.database import get_article, get_profile

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["agent"])


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


@router.post("/agent/chat", response_model=ChatResponse)
async def agent_chat(req: ChatRequest) -> ChatResponse:
    """Agent 对话接口。

    ChromaDB 索引由 scheduler 采集时同步维护，Agent 直接检索即可。
    无需每次请求重建索引。

    Args:
        req: ChatRequest（message 必填，history / interests 可选）。

    Returns:
        ChatResponse: 包含 LLM 回复文本。

    Raises:
        HTTPException 400: message 为空字符串。
        HTTPException 500: Agent 调用异常。
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

    try:
        answer = await chat(
            message=req.message,
            history=req.history,
            interests=interests,
            reading_history=reading_history,
        )
    except Exception as exc:
        logger.exception("Agent 对话失败")
        raise HTTPException(status_code=500, detail=f"Agent 调用失败: {exc}") from exc

    return ChatResponse(answer=answer)