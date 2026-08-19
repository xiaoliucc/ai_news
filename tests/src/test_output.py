"""
测试 output 模块 — 三种输出格式。

覆盖：
    - output_text:  纯文本格式
    - output_json:  JSON 格式
    - output_markdown: Markdown 格式
    - 边界情况: 空列表处理
"""

import json
from datetime import datetime

from src.models import Article
from src.output import output_text, output_json, output_markdown


# ---------------------------------------------------------------------------
# 测试数据
# ---------------------------------------------------------------------------

def make_article(**kwargs) -> Article:
    """快速创建测试用 Article，参数覆盖默认值。"""
    defaults = {
        "id": "1",
        "title": "Test Article",
        "url": "https://example.com",
        "source": "hackernews",
        "summary": None,
        "author": "Alice",
        "published_at": datetime(2026, 7, 31, 10, 30),
        "score": 100,
        "tags": ["LLM"],
        "language": "en",
    }
    defaults.update(kwargs)
    return Article(**defaults)


# ---------------------------------------------------------------------------
# output_text 测试
# ---------------------------------------------------------------------------

class TestOutputText:

    def test_empty_list(self):
        """空列表返回提示信息。"""
        result = output_text([])
        assert "暂无" in result

    def test_single_article(self):
        """单篇文章应包含标题和 URL。"""
        a = make_article(title="AI News")
        result = output_text([a])  # 修复：传入列表
        assert "AI News" in result
        assert "https://example.com" in result

    def test_shows_source_and_score(self):
        """应显示来源名和热度分数。"""
        a = make_article(source="arxiv", score=42)
        result = output_text([a])  # 修复：传入列表
        assert "arxiv" in result
        assert "42" in result

    def test_unknown_time(self):
        """published_at 为 None 时显示'未知'。"""
        a = make_article(published_at=None)
        result = output_text([a])  # 修复：传入列表
        assert "未知" in result


# ---------------------------------------------------------------------------
# output_json 测试
# ---------------------------------------------------------------------------

class TestOutputJson:

    def test_empty_list(self):
        """空列表返回空 JSON 数组。"""
        result = output_json([])
        assert json.loads(result) == []

    def test_valid_json(self):
        """返回合法 JSON 字符串。"""
        a = make_article()
        result = output_json([a])  # 修复：传入列表
        parsed = json.loads(result)
        assert isinstance(parsed, list)

    def test_preserves_all_fields(self):
        """所有字段应保留在 JSON 中。"""
        a = make_article()
        result = output_json([a])  # 修复：传入列表
        parsed = json.loads(result)[0]
        assert parsed["id"] == "1"
        assert parsed["title"] == "Test Article"
        assert parsed["url"] == "https://example.com"
        assert parsed["source"] == "hackernews"
        assert parsed["summary"] is None
        assert parsed["author"] == "Alice"
        assert parsed["score"] == 100
        assert parsed["tags"] == ["LLM"]
        assert parsed["language"] == "en"

    def test_datetime_serialized_as_iso(self):
        """published_at 应序列化为 ISO 格式字符串。"""
        a = make_article(published_at=datetime(2026, 7, 31, 10, 30, 0))
        result = output_json([a])  # 修复：传入列表
        parsed = json.loads(result)[0]
        assert parsed["published_at"] == "2026-07-31T10:30:00"

    def test_none_datetime(self):
        """published_at 为 None 时 JSON 中为 null。"""
        a = make_article(published_at=None)
        result = output_json([a])  # 修复：传入列表
        parsed = json.loads(result)[0]
        assert parsed["published_at"] is None


# ---------------------------------------------------------------------------
# output_markdown 测试
# ---------------------------------------------------------------------------

class TestOutputMarkdown:

    def test_empty_list(self):
        """空列表返回提示信息。"""
        result = output_markdown([])
        assert "暂无" in result

    def test_contains_article_title(self):
        """应包含文章标题。"""
        a = make_article(title="GPT-5 发布")
        result = output_markdown([a])  # 修复：传入列表
        assert "GPT-5 发布" in result

    def test_contains_link(self):
        """应包含原文链接。"""
        a = make_article()
        result = output_markdown([a])  # 修复：传入列表
        assert "https://example.com" in result

    def test_contains_source_info(self):
        """应包含来源和热度信息。"""
        a = make_article(source="papers", score=200)
        result = output_markdown([a])  # 修复：传入列表
        assert "papers" in result
        assert "200" in result