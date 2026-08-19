import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch

from backend.routers.stats import router
from fastapi import FastAPI

app = FastAPI()
app.include_router(router)
client = TestClient(app)


# ---------- 测试用例 ----------

def test_list_stats_empty(mock_get_collection_stats):
    """DB 无采集记录时，返回默认值"""
    mock_get_collection_stats.return_value = {
        "total_runs": 0,
        "total_articles": 0,
        "last_collection_at": None,
        "runs": [],
    }

    response = client.get("/api/stats")
    assert response.status_code == 200
    data = response.json()
    assert data["total_runs"] == 0
    assert data["total_articles"] == 0
    assert data["last_collection_at"] is None
    assert data["runs"] == []


def test_list_stats_with_data(mock_get_collection_stats):
    """有采集记录时，返回统计 + 明细"""
    mock_get_collection_stats.return_value = {
        "total_runs": 5,
        "total_articles": 120,
        "last_collection_at": "2026-08-05T14:00:00+00:00",
        "runs": [
            {
                "id": 5,
                "started_at": "2026-08-05T14:00:00+00:00",
                "finished_at": "2026-08-05T14:00:05+00:00",
                "total_articles": 25,
                "deduped_count": 2,
                "status": "finished",
                "source_stats": [
                    {"name": "arxiv", "fetched": 15, "failed": False, "error": None, "elapsed_ms": 2000},
                    {"name": "hackernews", "fetched": 10, "failed": False, "error": None, "elapsed_ms": 1500},
                ],
                "error": None,
            },
        ],
    }

    response = client.get("/api/stats")
    assert response.status_code == 200
    data = response.json()
    assert data["total_runs"] == 5
    assert data["total_articles"] == 120
    assert data["last_collection_at"] == "2026-08-05T14:00:00+00:00"
    assert len(data["runs"]) == 1
    run = data["runs"][0]
    assert run["id"] == 5
    assert run["total_articles"] == 25
    assert run["deduped_count"] == 2
    assert run["status"] == "finished"
    assert len(run["source_stats"]) == 2
    assert run["source_stats"][0]["name"] == "arxiv"


def test_list_stats_custom_limit(mock_get_collection_stats):
    """limit 参数应透传给 get_collection_stats"""
    mock_get_collection_stats.return_value = {
        "total_runs": 0,
        "total_articles": 0,
        "last_collection_at": None,
        "runs": [],
    }

    response = client.get("/api/stats?limit=5")
    assert response.status_code == 200
    mock_get_collection_stats.assert_called_once_with(limit=5)


def test_list_stats_limit_out_of_range_422():
    """limit 超出范围应返回 422"""
    response = client.get("/api/stats?limit=0")
    assert response.status_code == 422

    response = client.get("/api/stats?limit=200")
    assert response.status_code == 422


# ---------- Fixture ----------

@pytest.fixture
def mock_get_collection_stats():
    with patch("backend.routers.stats.get_collection_stats") as mock:
        yield mock
