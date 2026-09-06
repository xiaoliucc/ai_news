# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Install dependencies
uv sync

# Run all tests
uv run pytest

# Run a single test file
uv run pytest tests/src/test_engine.py

# Run tests matching a keyword
uv run pytest -k "dedup"

# Run only unit tests (skip network-dependent integration tests)
uv run pytest -m unit
uv run pytest -m "not integration"

# Frontend tests (Vitest, tests/frontend/ mirrors frontend/src)
cd frontend && npm test

# CLI: fetch AI news from all sources
uv run python -m src.main fetch --limit 20

# CLI: specific sources, output to file
uv run python -m src.main fetch -s arxiv,hackernews -o markdown -f daily.md

# Start the FastAPI backend (with hot reload)
uv run uvicorn backend.main:app --reload

# Docker single-service deploy (frontend dist + backend + scheduler, port 8000)
docker compose up -d --build
# 墙内需 .env 配 DOCKER_HTTPS_PROXY=http://host.docker.internal:7890（Clash 开 Allow LAN）
# 模型缓存卷：HF_CACHE_DIR 指向本机缓存或留空首次联网下载

# Frontend: install deps, dev server, typecheck, build
cd frontend && npm install
cd frontend && npm run dev        # http://localhost:5173, /api proxied to :8000
cd frontend && npm run typecheck
cd frontend && npm run build
```

## Architecture

This is a **dual-mode Python application** (CLI tool + Web API) that aggregates AI research content from multiple sources. It uses `uv` for package management and requires Python ≥ 3.13.

### Two entry points, one engine

```
CLI (src/main.py) ──→ NewsEngine ──→ SourcePlugin.fetch() × N
                          │
Web API (backend/main.py) ┘
                          ↓
              deduplicate → rank → output / save to SQLite
```

**`src/`** — The headless data pipeline: data model, source plugins, engine, ranking, LLM integration, CLI entry point. No web awareness.

**`backend/`** — FastAPI layer: REST API, SQLite storage, APScheduler for periodic collection, and the AI Agent (LLM + tool-use loop). Depends on `src/` for the engine and models.

**`frontend/`** — Vue 3.5 SPA (Vite + TS + Element Plus + Pinia + vue-echarts), ported from the OpenDesign `endfield-ai-intel-dashboard` design project. Three-pane dashboard (sources sidebar / main articles-trends-hotlist / agent chat). Talks to the backend through an axios layer (`src/api/`) — dev proxy `/api` → `http://localhost:8000`.

### Core data flow

