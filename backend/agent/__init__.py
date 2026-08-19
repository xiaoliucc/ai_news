"""
AI Agent 核心 — LLM + tool-use 模式（非 LangChain）。

职责：
    core.py     — Agent 主循环：接收消息 → 判断是否需要工具 → 调用工具 → 生成回复
    tools.py    — Agent 工具集（search_articles / get_article_detail / summarize_articles / analyze_trend / trigger_collection）
    prompts.py  — System prompt 定义

依赖：
    openai SDK（OpenAI 兼容端点，DeepSeek）
    src/pipeline/llm.py — LLM 调用封装
"""
