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
