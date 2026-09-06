"""
测试 CSDN 热榜数据源 — 热榜 JSON 解析。

覆盖：
    - _parse_rows 单元测试（纯函数，无网络）：基础字段 / id 提取 / 跳过
      畸形行 / 截断 / 空数据 / 去重
    - fetch 网络错误返回空（httpx 异常模拟）
"""

import httpx
import pytest

from src.sources.csdn import CsdnSource

# ── fixture 数据（真实接口形态：数字字段均为字符串）──────────────────────────

_ROWS = [
    {
        "articleTitle": "【LangChain】实战指南：从模型定义到终端",
        "articleDetailUrl": "https://blog.csdn.net/author_a/article/details/164109036",
        "productId": "164109036",
        "nickName": "作者A",
        "viewCount": "2333",
        "favorCount": "59",
        "hotRankScore": "24913",
    },
    {
        "articleTitle": "鸿蒙应用 AI 对话实战",
        "articleDetailUrl": "https://blog.csdn.net/author_b/article/details/164208877",
        "productId": "164208877",
        "nickName": "作者B",
        "viewCount": "15200",
        "favorCount": "9",
    },
    {
        # 无 productId 且 URL 无法提取数字 ID → 跳过
        "articleTitle": "无链接文章",
        "articleDetailUrl": "https://blog.csdn.net/author_c/article/not-a-number",
        "nickName": "作者C",
        "viewCount": "100",
    },
    {
        # 空标题 → 跳过
        "articleTitle": "",
        "articleDetailUrl": "https://blog.csdn.net/x/article/details/164300000",
        "productId": "164300000",
        "nickName": "作者D",
        "viewCount": "200",
    },
]


# ── _parse_rows 单元测试 ─────────────────────────────────────────────────────

def test_parse_basic_fields():
    """基础字段映射：id（productId）/标题/URL/作者/热度/语言/时间戳。"""
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)
    articles = CsdnSource()._parse_rows(_ROWS, limit=10, published_at=now)

    first = articles[0]
    assert first.id == "csdn_164109036"  # productId
    assert first.title == "【LangChain】实战指南：从模型定义到终端"
    assert first.url == "https://blog.csdn.net/author_a/article/details/164109036"
    assert first.author == "作者A"
    assert first.score == 2333  # viewCount（字符串 "2333"）作热度
    assert first.language == "zh"
    assert first.source == "csdn"
    assert first.summary is None  # 接口不含正文摘要
    assert first.tags == []
    assert first.published_at == now  # 无发布时间字段，取采集时刻
    # 无数字 ID / 空标题的两条被跳过
    assert len(articles) == 2


def test_parse_falls_back_to_url_id():
    """无 productId 时从 URL /details/{id} 回退提取。"""
    from datetime import datetime, timezone

    row = dict(_ROWS[0])
    row.pop("productId")
    articles = CsdnSource()._parse_rows(
        [row], limit=10, published_at=datetime.now(timezone.utc)
    )
    assert articles[0].id == "csdn_164109036"


def test_parse_limit_truncation():
    from datetime import datetime, timezone

    articles = CsdnSource()._parse_rows(
        _ROWS, limit=1, published_at=datetime.now(timezone.utc)
    )
    assert len(articles) == 1
    assert articles[0].id == "csdn_164109036"


def test_parse_dedup_same_article():
    """同一文章 ID 出现多次时只保留第一条。"""
    from datetime import datetime, timezone

    rows = [_ROWS[0], dict(_ROWS[0]), _ROWS[1]]
    articles = CsdnSource()._parse_rows(
        rows, limit=10, published_at=datetime.now(timezone.utc)
    )
    assert [a.id for a in articles] == ["csdn_164109036", "csdn_164208877"]


def test_parse_empty_or_malformed():
    """空列表 / None / 非 dict 行 → 空列表（不抛异常）。"""
    assert CsdnSource()._parse_rows(None, 10) == []
    assert CsdnSource()._parse_rows([], 10) == []
    assert CsdnSource()._parse_rows(["not-a-dict"], 10) == []
    assert CsdnSource()._parse_rows([{"articleTitle": "x"}], 10) == []  # 无 URL


def test_parse_view_count_not_int_degrades():
    """viewCount 非数字（如 "N/A"）时 score 置 0 不崩溃。"""
    from datetime import datetime, timezone

    row = dict(_ROWS[0])
    row["viewCount"] = "N/A"
    articles = CsdnSource()._parse_rows(
        [row], limit=10, published_at=datetime.now(timezone.utc)
    )
    assert articles[0].score == 0


def test_to_int():
    """_to_int：字符串数字 / int / 空 / 非数字的解析。"""
    from src.sources.csdn import _to_int

    assert _to_int("2333") == 2333
    assert _to_int(42) == 42
    assert _to_int(None) == 0
    assert _to_int("") == 0
    assert _to_int("N/A") == 0
    assert _to_int(0) == 0


# ── fetch 网络错误降级 ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_fetch_network_error_returns_empty(monkeypatch):
    """fetch 网络错误返回空列表（不影响其他源）。"""

    class FakeResp:
        def raise_for_status(self):
            raise httpx.ConnectError("network down")

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        async def get(self, url, params=None):
            return FakeResp()

    monkeypatch.setattr("src.sources.csdn.httpx.AsyncClient", FakeClient)
    assert await CsdnSource().fetch(limit=5) == []
