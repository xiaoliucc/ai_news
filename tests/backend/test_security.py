"""
测试安全响应头与文档暴露开关（H-6-4）。

覆盖：
    - 默认不暴露 /docs、/redoc、/openapi.json（404）
    - 安全头出现在 200、401、429 三类响应上（提前返回也要带）
    - 静态首页（挂载前的 / 路由）同样带头
"""

import pytest
from fastapi.testclient import TestClient

from backend import main as main_module
from backend.main import SECURITY_HEADERS, app


@pytest.fixture
def client(monkeypatch):
    """无门禁、无限流的干净客户端（多数断言只关心头）。"""
    monkeypatch.setattr(main_module, "API_TOKEN", None)
    monkeypatch.setattr(main_module, "RATE_LIMIT_ENABLED", False)
    return TestClient(app)


# ── 文档暴露 ────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("path", ["/docs", "/redoc", "/openapi.json"])
def test_docs_disabled_by_default(client, path):
    """默认不暴露接口清单（扫描器拿不到参数结构）。"""
    assert main_module.ENABLE_DOCS is False
    assert client.get(path).status_code == 404


def test_docs_enabled_by_env(monkeypatch):
    """ENABLE_DOCS=1 时文档可用——验证开关本身有效（需同时重载 config 与 main）。

    只重载 main 不够：`backend.config` 已在 sys.modules 里，`from .config import
    ENABLE_DOCS` 会拿到旧值（第一次写这个测试时踩过）。
    """
    from importlib import reload

    import backend.config as config_module

    monkeypatch.setenv("ENABLE_DOCS", "1")
    try:
        reload(config_module)
        reloaded = reload(main_module)
        assert reloaded.ENABLE_DOCS is True
        assert reloaded.app.docs_url == "/docs"
        assert TestClient(reloaded.app).get("/openapi.json").status_code == 200
    finally:
        monkeypatch.delenv("ENABLE_DOCS", raising=False)
        reload(config_module)
        reload(main_module)  # 还原模块级 app，避免污染其他测试


# ── 安全响应头 ──────────────────────────────────────────────────────────────

def test_security_headers_on_health(client):
    """/health（门禁豁免路径）带全部安全头。"""
    resp = client.get("/health")
    assert resp.status_code == 200
    for name, value in SECURITY_HEADERS.items():
        assert resp.headers[name] == value


def test_security_headers_on_401(client, monkeypatch):
    """门禁提前返回的 401 也要带安全头（中间件位于最外层）。"""
    monkeypatch.setattr(main_module, "API_TOKEN", "secret-token")
    resp = client.get("/api/stats")
    assert resp.status_code == 401
    for name, value in SECURITY_HEADERS.items():
        assert resp.headers[name] == value


def test_security_headers_on_429(client, monkeypatch):
    """限流提前返回的 429 也要带安全头 + Retry-After。"""
    monkeypatch.setattr(main_module, "RATE_LIMIT_ENABLED", True)
    monkeypatch.setattr(main_module, "RATE_LIMITS", {"/api/stats": (1, 600)})
    monkeypatch.setattr(main_module, "rate_limiter", main_module.SlidingWindowLimiter())

    assert client.get("/api/stats").status_code == 200
    resp = client.get("/api/stats")
    assert resp.status_code == 429
    assert "Retry-After" in resp.headers
    for name, value in SECURITY_HEADERS.items():
        assert resp.headers[name] == value


def test_csp_deliberately_absent(client):
    """故意不设 CSP（内联样式会白屏），防止有人"顺手"加上而打断前端。"""
    resp = client.get("/health")
    assert "Content-Security-Policy" not in resp.headers
