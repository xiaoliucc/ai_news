"""
FastAPI app — API 入口和服务生命周期管理。

启动: uvicorn backend.main:app --reload
"""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from . import scheduler
from .config import (
    API_TOKEN,
    CORS_ORIGINS,
    ENABLE_DOCS,
    PUBLIC_BACKEND_URL,
    PUBLIC_FRONTEND_URL,
    RATE_LIMIT_CHAT,
    RATE_LIMIT_COLLECT,
    RATE_LIMIT_ENABLED,
    RATE_LIMIT_WINDOW,
)
from .ratelimit import SlidingWindowLimiter, client_key
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

# 文档暴露（2026-11-01，H-6-4）：默认关闭 /docs、/redoc、/openapi.json——公网部署时
# 接口清单等于把参数结构送给扫描器。本地调试时 .env 设 ENABLE_DOCS=1 打开。
app = FastAPI(
    lifespan=lifespan,
    docs_url="/docs" if ENABLE_DOCS else None,
    redoc_url="/redoc" if ENABLE_DOCS else None,
    openapi_url="/openapi.json" if ENABLE_DOCS else None,
)

# ===================== 速率限制（2026-11-01） =====================
# 只保护「会花钱」的两个接口：POST /api/collect（每轮抓 6 个源 + LLM 判定）、
# POST /api/agent/chat（直接烧 LLM/Tavily 额度）。其余 /api 是 SQLite 只读查询，
# 单用户自部署下限制它们只会误伤自己。额度与窗口在 .env（见 config.py）。
# `RATE_LIMITS` 保持模块级变量，测试可 monkeypatch 换路径/额度。
RATE_LIMITS: dict[str, tuple[int, int]] = {
    "/api/agent/chat": (RATE_LIMIT_CHAT, RATE_LIMIT_WINDOW),
    "/api/collect": (RATE_LIMIT_COLLECT, RATE_LIMIT_WINDOW),
}
rate_limiter = SlidingWindowLimiter()


@app.middleware("http")
async def rate_limit_requests(request, call_next):
    """超出配额的请求返回 429 + Retry-After（CORS 预检不计次）。"""
    if RATE_LIMIT_ENABLED and request.method != "OPTIONS":
        spec = RATE_LIMITS.get(request.url.path)
        if spec:
            limit, window = spec
            client = client_key(
                request.headers.get("X-Forwarded-For"), request.client.host if request.client else None
            )
            allowed, retry_after = rate_limiter.hit(client, request.url.path, limit, window)
            if not allowed:
                logger.warning("限流命中: %s %s client=%s", request.method, request.url.path, client)
                return JSONResponse(
                    status_code=429,
                    content={
                        "detail": (
                            f"请求过于频繁：{request.url.path} 每 {window} 秒最多 {limit} 次，"
                            f"请 {retry_after} 秒后重试"
                        )
                    },
                    headers={"Retry-After": str(retry_after)},
                )
    return await call_next(request)


# ===================== 可选 API Token 门禁 =====================
# .env 配了 API_TOKEN 时，所有 /api/* 请求必须携带 X-API-Token 头（防公网
# 扫描器刷采集/烧 LLM 额度）。运行时读 config 便于测试 monkeypatch；
# OPTIONS（CORS preflight）放行，非 /api 路径（/ /health 静态页）不拦。
# 个人自部署各实例填自己的 token——key/额度按部署者隔离，不共享。
# 注册在限流之后 → 处于限流器外层：**没带对 token 的请求不会消耗配额**。
@app.middleware("http")
async def require_api_token(request, call_next):
    token = API_TOKEN
    if (
        token
        and request.url.path.startswith("/api/")
        and request.method != "OPTIONS"
        and request.headers.get("X-API-Token") != token
    ):
        return JSONResponse(
            status_code=401,
            content={"detail": "缺少或错误的 X-API-Token（请检查 .env 的 API_TOKEN）"},
        )
    return await call_next(request)


# ===================== CORS 跨域配置核心 =====================
# **必须最后 add_middleware**：Starlette 的 add_middleware 是往栈顶插入，
# 越后添加越靠外层。CORS 放最外层才能给 401/429 这类提前返回的响应也加上
# Access-Control-* 头（否则跨域开发时浏览器只看到网络错误、拿不到状态码）。
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# ===================== 安全响应头（2026-11-01，H-6-4） =====================
# 加在 CORS 之后 ⇒ 位于最外层，401/429/静态文件都能带上这几个头。
# 只放零风险的三项：nosniff（禁 MIME 嗅探）、DENY（禁被 iframe 嵌套）、
# no-referrer（不把本页地址带给第三方）。**故意不加 CSP**：Vite 产物与
# ECharts 依赖内联样式，CSP 需按实际部署域逐条配，配错就是白屏；
# XSS 面已在 H-6-1 用 DOMPurify 白名单堵住，CSP 属于纵深防御的第二层。
SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Permissions-Policy": "geolocation=(), microphone=(), camera=()",
}


@app.middleware("http")
async def add_security_headers(request, call_next):
    """给所有响应补安全头（含中间件提前返回的 401/429）。"""
    response = await call_next(request)
    for name, value in SECURITY_HEADERS.items():
        response.headers.setdefault(name, value)
    return response


# ================================================================
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