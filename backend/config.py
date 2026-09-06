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
