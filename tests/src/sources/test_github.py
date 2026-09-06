"""
测试 GitHub Trending 数据源 — 页面解析。

覆盖：
    - _parse_html 单元测试（纯函数，无网络）：基础字段 / 无描述 / 无今日 star
      回退总 star / 截断 / 畸形 / 空页
    - _extract_stars_today / _parse_int 辅助函数
    - fetch 网络错误返回空（httpx 异常模拟）
"""

import httpx
import pytest

from src.sources.github import (
    GitHubSource,
    DEFAULT_TOPICS,
    _extract_stars_today,
    _merge_dedup,
    _parse_int,
    _resolve_topics,
)


# ── fixture HTML ─────────────────────────────────────────────────────────────

def _trending_html() -> str:
    """模仿 github.com/trending 的 Box-row 结构（两个仓库）。"""
    return """<html><body><main>
  <article class="Box-row">
    <h2 class="h3 lh-condensed">
      <a href="/openai/openai">openai / <b>openai</b></a>
    </h2>
    <p>OpenAI 官方仓库</p>
    <div class="f6">
      <span><span class="repo-language-color"></span>
        <span itemprop="programmingLanguage">Python</span></span>
      <a href="/openai/openai/stargazers">82,431</a>
      <a href="/openai/openai/forks">12,345</a>
      <span class="float-sm-right">+1,234 stars today</span>
    </div>
  </article>
  <article class="Box-row">
    <h2 class="h3 lh-condensed">
      <a href="/anthropics/anthropic-sdk-python">anthropics / <b>anthropic-sdk-python</b></a>
    </h2>
    <p>Anthropic Python SDK</p>
    <div class="f6">
      <span><span class="repo-language-color"></span>
        <span itemprop="programmingLanguage">TypeScript</span></span>
      <a href="/anthropics/anthropic-sdk-python/stargazers">567</a>
      <a href="/anthropics/anthropic-sdk-python/forks">89</a>
      <span class="float-sm-right">+12 stars today</span>
    </div>
  </article>
</main></body></html>
"""


# ── 单元测试：_parse_html ────────────────────────────────────────────────────

def test_parse_basic_fields():
    """基础字段映射：id/title/url/summary/score/tags/author/language/published_at。"""
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)
    articles = GitHubSource()._parse_html(_trending_html(), limit=10, published_at=now)
    assert len(articles) == 2

    a = articles[0]
    assert a.id == "github_openai/openai"
    assert a.title == "openai/openai"
    assert a.url == "https://github.com/openai/openai"
    assert a.source == "github"
    assert a.summary == "OpenAI 官方仓库"
    assert a.author == "openai"
    assert a.score == 1234  # 今日新增 star（去千分位逗号）
    assert a.tags == ["Python"]
    assert a.language == "en"
    assert a.published_at == now  # trending 无日期，取采集时刻

    b = articles[1]
    assert b.id == "github_anthropics/anthropic-sdk-python"
    assert b.score == 12
    assert b.tags == ["TypeScript"]


def test_parse_limit_truncation():
    """limit 截断生效。"""
    articles = GitHubSource()._parse_html(_trending_html(), limit=1)
    assert len(articles) == 1
    assert articles[0].title == "openai/openai"


def test_parse_no_today_stars_falls_back_to_total():
    """无"stars today"时回退总 star 数（去逗号）。"""
    html = _trending_html().replace("+1,234 stars today", "")
    articles = GitHubSource()._parse_html(html, limit=10)
    assert articles[0].score == 82431


def test_parse_missing_description():
    """无描述时 summary 为 None。"""
    html = _trending_html().replace("<p>OpenAI 官方仓库</p>", "")
    articles = GitHubSource()._parse_html(html, limit=10)
    assert articles[0].summary is None


def test_parse_missing_language():
    """无语言标签时 tags 为空。"""
    html = _trending_html().replace(
        '<span itemprop="programmingLanguage">Python</span>', ""
    )
    articles = GitHubSource()._parse_html(html, limit=10)
    assert articles[0].tags == []


def test_parse_malformed_row_skipped():
    """缺少 h2 a 的行跳过，不影响其他行。"""
    html = _trending_html().replace(
        '<a href="/openai/openai">openai / <b>openai</b></a>', ""
    )
    articles = GitHubSource()._parse_html(html, limit=10)
    assert len(articles) == 1
    assert articles[0].title == "anthropics/anthropic-sdk-python"


