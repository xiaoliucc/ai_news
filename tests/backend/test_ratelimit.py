"""测试进程内滑动窗口限流：限流器本身 + 中间件接线（backend/main.py）。

限流器用假时钟推进时间，不 sleep；中间件测试通过 monkeypatch 把额度压到 1，
并用真实的 TestClient，验证 429 / Retry-After / 多客户端隔离 / 与门禁的先后顺序。
"""

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.ratelimit import SlidingWindowLimiter, client_key

client = TestClient(app)


class FakeClock:
    """可推进的单调时钟替身。"""

    def __init__(self, start: float = 1000.0) -> None:
        self.now = start

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


@pytest.fixture
def limiter(clock: FakeClock) -> SlidingWindowLimiter:
    return SlidingWindowLimiter(clock=clock)


# ---------- 限流器本体 ----------


def test_allows_up_to_limit(limiter: SlidingWindowLimiter) -> None:
    """额度内全部放行，命中时不产生等待时间。"""
    for i in range(5):
        allowed, retry_after = limiter.hit("1.1.1.1", "/api/x", limit=5, window=60)
        assert allowed is True, f"第 {i + 1} 次不应被拦"
        assert retry_after == 0


def test_blocks_after_limit_and_reports_retry_after(limiter: SlidingWindowLimiter) -> None:
    """超出额度即拦截，Retry-After 应等于最早一次命中过期所需时间。"""
    for _ in range(2):
        assert limiter.hit("1.1.1.1", "/api/x", limit=2, window=60) == (True, 0)

    allowed, retry_after = limiter.hit("1.1.1.1", "/api/x", limit=2, window=60)
    assert allowed is False
    assert retry_after == 60  # 刚命中，需等满一个窗口


def test_window_slides(limiter: SlidingWindowLimiter, clock: FakeClock) -> None:
    """时间推进到窗口外后，旧命中被淘汰、重新放行。"""
    for _ in range(2):
        limiter.hit("1.1.1.1", "/api/x", limit=2, window=60)

    clock.advance(59)
    blocked, retry_after = limiter.hit("1.1.1.1", "/api/x", limit=2, window=60)
    assert blocked is False
    assert retry_after == 1  # 差 1 秒到期

    clock.advance(1)
    allowed, _ = limiter.hit("1.1.1.1", "/api/x", limit=2, window=60)
    assert allowed is True


def test_clients_and_buckets_are_isolated(limiter: SlidingWindowLimiter) -> None:
    """不同客户端、不同接口各算各的额度。"""
    assert limiter.hit("a", "/api/x", limit=1, window=60)[0] is True
    assert limiter.hit("a", "/api/x", limit=1, window=60)[0] is False

    assert limiter.hit("b", "/api/x", limit=1, window=60)[0] is True  # 另一个客户端
    assert limiter.hit("a", "/api/y", limit=1, window=60)[0] is True  # 另一个接口


@pytest.mark.parametrize("limit", [0, -1])
def test_non_positive_limit_means_unlimited(limiter: SlidingWindowLimiter, limit: int) -> None:
    """0 / 负数表示关闭限制（.env 里写 0 即放开）。"""
    for _ in range(50):
        assert limiter.hit("1.1.1.1", "/api/x", limit=limit, window=60) == (True, 0)


def test_reset_clears_all_counters(limiter: SlidingWindowLimiter) -> None:
    """reset 后计数清零（测试与实际运维都用得上）。"""
    limiter.hit("1.1.1.1", "/api/x", limit=1, window=60)
    assert limiter.hit("1.1.1.1", "/api/x", limit=1, window=60)[0] is False

    limiter.reset()
    assert limiter.tracked_keys() == 0
    assert limiter.hit("1.1.1.1", "/api/x", limit=1, window=60)[0] is True


# ---------- 客户端标识 ----------


