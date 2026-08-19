import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

# 导入包含路由的 APIRouter（这里假设路由定义在 backend.routers.articles 中）
from backend.routers.articles import router
from fastapi import FastAPI

# 创建测试用 app
app = FastAPI()
app.include_router(router)
client = TestClient(app)


# ---------- 测试用例 ----------

def test_get_articles_default(mock_query_articles):
    """测试默认参数：days=7, sources=None, limit=20"""
    # mock 返回值
    mock_query_articles.return_value = [
        {"id": 1, "title": "Article A", "tags": ["AI"], "collected_at": "2026-08-04"}
    ]

    response = client.get("/api/articles")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert len(data["articles"]) == 1
    assert data["articles"][0]["title"] == "Article A"

    # 验证 query_articles 被正确调用
    mock_query_articles.assert_called_once_with(
        days=7,
        sources=None,
        limit=20
    )


def test_get_articles_with_days_and_limit(mock_query_articles):
    """测试自定义 days 和 limit"""
    mock_query_articles.return_value = []

    response = client.get("/api/articles?days=3&limit=5")
    assert response.status_code == 200
    mock_query_articles.assert_called_once_with(
        days=3,
        sources=None,
        limit=5
    )


def test_get_articles_with_single_source(mock_query_articles):
    """测试单个 sources 参数"""
    mock_query_articles.return_value = []

    response = client.get("/api/articles?sources=arxiv")
    assert response.status_code == 200
    mock_query_articles.assert_called_once_with(
        days=7,
        sources=["arxiv"],
        limit=20
    )


def test_get_articles_with_multiple_sources(mock_query_articles):
    """测试多个 sources（逗号分隔）"""
    mock_query_articles.return_value = []

    response = client.get("/api/articles?sources=arxiv,hackernews,medium")
    assert response.status_code == 200
    mock_query_articles.assert_called_once_with(
        days=7,
        sources=["arxiv", "hackernews", "medium"],
        limit=20
    )


def test_get_articles_with_sources_containing_spaces(mock_query_articles):
    """测试 sources 包含空格（strip 处理）"""
    mock_query_articles.return_value = []

    response = client.get("/api/articles?sources= arxiv , hackernews ")
    assert response.status_code == 200
    mock_query_articles.assert_called_once_with(
        days=7,
        sources=["arxiv", "hackernews"],
        limit=20
    )


def test_get_articles_with_empty_sources(mock_query_articles):
    """测试 sources 为空字符串 → 应转为 None"""
    mock_query_articles.return_value = []

    response = client.get("/api/articles?sources=")
    assert response.status_code == 200
    mock_query_articles.assert_called_once_with(
        days=7,
        sources=None,   # 因为 if sources else None 为空字符串走 else
        limit=20
    )


def test_get_articles_with_only_commas(mock_query_articles):
    """测试 sources 为 "," → split 后产生空字符串（未过滤）"""
    mock_query_articles.return_value = []

    response = client.get("/api/articles?sources=,")
    assert response.status_code == 200
    # 此处会调用 sources=["", ""]（因为 strip 后变空字符串，但未过滤）
    # 实际业务可能不希望这样，你可以根据需求决定是否过滤
    mock_query_articles.assert_called_once_with(
        days=7,
        sources=["", ""],
        limit=20
    )
    # 如果想避免这种情况，可以在路由层加上过滤，测试也会相应变化


# ---------- Fixture 用于 mock ----------

@pytest.fixture
def mock_query_articles():
    with patch("backend.routers.articles.query_articles") as mock:
        yield mock