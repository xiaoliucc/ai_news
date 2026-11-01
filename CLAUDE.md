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

1. **Source plugins** (`src/sources/`) inherit from `SourcePlugin` (abstract `async fetch(limit) → list[Article]`). Six sources: HackerNews (Firebase API), ArXiv (official library), HuggingFace Papers (`/api/papers`), RSS (`rss.py`, a configurable RSS/Atom aggregator driven by `RSS_FEEDS`, used for Chinese sources), GitHub (`github.py`, parses the static `github.com/trending` + `github.com/explore` + AI topic pages (`/topics/{t}?o=desc&s=updated`, `.env` `GITHUB_TOPICS`) with BeautifulSoup — no official API; trending score = stars today, explore 推荐仓库与 topics 活跃仓库 score=0 避免量纲混用，页面按仓库 id 合并去重 trending 优先; explore/topics 的 `published_at` 分别取采集时刻与行内 `relative-time` 真实活跃时间), and CSDN (`csdn.py`, 解析博客热榜 JSON 接口 `phoenix/web/blog/hot-rank` — 无公开文档但结构稳定; 数字字段为字符串需 `_to_int`; score=viewCount; **直连国内站：AsyncClient 显式 `trust_env=False` 禁读环境代理**（2026-09-06 修复——httpx 默认 trust_env=True 会劫持 Docker 墙内注入的 HTTPS_PROXY 导致采集失败，见 csdn.py 注释 + test_csdn 回归)). All httpx-based sources honor the global proxy: `.env` `HTTPS_PROXY` (empty = direct; system env var takes precedence over `.env` since `load_dotenv` doesn't override). CLI (`src/main.py`) keeps the original three; the scheduler registers all six via `SOURCE_REGISTRY`.

2. **NewsEngine.run()** concurrently calls all registered sources via `asyncio.gather`, tolerates individual source failures, then runs **cross-source dedup** (arxiv ID fingerprint matching across arxiv ↔ pwc ↔ HN) and **composite ranking** (`pipeline/ranking.py` v2: `normalized_score × time_decay (48h half-life) × source_weight × quality_factor`, quality_factor = 0.7 + 0.3×quality/100, None 回退 1.0).

3. **Output**: In CLI mode, results pass through `filters.py` (keyword-based AI relevance gate) then to formatters (text/json/markdown). In backend mode, results go to `backend/database.py` (SQLite, WAL mode).

### AI Agent (`backend/agent/`)

A **tool-use loop** (not LangChain) built directly on the OpenAI-compatible SDK:

- `core.py` — main loop: system prompt → LLM call with tools → execute tool calls concurrently → repeat (max 5 turns). **只有一套循环：`chat_stream()`（2026-11-01 合并）**——非流式的 `chat()` 已删除（SSE 上线后生产无调用方，两套逻辑会各自漂移）。`reading_history`（阅读历史标题）与 `conversation_summary` 由 `_build_messages()` 注入 system prompt，避免重复推荐；LLM 调用 `stream=True`，工具轮发 `tool start/done` 事件（真实上报），答案轮 token 逐块 yield；同步流式 chunk 经线程+队列桥接（`_iter_chunks`）避免阻塞事件循环。路由 `/api/agent/chat` 返回 `text/event-stream`。想拿完整字符串就 `async for` 收事件取最后一个 `done`。
- `tools.py` — 6 tools all implemented: search_articles (ChromaDB semantic search with SQLite summary backfill; falls back to SQLite keyword search `_keyword_fallback` when ChromaDB returns empty; **exact-match shortcut**: space-less proper-noun queries like repo paths resolve via `_resolve_article` first), get_article_detail (SQLite; **`_resolve_article` falls back to exact-title match when the LLM passes a title instead of an ID**), summarize_articles (LLM), analyze_trend (semantic search + LLM hotspot detection), trigger_collection (scheduler.collect_once), **web_search (Tavily 联网搜索，2026-09-06)** — 采集库外的实时/最新信息；请求走全局代理（`backend.config.PROXY_URL`），key 读 `.env` `TAVILY_API_KEY`（config.TAVILY_API_KEY），未配置/网络失败返回可读 error 不中断对话；纯函数 `_parse_search_results` 过滤脏条目 + content 截断 500 字。get_article_detail/summarize_articles implicitly record read article IDs into `user_profile.reading_history` via `_record_reading_history` (dedup, newest-first, cap 50).
- `prompts.py` — system prompt with date anchor, data boundary rules, user preference injection

### Vector store (`backend/vector_store.py`)

ChromaDB with `PersistentClient` and SentenceTransformer embeddings (`paraphrase-multilingual-MiniLM-L12-v2`, 384-dim). Public API: `add_articles()`, `search()` (semantic with optional source/days filter using Unix timestamp metadata), `clear()`, `delete_article()`. Thread-safe lazy init via double-checked locking. `_get_embedding_fn()` lazily initializes the embedding function to avoid blocking on import. Index is maintained by the scheduler at collection time — Agent reads directly, no per-request rebuild.

### LLM integration (`src/pipeline/llm.py`)

LLM is accessed via **OpenAI-compatible endpoint** (default `deepseek-chat` since 2026-10-29; `qwen-turbo` was decommissioned — on DashScope see `qwen3.8-flash` + `enable_thinking=false`, configurable via `.env`). `_build_client()` auto-selects the API key by base_url: DashScope → `DASHSCOPE_API_KEY`, otherwise → `DEEPSEEK_API_KEY` (optional `OPENAI_API_KEY` override). Key design: **graceful degradation** — when the LLM is unavailable, AI relevance judgment falls back to keyword matching (`filters.py`), and quality scoring returns `None`. `_chat_json` retries transient errors (connection/timeout/5xx/429) with exponential backoff.

### Database (`backend/database.py`)

Three SQLite tables: `articles` (INSERT OR REPLACE by id), `collection_runs` (logs each collection), `user_profile` (single-row, interests/reading_history/language). JSON columns (tags, interests) are serialized as strings and deserialized on read. Two aggregate queries: `get_source_stats()` (GROUP BY source), `get_collection_stats()` (total runs/articles + recent runs with parsed source_stats). Auto-init on import.

### Scheduler (`backend/scheduler.py`)

APScheduler `AsyncIOScheduler` with interval job. `start()` is idempotent — fires an immediate collection on startup via `asyncio.ensure_future`, then repeats every `COLLECTION_HOURS` (default 6h, from `.env`). `collect_once()` pipeline: instantiate sources per `user_profile.selected_sources` (empty = all, via `SOURCE_REGISTRY`) → engine.run() → `_filter_ai_related()` (LLM semantic AI-relevance filter, 4-thread concurrent, falls back to keyword matching when LLM unavailable) → save_articles (SQLite) → add_articles (ChromaDB). `_collect_lock` (asyncio.Lock) prevents concurrent collection. Source toggles via `PUT /api/sources/{name}` only affect the scheduler (CLI unaffected). Manual trigger: `POST /api/collect` (202 + background task) and the Agent's `trigger_collection` tool both call `collect_once()`.

## Key conventions

- **Tests mirror source structure**: `tests/src/test_engine.py` tests `src/engine.py`; `tests/backend/agent/test_agent.py` tests `backend/agent/core.py`. pytest config in `pyproject.toml` uses markers `unit`, `integration`, `slow`.
- **Config via `.env`**: `SQLITE_PATH`, `CHROMA_DIR`, `COLLECTION_LIMIT`, `COLLECTION_HOURS`, `RSS_FEEDS`, `DASHSCOPE_API_KEY`, `DEEPSEEK_API_KEY`, `LLM_MODEL_ID`, `LLM_BASE_URL`, `LLM_TIMEOUT`, `HTTPS_PROXY` (global proxy for walled-off sources like GitHub/HF; empty = direct; multi-device: each device keeps its own `.env`; restart to apply). **可选 API 门禁 Token（2026-09-06）**: `API_TOKEN`（留空 = 关闭门禁）——部署者自备 token（`python -c "import secrets;print(secrets.token_urlsafe(32))"` 生成）；backend/main.py 的 `require_api_token` HTTP 中间件对 `/api/*`（除 OPTIONS 预检）校验请求头 `X-API-Token`，不匹配返回 401；`/`、`/health`、前端静态资源豁免。单用户自部署语义：公网暴露时挡互联网扫描器（防 RSS 配额/LLM 花费被耗尽），非多用户鉴权。前端构建时 vite.config 把根 `.env` 同一 `API_TOKEN` 注入 `VITE_API_TOKEN`，axios 拦截器与 agent SSE fetch 自动带头（token 进前端 bundle 在单用户威胁模型下可接受）。**内网穿透（cpolar 双隧道，2026-08-28）**: `PUBLIC_BACKEND_URL`（后端 :8000 隧道 → 前端注入 `VITE_API_BASE` 并拼 `/api` 作为 API 地址）、`PUBLIC_FRONTEND_URL`（前端 :5173 隧道 → 后端 CORS 放行该 Origin）；留空 = 直连/局域网。前端构建时 vite.config `loadEnv` 读根 `.env` 注入；`server.allowedHosts` 动态放行 `.cpolar.top` 通配域 + 配置的隧道域名（Vite DNS-rebinding 防护默认拒外部域名），`server.host` 显式 `127.0.0.1`（Vite 默认只绑 IPv6 `[::1]`，cpolar 转发目标是 IPv4）。`.env.example` is the committed template.
- **速率限制（2026-11-01）**：`backend/ratelimit.py` 的 `SlidingWindowLimiter`（线程安全内存滑动窗口，时钟可注入便于测试）+ `backend/main.py` 的 `rate_limit_requests` 中间件，只保护**会花钱**的 `POST /api/collect`（默认 3 次/10 分钟/客户端）与 `POST /api/agent/chat`（20 次），其余接口不限。额度与开关走 `.env`（`RATE_LIMIT_ENABLED` / `RATE_LIMIT_WINDOW` / `RATE_LIMIT_CHAT` / `RATE_LIMIT_COLLECT`，写 0 = 不限）；超限返回 429 + `Retry-After` + 中文 detail。**中间件注册顺序即洋葱模型**：`add_middleware` 往栈顶插，越后添加越靠外——门禁在限流之后注册（外层，401 不耗配额），CORS 最后注册（最外层，401/429 也带 `Access-Control-*`）。客户端标识优先取 `X-Forwarded-For` 首跳（隧道后 `client.host` 全是 127.0.0.1）。单进程计数，多 worker 部署额度按 worker 数放大。
- **文档与日志隐私（2026-11-01）**：`ENABLE_DOCS` **默认关**——不暴露 `/docs`、`/redoc`、`/openapi.json`（公网部署时接口清单等于送参数结构给扫描器），本地调试设 `1` 打开；`LOG_FULL_MESSAGE` **默认关**——`routers/agent.py` 只记提问长度 + 前 20 字符（SSE 的 token 事件降到 DEBUG，只有 tool/done/error 记 INFO）。安全响应头由 `main.py` 的 `add_security_headers` 中间件统一加（`X-Content-Type-Options: nosniff` / `X-Frame-Options: DENY` / `Referrer-Policy: no-referrer` / `Permissions-Policy`），注册在 CORS 之后 ⇒ 位于最外层，401/429/静态文件也带；**故意不设 CSP**：Vite 产物与 ECharts 依赖内联样式，CSP 要按部署域逐条配，配错就是白屏，XSS 面已由 DOMPurify 白名单堵住（见 main.py 注释与 `tests/backend/test_security.py`）。
- **Docstrings are Google style**: `Args:` / `Returns:` / `Raises:` sections.
- **Logging, not print**: Use `logging` (stderr) for diagnostics; stdout is reserved for CLI output that may be piped.
- **`_chat_json` is the LLM call facade**: All LLM calls go through `src/pipeline/llm._chat_json(system_prompt, user_content, max_tokens) → str | None` with JSON mode and temperature=0.
- **Frontend conventions**: Element Plus and ECharts are on-demand (unplugin-vue-components/AutoImport + `echarts/core` use()); `ElMessage` must be imported deep (`element-plus/es/components/message/index` + style/css) — the package entry pulls the full bundle. `endfield-theme.css`'s global `.el-button { background: transparent }` shorthand overrides EP CSS variables — override buttons with scoped longhand properties. Types in `src/types/index.ts` mirror backend JSON shapes (source category is English enum `tech_community`/`academic`/`chinese_media`; `collection_runs` uses `total_articles`/`source_stats`). **Agent 对话走 SSE 真流式（2026-08-28）**：`POST /api/agent/chat` 返回 `text/event-stream`（`tool`/`token`/`done`/`error` 事件）；前端 `api/agent.ts` 用 fetch + ReadableStream 增量解析（axios 无法消费 SSE），`stores/agent.ts` 实时渲染 token 并展示后端真实上报的工具标签；`mock/streamSimulator.ts` 与 `inferToolCalls` 已删除。对话归档 P2 仍在路由层：history 超阈值时最早部分压缩进 `conversation_summary`。 **筛选口径（2026-11-01）**：`stores/articles.ts` 的 `days/sources` 只由后端过滤，`filteredArticles` 只做 search/sort；`setFilter` 显式判断是否重拉（`watch` 已删，直接写 store 字段不重拉，组件必须走 `setFilter`）。Agent 的初始文案/快捷操作/上限常量在 `constants/chat.ts`（原 `mock/data.ts` 已删，生产代码不再 import `mock/`）。
- **提交与推送（2026-11-01）**：`.github/workflows/daily-report.yml` 每天自动提交 `reports/daily-*.md`，本地必然落后于 origin ⇒ push 前必须先 rebase。已封装成一条命令 **`git sync`**（= `git pull --rebase` + `git push`），并设了 `pull.rebase=true` / `rebase.autoStash=true`（有未提交改动也能直接跑，不会产生 merge 提交）。新机器 clone 后补一次：`git config pull.rebase true && git config rebase.autoStash true && git config alias.sync "!git pull --rebase && git push"`。若 rebase 冲突：改完文件 `git add` + `git rebase --continue`，再跑 `git sync` 即可。本地/远端只差 `reports/` 的常规情况不会冲突，因为 Actions 只新增该目录。

## Current project phase

Phases 0-4 complete; Phase 5 all three batches complete (quality + memory P1, source toggles + RSS, frontend integration + optimization). `user_profile.selected_sources` drives scheduler source selection (empty = all); `PUT /api/sources/{name}` toggles. Frontend live at `frontend/` (Vue 3 SPA, real API). **Agent 真流式（SSE）已完成（2026-08-28）**：后端 `chat_stream()` 事件流 + 路由 StreamingResponse，前端 fetch 增量读取删模拟器；工具事件真实上报、token 级流式输出（端到端验证：245 事件 = 2 tool + 242 token + 1 done，回答基于真实检索）。Note: 机器之心 official RSS is configured in `RSS_FEEDS` (free quota — frequent requests trigger 429 rate-limiting; scheduler's 6h interval is safe, avoid over-using `trigger_collection`). 知乎 needs login, public RSSHub instances are unreliable — additional Chinese sources require a self-hosted RSSHub appended to `RSS_FEEDS`. **第 6 源 CSDN（2026-09-06）**：`src/sources/csdn.py` 博客热榜 JSON 接口（数字字段字符串化需 `_to_int`；直连国内站——2026-09-06 补 `trust_env=False` 修复 Docker 墙内环境代理劫持导致采集失败）；**Docker 部署已完成（2026-09-06）**：单服务全栈（见上 Commands），backend/main.py 在存在 `frontend/dist` 时挂 StaticFiles 托管（Mount 注册在 /api 与 /、/health 之后）。**ranking v2 + Actions 日报（2026-09-06）**：`llm.judge_article()` 单次 LLM 调用合并返回（相关, 质量分）——scheduler 过滤时同步评分写入 `Article.quality`/articles.quality 列（`_migrate_articles_quality` 迁移），前端卡片显示 Q 质量徽章；`.github/workflows/daily-report.yml` 每日自动日报。**可选 API 门禁 Token（2026-09-06）**：`API_TOKEN` + `X-API-Token` 中间件（详见 Key conventions），留空即完全关闭、零侵入；全端到端验证 401/401/200 + `/health` 200。Next candidates: more Chinese sources, 云服务器迁移.

## Test structure

Tests mirror the source tree under `tests/` — `tests/src/sources/test_hackernews.py` tests `src/sources/hackernews.py`, `tests/backend/routers/test_sources.py` tests `backend/routers/sources.py`, `tests/backend/test_auth.py` tests the optional API_TOKEN gate (monkeypatches `backend.main.API_TOKEN`). 284 total cases (276 unit + 8 integration) + 35 frontend Vitest (含组件测试；涉及 DOMPurify 的用例用 `// @vitest-environment jsdom`；`test_security.py` 覆盖 docs 开关与 200/401/429 三类响应的安全头).
