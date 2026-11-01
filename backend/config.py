"""
全局配置 — 从 .env 读取运行参数，提供默认值。

配置项：
    SQLITE_PATH       — SQLite 数据库文件路径，默认 backend/data.db
    COLLECTION_LIMIT  — 调度器每源采集条数，默认 20
    COLLECTION_HOURS  — 调度间隔（小时），默认 6
"""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

# 数据库：默认放在 backend/db/data.db
SQLITE_PATH = Path(
    os.getenv("SQLITE_PATH", str(Path(__file__).resolve().parent / "db/data.db"))
)
CHROMA_DIR = Path(
    os.getenv("CHROMA_DIR", str(Path(__file__).resolve().parent / "db/chroma"))
)
# 采集参数
COLLECTION_LIMIT = int(os.getenv("COLLECTION_LIMIT", "20"))
COLLECTION_HOURS = int(os.getenv("COLLECTION_HOURS", "6"))

# RSS 聚合源：逗号分隔的 feed URL 列表（如 RSSHub 的机器之心/知乎热榜路由）
RSS_FEEDS = [
    f.strip()
    for f in os.getenv("RSS_FEEDS", "").split(",")
    if f.strip()
]

# 网络代理：墙外源（GitHub / HuggingFace）需要时填写本机代理地址；
# 留空 = 直连。多设备各自维护 .env，代理地址按设备填写（Clash 默认 7890）。
# 优先级：系统环境变量 HTTPS_PROXY（若已存在）> .env > 直连。
# 改动需重启后端生效（启动日志会打印当前网络模式）。
PROXY_URL = os.getenv("HTTPS_PROXY", "").strip() or None

# Tavily 联网搜索 API key（Agent web_search 工具用，查询采集库外的实时信息）
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "").strip() or None


def _normalize_url(value: str) -> str | None:
    """归一化公网地址：去首尾空白与尾部斜杠，空串返回 None。

    Args:
        value: .env 中公网地址的原始值。

    Returns:
        str | None: 清洗后的地址；空值返回 None。
    """
    v = value.strip().rstrip("/")
    return v or None


def cors_origins(page_url: str | None) -> list[str]:
    """CORS 放行名单：本地开发端口 + 可选内网穿透页面地址。

    Args:
        page_url: 前端页面隧道公网地址（无则 None）。

    Returns:
        list[str]: 放行 origin 列表。
    """
    origins = ["http://localhost:5173", "http://127.0.0.1:5173"]
    if page_url:
        origins.append(page_url)
    return origins


# 内网穿透（cpolar 双隧道——一条隧道只能转发一个本地端口，前后端各一条）：
#   PUBLIC_BACKEND_URL — 后端 :8000 隧道：前端页面访问 API 的地址（vite.config 注入前端）
#   PUBLIC_FRONTEND_URL — 前端 :5173 隧道：后端 CORS 放行该 Origin（浏览器请求来源）
# 留空 = 直连/局域网（前后端互不依赖公网）。修改后需重启后端生效，
# 启动日志会打印隧道模式。免费版隧道重启后子域可能变化，需同步更新。
PUBLIC_BACKEND_URL = _normalize_url(os.getenv("PUBLIC_BACKEND_URL", ""))
PUBLIC_FRONTEND_URL = _normalize_url(os.getenv("PUBLIC_FRONTEND_URL", ""))
CORS_ORIGINS = cors_origins(PUBLIC_FRONTEND_URL)

def _env_bool(name: str, default: bool = True) -> bool:
    """读取布尔型环境变量（`0/false/no/off` 视为关，其余含空串视为开）。

    Args:
        name: 环境变量名。
        default: 变量未设置时的默认值。

    Returns:
        bool: 解析结果。
    """
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() not in {"0", "false", "no", "off"}


# 速率限制（2026-11-01）：只保护「会花钱」的两个接口——POST /api/collect（每轮
# 抓 6 个源 + LLM 判定）与 POST /api/agent/chat（直接烧 LLM/Tavily 额度）。
# 内存滑动窗口，单进程计数；多 worker 部署时额度按 worker 数放大。
#   RATE_LIMIT_ENABLED — 总开关，默认开；设 0 完全关闭
#   RATE_LIMIT_WINDOW  — 窗口长度（秒），默认 600（10 分钟）
#   RATE_LIMIT_CHAT    — 每窗口每客户端 chat 次数，默认 20；0 = 不限制
#   RATE_LIMIT_COLLECT — 每窗口每客户端采集次数，默认 3；0 = 不限制
RATE_LIMIT_ENABLED = _env_bool("RATE_LIMIT_ENABLED", True)
RATE_LIMIT_WINDOW = int(os.getenv("RATE_LIMIT_WINDOW", "600"))
RATE_LIMIT_CHAT = int(os.getenv("RATE_LIMIT_CHAT", "20"))
RATE_LIMIT_COLLECT = int(os.getenv("RATE_LIMIT_COLLECT", "3"))

# 可选 API 门禁 Token（2026-09-06）：
#   留空 = 不启用（本机/局域网模式，前端不带任何头，零配置零开销）；
#   填值 = 公网暴露（cpolar / 云服务器）时所有 /api/* 请求必须携带
#   X-API-Token 请求头，防止互联网扫描器刷采集 / 烧部署者的 LLM 额度。
#   个人自部署各填各 token——key 与额度按部署者隔离，不共享。
#   前端构建时 vite.config 读同名变量注入（见 vite.config.ts 注释）。
API_TOKEN = os.getenv("API_TOKEN", "").strip() or None

# 文档暴露与日志隐私（2026-11-01）：
#   ENABLE_DOCS      — 是否暴露 /docs、/redoc、/openapi.json，**默认关**。公网部署时
#                      接口清单等于把参数结构送给扫描器；本地调试临时设 1 打开。
#   LOG_FULL_MESSAGE — 是否在日志里记录用户提问原文，**默认关**。关闭时只记长度
#                      与前 20 字符，避免 docker logs 里留下用户原话。
ENABLE_DOCS = _env_bool("ENABLE_DOCS", False)
LOG_FULL_MESSAGE = _env_bool("LOG_FULL_MESSAGE", False)
