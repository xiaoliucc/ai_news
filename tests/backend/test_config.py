"""
测试全局配置 — 内网穿透公网地址归一化与 CORS 放行名单组合。

纯函数测试（_normalize_url / cors_origins），不触碰真实 .env。
"""

from backend.config import _normalize_url, cors_origins


# ── _normalize_url ─────────────────────────────────────────────────────────

def test_normalize_url_basic():
    """去首尾空白与尾部斜杠。"""
    assert _normalize_url("  https://xxxxx.cpolar.top/  ") == "https://xxxxx.cpolar.top"


def test_normalize_url_keeps_port_and_scheme():
    """带端口 / http 前缀的 cpolar 地址原样保留。"""
    assert _normalize_url("http://xxx.cpolar.top:8080") == "http://xxx.cpolar.top:8080"


def test_normalize_url_empty_returns_none():
    """空串 / 纯空白返回 None（= 直连模式）。"""
    assert _normalize_url("") is None
    assert _normalize_url("   ") is None
    assert _normalize_url("/") is None


# ── cors_origins ──────────────────────────────────────────────────────────

def test_cors_origins_default_only_local():
    """未填前端隧道地址时仅本地开发端口。"""
    assert cors_origins(None) == [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]


def test_cors_origins_appends_page_url():
    """填入前端隧道地址（页面 Origin）后追加到放行名单。"""
    origins = cors_origins("https://7b9a52aa.r20.cpolar.top")
    assert origins[-1] == "https://7b9a52aa.r20.cpolar.top"
    assert len(origins) == 3