def test_parse_empty_html():
    """空页/无 Box-row 返回空列表。"""
    assert GitHubSource()._parse_html("", limit=10) == []
    assert GitHubSource()._parse_html("<html><body></body></html>", limit=10) == []


# ── 辅助函数 ─────────────────────────────────────────────────────────────────

def test_extract_stars_today():
    assert _extract_stars_today("+1,234 stars today") == 1234
    assert _extract_stars_today("+56 stars today") == 56
    assert _extract_stars_today("no stars info") is None
    assert _extract_stars_today("") is None


def test_parse_int():
    assert _parse_int("1,234") == 1234
    assert _parse_int(" 82,431 ") == 82431
    assert _parse_int("0") == 0
    assert _parse_int("abc") is None
    assert _parse_int("") is None


# ── fetch 网络错误降级 ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_fetch_network_error_returns_empty(monkeypatch):
    """fetch 网络错误返回空列表（不影响其他源）。"""

    class FakeResp:
        def raise_for_status(self):
            raise httpx.ConnectError("proxy down")

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        async def get(self, url):
            return FakeResp()

    monkeypatch.setattr("src.sources.github.httpx.AsyncClient", FakeClient)
    assert await GitHubSource().fetch(limit=5) == []


# ── explore 解析（2026-08-20 新增：整合 github.com/explore 推荐仓库）───────────

EXPLORE_HTML = """<html><body>
  <div class="d-md-flex">
    <div>
      <article class="border rounded color-shadow-small color-bg-subtle">
        <div class="d-flex tmp-p-3">
          <div class="col-sm-10 d-flex tmp-mr-3">
            <h3><a href="/openai/codex">openai / codex</a></h3>
          </div>
          <p>Lightweight coding agent for your terminal</p>
          <span itemprop="programmingLanguage">Rust</span>
        </div>
      </article>
      <article class="border rounded color-shadow-small color-bg-subtle">
        <div class="d-flex tmp-p-3">
          <h3><a href="/anthropics/claude-code">anthropics / claude-code</a></h3>
          <p>Claude Code CLI</p>
          <span itemprop="programmingLanguage">Go</span>
        </div>
      </article>
    </div>
    <div>
      <h3><a href="/topics/database">Database</a></h3>
      <h3><a href="/collections/pixel-art-tools">Pixel Art Tools</a></h3>
      <h3><a href="/marketplace/snyk">Snyk</a></h3>
      <h3><a href="/trending/developers">Trending developers</a></h3>
    </div>
  </div>
</body></html>"""


def test_parse_explore_extracts_repos():
    """explore 解析：只取 owner/repo 仓库，排除 topics/collections/marketplace/trending。"""
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)
    articles = GitHubSource()._parse_repo_page_html(EXPLORE_HTML, limit=20, published_at=now)
    ids = [a.id for a in articles]
    assert ids == ["github_openai/codex", "github_anthropics/claude-code"]

    first = articles[0]
    assert first.title == "openai/codex"
    assert first.summary == "Lightweight coding agent for your terminal"
    assert first.tags == ["Rust"]
    assert first.score == 0  # explore 无 today 数据，不参与热度量纲
    assert first.url == "https://github.com/openai/codex"
    assert first.source == "github"
    assert first.published_at == now


def test_parse_explore_limit():
    from datetime import datetime, timezone

    articles = GitHubSource()._parse_repo_page_html(
        EXPLORE_HTML, limit=1, published_at=datetime.now(timezone.utc)
    )
    assert len(articles) == 1
    assert articles[0].id == "github_openai/codex"


def test_parse_explore_empty():
    assert GitHubSource()._parse_repo_page_html("<html><body></body></html>", 20) == []
    assert GitHubSource()._parse_repo_page_html("", 20) == []


# ── topics 活跃榜解析（2026-09-06 新增：github.com/topics/{t}?s=updated）───────

