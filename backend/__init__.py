"""
AI 研究情报平台 — FastAPI 后端。

四层结构中的 API 层 + Agent 层：
    backend/main.py       — FastAPI app 入口（Phase 2）
    backend/config.py     — 配置管理（Phase 2）
    backend/database.py   — SQLite 连接 + 建表（Phase 2）
    backend/vector_store.py — ChromaDB 向量索引（Phase 2）
    backend/scheduler.py  — APScheduler 定时采集（Phase 2）
    backend/agent/        — AI Agent 核心（Phase 1）
    backend/routes/       — REST 路由（Phase 2）
"""