def test_client_key_prefers_first_forwarded_hop() -> None:
    """隧道场景下 X-Forwarded-For 才是真实来源。"""
    assert client_key("203.0.113.7, 10.0.0.1", "127.0.0.1") == "203.0.113.7"
    assert client_key("", "127.0.0.1") == "127.0.0.1"
    assert client_key(None, "127.0.0.1") == "127.0.0.1"
    assert client_key(None, None) == "unknown"


# ---------- 中间件接线 ----------


@pytest.fixture
def fresh_limits(monkeypatch: pytest.MonkeyPatch) -> None:
    """把限流额度压到「/api/stats 每窗口 1 次」，清空计数，并关掉 Token 门禁。

    关掉门禁是因为本地 `.env` 可能已开启 `API_TOKEN`——不关的话所有请求先吃 401，
    测不到限流。（顺序本身另有一个用例专门验证。）
    """
    monkeypatch.setattr("backend.main.RATE_LIMITS", {"/api/stats": (1, 60)})
    monkeypatch.setattr("backend.main.RATE_LIMIT_ENABLED", True)
    monkeypatch.setattr("backend.main.rate_limiter", SlidingWindowLimiter())
    monkeypatch.setattr("backend.main.API_TOKEN", None)


def test_middleware_returns_429_with_retry_after(fresh_limits: None) -> None:
    """第二次请求被拦：429 + Retry-After + 可读中文说明。"""
    first = client.get("/api/stats")
    assert first.status_code == 200

    second = client.get("/api/stats")
    assert second.status_code == 429
    assert int(second.headers["Retry-After"]) >= 1
    assert "请求过于频繁" in second.json()["detail"]


def test_429_keeps_cors_headers(fresh_limits: None) -> None:
    """提前返回的 429 也必须带 CORS 头，否则跨域前端只能看到网络错误。"""
    client.get("/api/stats", headers={"Origin": "http://localhost:5173"})
    resp = client.get("/api/stats", headers={"Origin": "http://localhost:5173"})

    assert resp.status_code == 429
    assert resp.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_forwarded_for_gets_separate_quota(fresh_limits: None) -> None:
    """不同来源 IP 互不占用额度。"""
    assert client.get("/api/stats", headers={"X-Forwarded-For": "203.0.113.7"}).status_code == 200
    assert client.get("/api/stats", headers={"X-Forwarded-For": "198.51.100.9"}).status_code == 200
    assert client.get("/api/stats", headers={"X-Forwarded-For": "203.0.113.7"}).status_code == 429


def test_disabled_switch_bypasses_limit(fresh_limits: None, monkeypatch: pytest.MonkeyPatch) -> None:
    """总开关关掉后完全放行。"""
    monkeypatch.setattr("backend.main.RATE_LIMIT_ENABLED", False)
    for _ in range(5):
        assert client.get("/api/stats").status_code == 200


def test_unlimited_paths_untouched(monkeypatch: pytest.MonkeyPatch) -> None:
    """不在 RATE_LIMITS 名单里的接口不受影响。"""
    monkeypatch.setattr("backend.main.API_TOKEN", None)
    monkeypatch.setattr("backend.main.RATE_LIMITS", {})
    monkeypatch.setattr("backend.main.rate_limiter", SlidingWindowLimiter())
    for _ in range(5):
        assert client.get("/api/stats").status_code == 200


def test_token_gate_runs_before_rate_limit(fresh_limits: None, monkeypatch: pytest.MonkeyPatch) -> None:
    """门禁在限流外层：没带对 token 的请求只吃 401，不消耗配额。"""
    monkeypatch.setattr("backend.main.API_TOKEN", "secret-123")

    for _ in range(3):
        assert client.get("/api/stats").status_code == 401

    ok = client.get("/api/stats", headers={"X-API-Token": "secret-123"})
    assert ok.status_code == 200, "前面被 401 的请求不应占用额度"

    assert client.get("/api/stats", headers={"X-API-Token": "secret-123"}).status_code == 429