TOPIC_HTML = """<html><body>
  <article class="border rounded color-shadow-small color-bg-subtle tmp-my-4">
    <h3>
      <a href="/theYahia">theYahia</a>
      <a href="/theYahia/yandex-metrika-mcp">theYahia / yandex-metrika-mcp</a>
    </h3>
    <p>MCP server for Yandex Metrika</p>
    <ul>
      <li>Updated <relative-time datetime="2026-09-06T08:42:01Z" class="no-wrap">Sep 6, 2026</relative-time></li>
      <li><span itemprop="programmingLanguage">TypeScript</span></li>
    </ul>
  </article>
  <article class="border rounded color-shadow-small color-bg-subtle tmp-my-4">
    <h3>
      <a href="/huggingface">huggingface</a>
      <a href="/huggingface/transformers">huggingface / transformers</a>
    </h3>
    <p>Transformers: State-of-the-art ML</p>
    <ul>
      <li>Updated <relative-time datetime="2026-08-20T10:00:00Z">Aug 20, 2026</relative-time></li>
      <li><span itemprop="programmingLanguage">Python</span></li>
    </ul>
  </article>
  <article class="border rounded color-shadow-small color-bg-subtle tmp-my-4">
    <h3><a href="/topics/llm">llm topic link</a></h3>
  </article>
</body></html>"""


def test_parse_topic_takes_repo_link_and_uses_updated():
    """topics 解析：h3 双链接（owner 页 + 仓库）取仓库链接；活跃时间优先于采集时刻。"""
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)
    articles = GitHubSource()._parse_repo_page_html(
        TOPIC_HTML, limit=20, published_at=now, use_updated=True
    )
    ids = [a.id for a in articles]
    assert ids == ["github_theYahia/yandex-metrika-mcp", "github_huggingface/transformers"]

    first = articles[0]
    assert first.title == "theYahia/yandex-metrika-mcp"
    assert first.summary == "MCP server for Yandex Metrika"
    assert first.tags == ["TypeScript"]
    assert first.score == 0  # 与 explore 同语义：无 today 数据
    # published_at 取行内 relative-time 的真实活跃时间（UTC），而非采集时刻
    assert first.published_at.isoformat() == "2026-09-06T08:42:01+00:00"
    assert articles[1].published_at.isoformat() == "2026-08-20T10:00:00+00:00"
    # topics/llm 等单段或排除前缀的链接行被跳过
    assert len(articles) == 2


def test_parse_topic_limit():
    from datetime import datetime, timezone

    articles = GitHubSource()._parse_repo_page_html(
        TOPIC_HTML, limit=1, published_at=datetime.now(timezone.utc), use_updated=True
    )
    assert len(articles) == 1
    assert articles[0].id == "github_theYahia/yandex-metrika-mcp"


def test_parse_topic_uses_collected_at_when_no_updated():
    """行内无 relative-time（或日期非法）时回退采集时刻。"""
    from datetime import datetime, timezone

    html = """<html><body>
      <article class="border rounded">
        <h3><a href="/foo/bar">foo / bar</a></h3>
        <p>desc</p>
        <ul><li>Updated</li></ul>
      </article>
    </body></html>"""
    now = datetime(2026, 9, 6, 3, 0, tzinfo=timezone.utc)
    articles = GitHubSource()._parse_repo_page_html(html, limit=10, published_at=now, use_updated=True)
    assert len(articles) == 1
    assert articles[0].published_at == now


def test_resolve_topics():
    """GITHUB_TOPICS 解析：逗号分隔 + 去空白小写；空配置回退内置默认主题。"""
    assert _resolve_topics(" llm ,agents,RAG ") == ("llm", "agents", "rag")
    assert _resolve_topics("") == DEFAULT_TOPICS
    assert _resolve_topics("  ,  ") == DEFAULT_TOPICS


# ── 合并去重（trending + explore 整合）────────────────────────────────────────

def _article(article_id: str, score: int):
    from src.models import Article

    return Article(
        id=article_id,
        title=article_id,
        url=f"https://github.com/{article_id}",
        source="github",
        summary=None,
        author="owner",
        published_at=None,
        score=score,
        tags=[],
        language="en",
    )


def test_merge_dedup_trending_priority():
    """重叠仓库保留 trending 版本（有 today 分数），explore 补充不重复仓库。"""
    trending = [_article("github_openai/codex", 1234), _article("github_a/b", 50)]
    explore = [_article("github_openai/codex", 0), _article("github_c/d", 0)]
    merged = _merge_dedup(trending, explore)
    assert [a.id for a in merged] == ["github_openai/codex", "github_a/b", "github_c/d"]
    codex = next(a for a in merged if a.id == "github_openai/codex")
    assert codex.score == 1234  # trending 优先，不被 explore 的 0 覆盖


def test_merge_dedup_secondary_only():
    """trending 为空时 explore 独立成列表。"""
    merged = _merge_dedup([], [_article("github_only/explore", 0)])
    assert [a.id for a in merged] == ["github_only/explore"]
