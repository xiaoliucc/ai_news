# syntax=docker/dockerfile:1
# ============================================================
# AI Research Intelligence Platform — 单服务全栈镜像
#   stage 1: Node 构建前端 dist
#   stage 2: Python + uv 运行 FastAPI 后端并托管 dist
# ============================================================

# ---------- stage 1: 前端构建 ----------
FROM node:20-alpine AS frontend
WORKDIR /build/frontend
# 先拷锁文件单独 npm ci（层缓存：依赖不变则复用）
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ---------- stage 2: 后端运行时 ----------
FROM python:3.13-slim
ENV UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1
WORKDIR /app

# uv 安装（后续 uv sync 读 pyproject 的 aliyun index，国内拉包稳定）
RUN pip install --no-cache-dir uv

# 依赖层（uv.lock 不变则缓存复用；--no-install-project 稍后拷源码再装）
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# 源码（排除项见 .dockerignore）
COPY . .
COPY --from=frontend /build/frontend/dist frontend/dist

# 嵌入模型离线加载：镜像不含模型，运行时挂载宿主 HF 缓存（见 docker-compose.yml）
ENV HF_HUB_OFFLINE=1
EXPOSE 8000

CMD ["uv", "run", "--no-sync", "uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
