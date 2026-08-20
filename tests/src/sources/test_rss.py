"""
测试通用 RSS 数据源 — RSS/Atom feed 解析。

覆盖：
    - _parse_feed 单元测试（纯函数，无网络）：RSS 2.0 / Atom / 空 / 畸形 / 去重
    - fetch 无 feed 配置返回空
    - _backoff_active 退避判定（官方免费 RSS 60 分钟/次限制）
"""

import time

import httpx
import pytest

from src.sources.rss import RSSSource, _backoff_active


# ── fixture XML ──────────────────────────────────────────────────────────────

def _rss_xml() -> str:
    """RSS 2.0 格式。"""
    return """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel>
  <title>Test Feed</title>
  <item>
    <title>机器之心文章一</title>
    <link>https://example.com/a1</link>
    <guid>https://example.com/a1</guid>
    <description>关于大模型的文章</description>
  </item>
  <item>
    <title>机器之心文章二</title>
    <link>https://example.com/a2</link>
    <guid>https://example.com/a2</guid>
  </item>
</channel></rss>
"""


def _atom_xml() -> str:
    """Atom 格式。"""
    return """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>Atom Feed</title>
  <entry>
    <title>知乎热榜问题一</title>
    <link href="https://www.zhihu.com/q/1"/>
    <id>urn:zhihu:1</id>
    <summary>热门问题摘要</summary>
  </entry>
  <entry>
    <title>知乎热榜问题二</title>
    <link href="https://www.zhihu.com/q/2"/>
    <id>urn:zhihu:2</id>
  </entry>
</feed>
"""


# ── 单元测试：_parse_feed ────────────────────────────────────────────────────

def test_parse_rss():
    """RSS 2.0 格式解析正确。"""
    source = RSSSource()
    articles = source._parse_feed(_rss_xml(), "https://feed.example.com", limit=20)

    assert len(articles) == 2
    a = articles[0]
    assert a.id == "rss_https://example.com/a1"
    assert a.title == "机器之心文章一"
    assert a.url == "https://example.com/a1"
    assert a.source == "rss"
    assert a.language == "zh"
    assert a.summary == "关于大模型的文章"


def test_parse_atom():
    """Atom 格式解析正确（href 属性取链接）。"""
    source = RSSSource()
    articles = source._parse_feed(_atom_xml(), "https://feed.example.com", limit=20)

    assert len(articles) == 2
    assert articles[0].title == "知乎热榜问题一"
    assert articles[0].url == "https://www.zhihu.com/q/1"
    assert articles[0].id == "rss_urn:zhihu:1"


def test_parse_limit_truncates():
    """超过 limit 截断。"""
    source = RSSSource()
    articles = source._parse_feed(_rss_xml(), "https://f", limit=1)
    assert len(articles) == 1


def test_parse_empty_feed():
    """无 item 的 feed 返回空。"""
    source = RSSSource()
    assert source._parse_feed("<rss><channel><title>empty</title></channel></rss>", "f", 20) == []


def test_parse_malformed_xml():
    """畸形 XML 返回空，不抛异常。"""
    source = RSSSource()
    assert source._parse_feed("<rss><channel>broken", "f", 20) == []


# ── fetch ────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_fetch_no_feeds_returns_empty():
    """未配置 feed 时返回空。"""
    source = RSSSource(feeds=[])
    assert await source.fetch(limit=10) == []


# ── 退避（官方免费 RSS：最多每 60 分钟请求一次） ──────────────────────────────

def test_backoff_active_within_interval():
    """距上次请求不足 min_interval 时处于退避期。"""
    now = time.monotonic()
    assert _backoff_active(now, now - 300, 3600) is True  # 5 分钟前
    assert _backoff_active(now, now, 3600) is True  # 刚刚请求过


def test_backoff_inactive_after_interval():
    """超过 min_interval 后退出退避期。"""
    now = time.monotonic()
    assert _backoff_active(now, now - 3601, 3600) is False


def test_backoff_disabled_or_never_requested():
    """min_interval<=0 或从未请求过时不退避。"""
    now = time.monotonic()
    assert _backoff_active(now, None, 3600) is False  # 从未请求
    assert _backoff_active(now, now - 10, 0) is False  # 禁用退避
    assert _backoff_active(now, None, 0) is False


@pytest.mark.asyncio
async def test_fetch_skips_within_backoff(monkeypatch):
    """退避期内 fetch 不发起网络请求，直接返回空。"""
    from src.sources import rss as rss_module

    monkeypatch.setattr(rss_module, "_last_request_ts", time.monotonic())

    called = False

    async def fake_request(*args, **kwargs):
        nonlocal called
        called = True
        return []

    monkeypatch.setattr(rss_module.httpx.AsyncClient, "__aenter__", fake_request)

    source = RSSSource(feeds=["https://feed.invalid/x"], min_interval=3600)
    result = await source.fetch(limit=10)
    assert result == []
    assert called is False  # 未触碰网络


@pytest.mark.asyncio
async def test_fetch_skips_within_429_cooldown(monkeypatch):
    """429 冷却期内 fetch 直接跳过（额度耗尽后避免白碰壁）。"""
    from src.sources import rss as rss_module

    monkeypatch.setattr(rss_module, "_last_429_ts", time.monotonic())

    called = False

    async def fake_request(*args, **kwargs):
        nonlocal called
        called = True
        return []

    monkeypatch.setattr(rss_module.httpx.AsyncClient, "__aenter__", fake_request)

    source = RSSSource(feeds=["https://feed.invalid/x"], min_interval=0)
    result = await source.fetch(limit=10)
    assert result == []
    assert called is False  # 未触碰网络


@pytest.mark.asyncio
async def test_fetch_feed_429_sets_cooldown(monkeypatch):
    """_fetch_feed 收到 429 时记录冷却时间（跨实例共享）。"""
    from src.sources import rss as rss_module

    monkeypatch.setattr(rss_module, "_last_429_ts", None)

    class FakeResponse:
        status_code = 429

    class FakeClient:
        async def get(self, url):
            raise httpx.HTTPStatusError(
                "429 Too Many Requests", request=httpx.Request("GET", url), response=FakeResponse()
            )

    source = RSSSource(feeds=["https://feed.invalid/x"], min_interval=0)
    result = await source._fetch_feed(FakeClient(), "https://feed.invalid/x", 10)
    assert result == []
    assert rss_module._last_429_ts is not None  # 已进入冷却


@pytest.mark.integration
@pytest.mark.asyncio
async def test_fetch_rsshub():
    """真网络：抓取一个公开 RSS feed（弱断言）。"""
    source = RSSSource(feeds=["https://rsshub.app/1x1/notion"])
    articles = await source.fetch(limit=5)
    # 网络不可达或 feed 不可用时返回空，不抛异常
    assert isinstance(articles, list)
    if articles:
        assert all(a.source == "rss" for a in articles)
