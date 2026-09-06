"""
测试可选 API Token 门禁 middleware（backend/main.py require_api_token）。

覆盖：
    - API_TOKEN 未配置（None）→ /api 请求放行（本机模式零配置）
    - API_TOKEN 配置后：无头 / 错头 → 401；对头 → 放行
    - /health（非 /api 前缀）不受门禁影响
    - OPTIONS（CORS preflight）放行
"""

from fastapi.testclient import TestClient
import pytest

from backend.main import app

client = TestClient(app)

# /api/nonexistent 恒 404：用于区分"被 middleware 拦截(401)"与"放行到达路由(404)"
_MISS = "/api/__no_such_route__"


def test_token_disabled_allows_request(monkeypatch):
    """未配置 API_TOKEN（本机模式）：/api 请求不被拦截（404 = 到达路由）。"""
    monkeypatch.setattr("backend.main.API_TOKEN", None)
    assert client.get(_MISS).status_code == 404


def test_token_required_when_missing_header(monkeypatch):
    """配置 token 后，无 X-API-Token 头的 /api 请求被 401。"""
    monkeypatch.setattr("backend.main.API_TOKEN", "secret-123")
    assert client.get(_MISS).status_code == 401


def test_token_wrong_rejected(monkeypatch):
    """错误 token 同样 401。"""
    monkeypatch.setattr("backend.main.API_TOKEN", "secret-123")
    r = client.get(_MISS, headers={"X-API-Token": "wrong"})
    assert r.status_code == 401


def test_token_correct_allowed(monkeypatch):
    """正确 token 放行到路由（404 = 未被门禁拦截）。"""
    monkeypatch.setattr("backend.main.API_TOKEN", "secret-123")
    r = client.get(_MISS, headers={"X-API-Token": "secret-123"})
    assert r.status_code == 404


def test_health_not_blocked(monkeypatch):
    """/health 非 /api 前缀，配置 token 时也不拦截。"""
    monkeypatch.setattr("backend.main.API_TOKEN", "secret-123")
    assert client.get("/health").status_code == 200


def test_options_preflight_allowed(monkeypatch):
    """CORS preflight（OPTIONS）放行——浏览器预检不携带自定义头。"""
    monkeypatch.setattr("backend.main.API_TOKEN", "secret-123")
    r = client.options(
        "/api/agent/chat",
        headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "POST"},
    )
    assert r.status_code == 200
