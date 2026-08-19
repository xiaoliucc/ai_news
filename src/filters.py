"""AI 关键词过滤 — 基于标题关键词匹配判断 AI 相关性。

后续由 src/pipeline/llm.py 的 LLM 语义判断替代，本模块保留为降级回退。
"""

from src.models import Article

AI_KEYWORDS = [
    # 英文关键词 — 基础 AI 术语
    "AI",
    "artificial intelligence",
    "LLM",
    "large language model",
    "GPT",
    "ChatGPT",
    "OpenAI",
    "Claude",
    "Anthropic",
    "Gemini",
    "LLaMA",
    "Mistral",
    "DeepSeek",
    "Transformer",
    "Neural Network",
    "Machine Learning",
    "Deep Learning",
    "Stable Diffusion",
    "LoRA",
    "fine-tuning",
    "RAG",
    "Copilot",
    "Chatbot",
    "AGI",
    "agent",
    "prompt",
    "token",
    "embedding",
    # 英文关键词 — 学术论文常用术语
    "computer vision",
    "natural language",
    "vision-language",
    "multimodal",
    "reinforcement learning",
    "self-supervised",
    "world model",
    "diffusion",
    "attention mechanism",
    "graph neural",
    "generative",
    "representation learning",
    "pre-training",
    "few-shot",
    "zero-shot",
    "speech recognition",
    "object detection",
    "segmentation",
    "image generation",
    "policy optimization",
    "robotics",
    "humanoid",
    "autonomous",
    "embodied",
    "quantization",
    "inference",
    "language model",
    "foundation model",
    # 中文关键词
    "大模型",
    "大语言模型",
    "模型",
    "价格",
    "人工智能",
    "深度学习",
    "机器学习",
    "生成式",
    "智能体",
    "多模态",
    "具身智能",
    "强化学习",
    "计算机视觉",
    "自然语言",
]


def is_ai_related(article: Article) -> bool:
    """判断文章是否与 AI 相关（基于标题关键词匹配）。

    检查 article.title 是否包含 AI_KEYWORDS 中任一关键词，不区分大小写。
    llm.py 上线后本函数作为 LLM 不可用时的降级回退。

    Args:
        article: 待判断的 Article 对象。

    Returns:
        bool: 标题匹配到关键词返回 True，否则返回 False。
    """
    title_lower = article.title.lower()
    for keyword in AI_KEYWORDS:
        if keyword.lower() in title_lower:
            return True
    return False


def filter_ai_articles(articles: list[Article]) -> list[Article]:
    """从文章列表中筛选 AI 相关文章。

    Args:
        articles: 待过滤的文章列表。

    Returns:
        list[Article]: 标题匹配到 AI 关键词的文章子集。
    """
    return [a for a in articles if is_ai_related(a)]