1. **Source plugins** (`src/sources/`) inherit from `SourcePlugin` (abstract `async fetch(limit) → list[Article]`). Six sources: HackerNews (Firebase API), ArXiv (official library), HuggingFace Papers (`/api/papers`), RSS (`rss.py`, a configurable RSS/Atom aggregator driven by `RSS_FEEDS`, used for Chinese sources), GitHub (`github.py`, parses the static `github.com/trending` + `github.com/explore` + AI topic pages (`/topics/{t}?o=desc&s=updated`, `.env` `GITHUB_TOPICS`) with BeautifulSoup — no official API; trending score = stars today, explore 推荐仓库与 topics 活跃仓库 score=0 避免量纲混用，页面按仓库 id 合并去重 trending 优先; explore/topics 的 `published_at` 分别取采集时刻与行内 `relative-time` 真实活跃时间), and CSDN (`csdn.py`, 解析博客热榜 JSON 接口 `phoenix/web/blog/hot-rank` — 无公开文档但结构稳定; 数字字段为字符串需 `_to_int`; score=viewCount; **直连不传代理**, 国内站). All httpx-based sources honor the global proxy: `.env` `HTTPS_PROXY` (empty = direct; system env var takes precedence over `.env` since `load_dotenv` doesn't override). CLI (`src/main.py`) keeps the original three; the scheduler registers all six via `SOURCE_REGISTRY`.

2. **NewsEngine.run()** concurrently calls all registered sources via `asyncio.gather`, tolerates individual source failures, then runs **cross-source dedup** (arxiv ID fingerprint matching across arxiv ↔ pwc ↔ HN) and **composite ranking** (`pipeline/ranking.py`: `normalized_score × time_decay (48h half-life) × source_weight`).

3. **Output**: In CLI mode, results pass through `filters.py` (keyword-based AI relevance gate) then to formatters (text/json/markdown). In backend mode, results go to `backend/database.py` (SQLite, WAL mode).

### AI Agent (`backend/agent/`)

A **tool-use loop** (not LangChain) built directly on the OpenAI-compatible SDK:

- `core.py` — main loop: system prompt → LLM call with tools → execute tool calls concurrently → repeat (max 5 turns). `chat()` takes `reading_history` (titles) and injects it into the system prompt to avoid re-recommending. **SSE 真流式（2026-08-28）**：新增 `chat_stream()` 事件生成器——LLM 调用 `stream=True`，工具轮发 `tool start/done` 事件（真实上报），答案轮 token 逐块 yield；同步流式 chunk 经线程+队列桥接（`_iter_chunks`）避免阻塞事件循环。路由 `/api/agent/chat` 返回 `text/event-stream`。
- `tools.py` — 6 tools all implemented: search_articles (ChromaDB semantic search with SQLite summary backfill; falls back to SQLite keyword search `_keyword_fallback` when ChromaDB returns empty; **exact-match shortcut**: space-less proper-noun queries like repo paths resolve via `_resolve_article` first), get_article_detail (SQLite; **`_resolve_article` falls back to exact-title match when the LLM passes a title instead of an ID**), summarize_articles (LLM), analyze_trend (semantic search + LLM hotspot detection), trigger_collection (scheduler.collect_once), **web_search (Tavily 联网搜索，2026-09-06)** — 采集库外的实时/最新信息；请求走全局代理（`backend.config.PROXY_URL`），key 读 `.env` `TAVILY_API_KEY`（config.TAVILY_API_KEY），未配置/网络失败返回可读 error 不中断对话；纯函数 `_parse_search_results` 过滤脏条目 + content 截断 500 字。get_article_detail/summarize_articles implicitly record read article IDs into `user_profile.reading_history` via `_record_reading_history` (dedup, newest-first, cap 50).
- `prompts.py` — system prompt with date anchor, data boundary rules, user preference injection

### Vector store (`backend/vector_store.py`)

ChromaDB with `PersistentClient` and SentenceTransformer embeddings (`paraphrase-multilingual-MiniLM-L12-v2`, 384-dim). Public API: `add_articles()`, `search()` (semantic with optional source/days filter using Unix timestamp metadata), `clear()`, `delete_article()`. Thread-safe lazy init via double-checked locking. `_get_embedding_fn()` lazily initializes the embedding function to avoid blocking on import. Index is maintained by the scheduler at collection time — Agent reads directly, no per-request rebuild.

### LLM integration (`src/pipeline/llm.py`)

LLM is accessed via **OpenAI-compatible endpoint** (qwen-turbo via DashScope by default, configurable via `.env`). `_build_client()` auto-selects the API key by base_url: DashScope → `DASHSCOPE_API_KEY`, otherwise → `DEEPSEEK_API_KEY` (optional `OPENAI_API_KEY` override). Key design: **graceful degradation** — when the LLM is unavailable, AI relevance judgment falls back to keyword matching (`filters.py`), and quality scoring returns `None`. `_chat_json` retries transient errors (connection/timeout/5xx/429) with exponential backoff.

### Database (`backend/database.py`)

Three SQLite tables: `articles` (INSERT OR REPLACE by id), `collection_runs` (logs each collection), `user_profile` (single-row, interests/reading_history/language). JSON columns (tags, interests) are serialized as strings and deserialized on read. Two aggregate queries: `get_source_stats()` (GROUP BY source), `get_collection_stats()` (total runs/articles + recent runs with parsed source_stats). Auto-init on import.

### Scheduler (`backend/scheduler.py`)

APScheduler `AsyncIOScheduler` with interval job. `start()` is idempotent — fires an immediate collection on startup via `asyncio.ensure_future`, then repeats every `COLLECTION_HOURS` (default 6h, from `.env`). `collect_once()` pipeline: instantiate sources per `user_profile.selected_sources` (empty = all, via `SOURCE_REGISTRY`) → engine.run() → `_filter_ai_related()` (LLM semantic AI-relevance filter, 4-thread concurrent, falls back to keyword matching when LLM unavailable) → save_articles (SQLite) → add_articles (ChromaDB). `_collect_lock` (asyncio.Lock) prevents concurrent collection. Source toggles via `PUT /api/sources/{name}` only affect the scheduler (CLI unaffected). Manual trigger: `POST /api/collect` (202 + background task) and the Agent's `trigger_collection` tool both call `collect_once()`.

## Key conventions

- **Tests mirror source structure**: `tests/src/test_engine.py` tests `src/engine.py`; `tests/backend/agent/test_agent.py` tests `backend/agent/core.py`. pytest config in `pyproject.toml` uses markers `unit`, `integration`, `slow`.
- **Config via `.env`**: `SQLITE_PATH`, `CHROMA_DIR`, `COLLECTION_LIMIT`, `COLLECTION_HOURS`, `RSS_FEEDS`, `DASHSCOPE_API_KEY`, `DEEPSEEK_API_KEY`, `LLM_MODEL_ID`, `LLM_BASE_URL`, `LLM_TIMEOUT`, `HTTPS_PROXY` (global proxy for walled-off sources like GitHub/HF; empty = direct; multi-device: each device keeps its own `.env`; restart to apply). **内网穿透（cpolar 双隧道，2026-08-28）**: `PUBLIC_BACKEND_URL`（后端 :8000 隧道 → 前端注入 `VITE_API_BASE` 并拼 `/api` 作为 API 地址）、`PUBLIC_FRONTEND_URL`（前端 :5173 隧道 → 后端 CORS 放行该 Origin）；留空 = 直连/局域网。前端构建时 vite.config `loadEnv` 读根 `.env` 注入；`server.allowedHosts` 动态放行 `.cpolar.top` 通配域 + 配置的隧道域名（Vite DNS-rebinding 防护默认拒外部域名），`server.host` 显式 `127.0.0.1`（Vite 默认只绑 IPv6 `[::1]`，cpolar 转发目标是 IPv4）。`.env.example` is the committed template.
- **Docstrings are Google style**: `Args:` / `Returns:` / `Raises:` sections.
- **Logging, not print**: Use `logging` (stderr) for diagnostics; stdout is reserved for CLI output that may be piped.
- **`_chat_json` is the LLM call facade**: All LLM calls go through `src/pipeline/llm._chat_json(system_prompt, user_content, max_tokens) → str | None` with JSON mode and temperature=0.
- **Frontend conventions**: Element Plus and ECharts are on-demand (unplugin-vue-components/AutoImport + `echarts/core` use()); `ElMessage` must be imported deep (`element-plus/es/components/message/index` + style/css) — the package entry pulls the full bundle. `endfield-theme.css`'s global `.el-button { background: transparent }` shorthand overrides EP CSS variables — override buttons with scoped longhand properties. Types in `src/types/index.ts` mirror backend JSON shapes (source category is English enum `tech_community`/`academic`/`chinese_media`; `collection_runs` uses `total_articles`/`source_stats`). **Agent 对话走 SSE 真流式（2026-08-28）**：`POST /api/agent/chat` 返回 `text/event-stream`（`tool`/`token`/`done`/`error` 事件）；前端 `api/agent.ts` 用 fetch + ReadableStream 增量解析（axios 无法消费 SSE），`stores/agent.ts` 实时渲染 token 并展示后端真实上报的工具标签；`mock/streamSimulator.ts` 与 `inferToolCalls` 已删除。对话归档 P2 仍在路由层：history 超阈值时最早部分压缩进 `conversation_summary`。

## Current project phase

Phases 0-4 complete; Phase 5 all three batches complete (quality + memory P1, source toggles + RSS, frontend integration + optimization). `user_profile.selected_sources` drives scheduler source selection (empty = all); `PUT /api/sources/{name}` toggles. Frontend live at `frontend/` (Vue 3 SPA, real API). **Agent 真流式（SSE）已完成（2026-08-28）**：后端 `chat_stream()` 事件流 + 路由 StreamingResponse，前端 fetch 增量读取删模拟器；工具事件真实上报、token 级流式输出（端到端验证：245 事件 = 2 tool + 242 token + 1 done，回答基于真实检索）。Note: 机器之心 official RSS is configured in `RSS_FEEDS` (free quota — frequent requests trigger 429 rate-limiting; scheduler's 6h interval is safe, avoid over-using `trigger_collection`). 知乎 needs login, public RSSHub instances are unreliable — additional Chinese sources require a self-hosted RSSHub appended to `RSS_FEEDS`. **第 6 源 CSDN（2026-09-06）**：`src/sources/csdn.py` 博客热榜 JSON 接口（数字字段字符串化需 `_to_int`，直连国内站）；**Docker 部署已完成（2026-09-06）**：单服务全栈（见上 Commands），backend/main.py 在存在 `frontend/dist` 时挂 StaticFiles 托管（Mount 注册在 /api 与 /、/health 之后）。Next candidates: GitHub Actions 自动日报, ranking v2, more Chinese sources.

## Test structure

Tests mirror the source tree under `tests/` — `tests/src/sources/test_hackernews.py` tests `src/sources/hackernews.py`, `tests/backend/routers/test_sources.py` tests `backend/routers/sources.py`. 230 total cases (222 unit + 8 integration) + 24 frontend Vitest.
