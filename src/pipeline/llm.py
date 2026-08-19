"""
LLM 语义模块 — 用 LLM 做 AI 相关性判断与质量打分，替代 filters.py 关键词匹配。

对外接口：
    is_ai_related(article: Article) -> bool        # AI 相关性判断（LLM 优先，关键词回退）
    score_quality(article: Article) -> int | None  # 质量打分 0-100，供 ranking v2 使用

LLM 通过 OpenAI 兼容端点访问（OpenAI / DeepSeek / 本地 Ollama 等），
连接参数从 .env 读取：DEEPSEEK_API_KEY / LLM_MODEL_ID / LLM_BASE_URL / LLM_TIMEOUT。

未配置 key 或调用失败时优雅降级：判断回退关键词、打分返回 None，
不影响采集主流程。
"""

import json
import logging
import os
import time
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

from src.models import Article

logger = logging.getLogger(__name__)

# 加载项目根目录的 .env（src/pipeline/llm.py → parents[2] = 项目根）
load_dotenv(Path(__file__).resolve().parents[2] / ".env")


def _build_client() -> OpenAI | None:
    """按 .env 配置构建 OpenAI 兼容客户端。

    优先 DEEPSEEK_API_KEY，其次 OPENAI_API_KEY。缺 key 时返回 None。

    Returns:
        OpenAI | None: 配置好的客户端实例，或 key 缺失时返回 None。
    """
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        return None
    kwargs: dict = {
        "api_key": api_key,
        "base_url": os.getenv("LLM_BASE_URL", "https://api.deepseek.com"),
        "timeout": float(os.getenv("LLM_TIMEOUT", "60")),
    }
    if os.getenv("OPENAI_API_KEY"):
        # 只覆盖 api_key，保留 base_url/timeout
        kwargs["api_key"] = os.environ["OPENAI_API_KEY"]
    return OpenAI(**kwargs)


def _model_id() -> str:
    """返回 .env 配置的模型 ID，默认 deepseek-chat。

    Returns:
        str: 模型标识符。
    """
    return os.getenv("LLM_MODEL_ID", "deepseek-chat")


# 模块级惰性客户端：首次调用任一公开函数时构建一次，构建失败缓存 None
_client: OpenAI | None = None
_client_loaded = False


def _get_client() -> OpenAI | None:
    """返回全局惰性初始化的 LLM 兼容客户端。

    首次调用时从 .env 构建一次，构建成功后缓存复用。
    构建失败（缺 key）不缓存结果，下次调用会重新尝试。

    Returns:
        OpenAI | None: 客户端实例，或 key 缺失时返回 None。
    """
    global _client, _client_loaded
    if not _client_loaded:
        client = _build_client()
        if client is not None:
            _client = client
            _client_loaded = True
    return _client


def _chat_json(system: str, user: str, *, max_tokens: int = 256) -> str | None:
    """调用 LLM 并要求输出 JSON。

    使用 response_format={"type": "json_object"} 约束输出格式，
    temperature=0 保证确定性。

    Args:
        system: System prompt。
        user: 用户消息（应包含 JSON 输出示例）。
        max_tokens: 最大输出 token 数。

    Returns:
        str | None: LLM 返回的原始文本；客户端不可用、调用失败或超时时返回 None。
    """
    client = _get_client()
    if client is None:
        return None
    started = time.monotonic()
    try:
        resp = client.chat.completions.create(
            model=_model_id(),
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=0,
            response_format={"type": "json_object"},
            max_tokens=max_tokens,
        )
        content = resp.choices[0].message.content
        return content
    except Exception as exc:  # noqa: BLE001 — 网络/鉴权/超时均降级处理
        logger.warning("LLM 调用失败: %s (%.1fs)", exc, time.monotonic() - started)
        return None


def _strip_code_fence(text: str) -> str:
    """去掉 LLM 偶尔输出的 ```json ... ``` 标记围栏代码块。

    Args:
        text: 可能包裹在代码围栏中的原始文本。

    Returns:
        str: 剥离围栏后的纯 JSON 文本。
    """
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        lines = lines[1:] if lines and lines[0].startswith("```") else lines
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    return text


# ---- 相关性判断 ----

# 快速回退：LLM 不可用时复用 filters 的关键词表（避免循环导入）
from src.filters import is_ai_related as _keyword_related  # noqa: E402


def _llm_is_ai_related(title: str, summary: str | None) -> bool | None:
    """用 LLM 判断标题/摘要是否与 AI 相关。

    Args:
        title: 文章标题。
        summary: 文章摘要（可为 None）。

    Returns:
        bool | None: True/False 表示 AI 相关性；LLM 不可用或解析失败返回 None。
    """
    content = _chat_json(
        "你是一个 AI 领域内容审核员，判断给定内容是否与人工智能（AI/机器学习/大模型等）相关。只输出 JSON。",
        json.dumps(
            {"title": title, "summary": summary or ""},
            ensure_ascii=False,
        )
        + '\n\n{"relevant": true/false}',
        max_tokens=64,
    )
    if content is None:
        return None
    try:
        data = json.loads(_strip_code_fence(content))
        return bool(data["relevant"])
    except Exception:  # noqa: BLE001 — 解析失败视为无法判断
        logger.warning("LLM 判断输出无法解析: %r", content)
        return None


def is_ai_related(article: Article) -> bool:
    """判断文章是否与 AI 相关。

    策略：LLM 语义判断优先（理解上下文），LLM 不可用或失败时回退到
    filters.py 的关键词匹配。

    Args:
        article: 待判断的 Article 对象。

    Returns:
        bool: True 表示 AI 相关。
    """
    verdict = _llm_is_ai_related(article.title, article.summary)
    if verdict is not None:
        return verdict
    return _keyword_related(article)


# ---- 质量打分 ----

def score_quality(article: Article) -> int | None:
    """对文章质量打分 0-100。

    综合新颖性、影响力、技术深度、实用性评估。LLM 不可用或调用失败时
    返回 None，调用方（如 ranking v2）应回退到 v1 排序公式。

    Args:
        article: 待打分的 Article 对象。

    Returns:
        int | None: 质量分（0-100），LLM 不可用/失败/解析失败返回 None。
    """
    content = _chat_json(
        "你是一个 AI 内容质量评估专家。综合新颖性、影响力、技术深度、实用性给文章打分 0-100。只输出 JSON。",
        json.dumps(
            {"title": article.title, "summary": article.summary or ""},
            ensure_ascii=False,
        )
        + '\n\n{"quality_score": 0-100}',
        max_tokens=64,
    )
    if content is None:
        return None
    try:
        data = json.loads(_strip_code_fence(content))
        score = int(data["quality_score"])
        return max(0, min(100, score))
    except Exception:  # noqa: BLE001 — 解析失败视为未打分
        logger.warning("质量打分输出无法解析: %r", content)
        return None
