import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch

from backend.routers.sources import router
from fastapi import FastAPI

# 创建测试用 app
app = FastAPI()
app.include_router(router)
client = TestClient(app)


# ---------- Fixture ----------

@pytest.fixture
def mock_get_source_stats():
    with patch("backend.routers.sources.get_source_stats") as mock:
        yield mock


@pytest.fixture
def mock_profile():
    """mock get_profile/set_profile，selected_sources 默认空（=全选）。"""
    profile = {"selected_sources": []}
    with patch("backend.routers.sources.get_profile") as mock_get, \
         patch("backend.routers.sources.set_profile") as mock_set:
        mock_get.side_effect = lambda: profile
        mock_set.side_effect = lambda **kw: profile.update(kw)
        yield profile


# ---------- GET /api/sources ----------

def test_list_sources_default(mock_get_source_stats, mock_profile):
    """默认情况：DB 无数据，各源 article_count 为 0，全部 enabled。"""
    mock_get_source_stats.return_value = {}

    response = client.get("/api/sources")
    assert response.status_code == 200
    data = response.json()
    assert "sources" in data
    assert len(data["sources"]) == 4

    for s in data["sources"]:
        assert "name" in s
        assert "label" in s
        assert "description" in s
        assert "category" in s
        assert "enabled" in s

    # category 为英文枚举（前端 i18n 按此映射展示文本）
    assert {s["category"] for s in data["sources"]} <= {
        "tech_community", "academic", "chinese_media"
    }

    for s in data["sources"]:
        assert s["article_count"] == 0
        assert s["enabled"] is True  # 空列表=全选

    names = [s["name"] for s in data["sources"]]
    assert "hackernews" in names
    assert "arxiv" in names
    assert "huggingface_papers" in names
    assert "rss" in names  # RSS 聚合源默认启用


def test_list_sources_with_counts(mock_get_source_stats, mock_profile):
    """DB 有数据时，article_count 反映实际数量。"""
    mock_get_source_stats.return_value = {
        "hackernews": 152,
        "arxiv": 89,
        "huggingface_papers": 7,
        "rss": 3,
    }

    response = client.get("/api/sources")
    data = response.json()
    counts = {s["name"]: s["article_count"] for s in data["sources"]}
    assert counts["hackernews"] == 152
    assert counts["arxiv"] == 89
    assert counts["rss"] == 3


def test_list_sources_respects_selected(mock_get_source_stats, mock_profile):
    """selected_sources 非空时，只有选中的源 enabled。"""
    mock_profile["selected_sources"] = ["arxiv"]
    mock_get_source_stats.return_value = {}

    response = client.get("/api/sources")
    data = response.json()
    states = {s["name"]: s["enabled"] for s in data["sources"]}
    assert states["arxiv"] is True
    assert states["hackernews"] is False
    assert states["rss"] is False


# ---------- PUT /api/sources/{name} ----------

def test_toggle_disable_source(mock_get_source_stats, mock_profile):
    """关闭某个源。"""
    response = client.put("/api/sources/arxiv", json={"enabled": False})
    assert response.status_code == 200
    body = response.json()
    assert body["enabled"] is False
    # arxiv 被剔除
    assert "arxiv" not in body["selected_sources"]


def test_toggle_enable_source(mock_get_source_stats, mock_profile):
    """开启某个已关闭的源。"""
    mock_profile["selected_sources"] = ["hackernews"]
    response = client.put("/api/sources/arxiv", json={"enabled": True})
    assert response.status_code == 200
    body = response.json()
    assert body["enabled"] is True
    assert "arxiv" in body["selected_sources"]


def test_toggle_normalizes_to_all(mock_get_source_stats, mock_profile):
    """开启到全部源时，规范化存回空列表（全选态）。"""
    mock_profile["selected_sources"] = ["hackernews", "arxiv", "huggingface_papers"]
    # 开启最后缺的 rss → 变成全选 → 规范化为 []
    response = client.put("/api/sources/rss", json={"enabled": True})
    assert response.status_code == 200
    assert response.json()["selected_sources"] == []


def test_toggle_unknown_source_404(mock_get_source_stats, mock_profile):
    """未知源返回 404。"""
    response = client.put("/api/sources/nonexistent", json={"enabled": True})
    assert response.status_code == 404


def test_toggle_last_source_400(mock_get_source_stats, mock_profile):
    """关闭最后一个源返回 400。"""
    mock_profile["selected_sources"] = ["arxiv"]
    response = client.put("/api/sources/arxiv", json={"enabled": False})
    assert response.status_code == 400
    assert "至少保留一个数据源" in response.json()["detail"]
