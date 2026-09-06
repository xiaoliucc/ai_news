"""
FastAPI app — API 入口和服务生命周期管理。

启动: uvicorn backend.main:app --reload
"""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from . import scheduler
from .config import CORS_ORIGINS, PUBLIC_BACKEND_URL, PUBLIC_FRONTEND_URL
from .routers import agent, articles, collect, sources, stats

logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting up...")
    if PUBLIC_BACKEND_URL or PUBLIC_FRONTEND_URL:
        logger.info(
            "内网穿透: API=%s / 页面=%s",
            PUBLIC_BACKEND_URL or "未配置（本地直连）",
            PUBLIC_FRONTEND_URL or "未配置（本地直连）",
        )
    logger.info("CORS 放行: %s", ", ".join(CORS_ORIGINS))
    try:
        scheduler.start()
    except Exception as e:
        logger.error("定时调度器启动失败，服务无法启动", exc_info=True)
        raise RuntimeError("Scheduler startup failed") from e
    logger.info("定时调度器 scheduler 启动成功")

    yield

    logger.info("Shutting down...")
    try:
        scheduler.shutdown()
    except Exception as e:
        logger.error("关闭 scheduler 异常", exc_info=True)
    logger.info("定时调度器正常关闭完成")

app = FastAPI(lifespan=lifespan)

# ===================== CORS 跨域配置核心 =====================
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# ===================== 路由挂载 =====================
app.include_router(articles.router)
app.include_router(sources.router)
app.include_router(stats.router)
app.include_router(agent.router)
app.include_router(collect.router)
# ==========================================================

@app.get("/")
async def root():
    """根路径，返回欢迎信息。"""
    return {"message": "AI Research Intelligence Platform API", "version": "0.1.0"}


@app.get("/health")
async def health_check():
    """健康检查接口，返回服务状态。"""
    return {"status": "ok"}


# ===================== 前端静态托管（部署模式） =====================
# 存在 frontend/dist（Docker 构建产物或本地 npm run build）时托管为根路径，
# 单端口全栈。注意：Mount "/" 是 catch-all，必须在 /api 路由与 /、/health
# 等显式路由之后注册（Starlette 按添加顺序匹配），否则静态层会拦截 API 路径。
# 开发模式（uvicorn --reload + vite dev）无 dist 则不挂载，保持纯 API。
_dist = Path(__file__).resolve().parent.parent / "frontend" / "dist"
if _dist.is_dir():
    app.mount("/", StaticFiles(directory=_dist, html=True), name="frontend")
    logger.info("已托管前端静态资源: %s", _dist)