# AI Research Intelligence Platform

AI 圈热点新闻聚合与智能研究情报平台。

自动聚合多个渠道的 AI 热点内容（技术社区 + 学术论文），提供 CLI 终端输出和 Web API 双重访问模式，集成 AI Agent 实现智能搜索、摘要和趋势分析。

## 快速开始

```bash
# 安装依赖
uv sync

# CLI: 采集 AI 热点新闻
uv run python -m src.main fetch --limit 20

# CLI: 指定来源，输出到文件
uv run python -m src.main fetch -s arxiv,hackernews -o markdown -f daily.md

# 启动 Web API 后端（含 AI Agent）
uv run uvicorn backend.main:app --reload

# 前端（Vue 3 SPA，dev 代理 /api → 8000）
cd frontend && npm install
cd frontend && npm run dev        # http://localhost:5173
cd frontend && npm run typecheck
cd frontend && npm run build
```

访问 `http://127.0.0.1:8000/docs` 查看 Swagger API 文档；前端 `http://localhost:5173`。

## 数据源

| 来源 | 内容 | 接口 |
|------|------|------|
| Hacker News | AI 相关热门帖子与讨论 | Firebase API，免费免认证 |
| ArXiv | cs.AI / cs.CL / cs.CV / cs.LG 等 11 个分类新论文 | 官方 API，免费免认证 |
| HuggingFace Papers | 每日 AI 论文 + 代码实现 | Hugging Face API（`/api/papers`），免费免认证 |
| RSS 聚合 | 中文源聚合（RSS/Atom），当前含机器之心官方 RSS | `RSS_FEEDS` 配置（逗号分隔），免费额度限流 |
| GitHub Trending | 今日热门开源项目（今日新增 star 热度） | 静态页解析（无官方 API），需代理 |

## 项目结构

```
├── src/                     # 核心数据流水线（无 Web 感知）
│   ├── main.py              # CLI 入口（click 命令组）
│   ├── engine.py            # NewsEngine 调度编排（并发采集 + 去重 + 排序）
│   ├── models.py            # Article 数据模型
│   ├── filters.py           # AI 相关性关键词过滤（LLM 降级回退）
│   ├── output.py            # 输出格式化（text/json/markdown）
│   ├── pipeline/            # 流水线加工模块
│   │   ├── ranking.py       # 复合排序（时间衰减 + 源权重）
│   │   └── llm.py           # LLM 语义判断 + 质量打分（OpenAI 兼容端点）
│   └── sources/             # 数据源插件
│       ├── base.py           # SourcePlugin 抽象基类（含全局代理 PROXY_URL）
│       ├── hackernews.py     # Hacker News（Firebase，并发拉详情）
│       ├── arxiv.py          # ArXiv 论文采集
│       ├── papers.py         # HuggingFace Papers 采集
│       ├── rss.py            # 通用 RSS/Atom 聚合（中文源，RSS_FEEDS 配置）
│       └── github.py         # GitHub Trending（静态页解析，需代理）
├── backend/                  # FastAPI 后端 + AI Agent
│   ├── main.py              # FastAPI app（lifespan + CORS + 5 路由）
│   ├── database.py          # SQLite 数据层（3 表，WAL 模式）
│   ├── vector_store.py      # ChromaDB 向量索引（语义检索）
│   ├── scheduler.py         # APScheduler 定时采集
│   ├── routers/             # REST API 路由
│   │   ├── articles.py      # GET /api/articles
│   │   ├── sources.py       # GET /api/sources + PUT /api/sources/{name}
│   │   ├── stats.py         # GET /api/stats
│   │   ├── agent.py         # POST /api/agent/chat
│   │   └── collect.py       # POST /api/collect（手动采集）
│   └── agent/               # AI Agent（LLM + tool-use loop）
│       ├── core.py          # 主循环（最多 5 轮，并发执行工具）
│       ├── tools.py         # 工具集（search/summarize/analyze_trend）
│       └── prompts.py       # System prompt
├── frontend/                  # Vue 3 SPA（Vite + TS + Element Plus + ECharts）
│   └── src/
│       ├── api/             # axios 数据层（5 模块 + http 实例）
│       ├── stores/          # Pinia（articles/sources/agent，真实 API）
│       ├── views/           # 5 视图（热榜/文章/趋势/源管理/Agent 对话）
│       ├── components/      # 7 组件（ArticleCard/MessageBubble 等）
│       ├── composables/     # useTheme 双主题 + 图表色
│       └── styles/          # 双主题令牌（cyan 青 / yellow 分栏明暗）+ EP 覆写
├── tests/                    # 测试（174 用例，镜像 src/ + backend/）
├── pyproject.toml            # uv 项目配置
└── CLAUDE.md                 # Claude Code 项目指南
```

## 技术栈

| 组件 | 选型 |
|------|------|
| 语言 | Python ≥ 3.13 |
| 包管理 | uv |
| CLI | click |
| HTTP 异步 | httpx |
| 数据模型 | dataclasses |
| 终端输出 | rich |
| Web 框架 | FastAPI |
| ASGI 服务器 | uvicorn |
| 数据库 | SQLite（WAL 模式） |
| 向量存储 | ChromaDB + SentenceTransformer |
| LLM | OpenAI 兼容端点（默认 qwen-turbo / DashScope，可切 DeepSeek） |
| 定时任务 | APScheduler（AsyncIOScheduler） |
| 前端框架 | Vue 3 + Vite + TypeScript |
| UI 组件库 | Element Plus（按需引入） |
| 状态管理 | Pinia |
| 图表 | ECharts（按需注册） |
| HTTP 客户端 | axios（前端） |
| 测试 | pytest + pytest-asyncio |

## API 端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/articles` | GET | 查询最近 N 天文章 |
| `/api/sources` | GET | 列出数据源、文章数及启用状态 |
| `/api/sources/{name}` | PUT | 切换数据源开关 |
| `/api/stats` | GET | 采集运行统计 + 历史明细 |
| `/api/agent/chat` | POST | AI Agent 对话（RAG 搜索 + 摘要 + 趋势分析） |
| `/api/collect` | POST | 手动触发一次全量采集（202 后台执行） |
| `/health` | GET | 健康检查 |

## 测试

```bash
# 全部测试
uv run pytest

# 仅单元测试
uv run pytest -m unit

# 跳过网络依赖的集成测试
uv run pytest -m "not integration"

# 按关键字筛选
uv run pytest -k "dedup"
```

## Docker 部署（单服务全栈）

一条命令构建并启动（前端 dist + 后端 + 定时采集同一容器，单端口 8000）：

```bash
docker compose up -d --build
# 访问 http://localhost:8000（前端页面 + /api 同源）；停止: docker compose down
```

**前置**：Docker Desktop（Windows/Mac）；`cp .env.example .env` 并按本机填写。

**`.env` 需额外配置的两项**：

| 变量 | 说明 |
|------|------|
| `DOCKER_HTTPS_PROXY` | 墙内容器经宿主代理采集墙外源：`http://host.docker.internal:7890`（**宿主 Clash 需开启 Allow LAN**）；墙外部署留空 = 容器直连 |
| `HF_CACHE_DIR` | 嵌入模型缓存目录（复用本机缓存，如 `C:\Users\you\.cache\huggingface`）；留空 = 首次启动联网下载到 `./hf-cache` |

**卷**：`./backend/db`（SQLite + ChromaDB 数据持久化，与开发模式共用同一库）、模型缓存目录（只读挂载）。

**注意**：部署前先停本机开发服务（8000 端口冲突）；`docker compose up` 后容器内 APScheduler 每 6h 自动采集，采集数据写入宿主的 `backend/db`——开发模式（uv + vite）与 Docker 部署可随时切换共用数据。公网访问复用宿主 cpolar 穿透 8000 端口（`PUBLIC_BACKEND_URL`/`PUBLIC_FRONTEND_URL` 配置不变）。

## 配置

通过 `.env` 文件配置：

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `DASHSCOPE_API_KEY` | 阿里百炼 key（base_url 含 `dashscope` 时生效，qwen-turbo） | — |
| `DEEPSEEK_API_KEY` | DeepSeek key（base_url 不含 dashscope 时生效） | — |
| `LLM_MODEL_ID` | LLM 模型 ID | `qwen-turbo` |
| `LLM_BASE_URL` | LLM API 地址 | `https://dashscope.aliyuncs.com/compatible-mode/v1` |
| `LLM_TIMEOUT` | LLM 请求超时（秒） | `60` |
| `TAVILY_API_KEY` | Agent web_search 联网搜索 key（采集库外实时信息） | — |
| `HTTPS_PROXY` | 全局网络代理（墙外源 GitHub/HF 需要）；留空=直连；多设备各自维护 `.env`，改动后重启生效 | 空（直连） |
| `HF_HUB_OFFLINE` | 嵌入模型离线加载（模型缓存后置 1，避免访问 huggingface.co 卡重试） | `1` |
| `PUBLIC_BACKEND_URL` / `PUBLIC_FRONTEND_URL` | 内网穿透双隧道（cpolar）：后端 8000 隧道（前端 API 地址）/ 前端 5173 隧道（后端 CORS 放行 Origin）；留空=直连/局域网 | 空 |
| `DOCKER_HTTPS_PROXY` / `HF_CACHE_DIR` | Docker 部署专用（见上节） | 空 / `./hf-cache` |
| `SQLITE_PATH` | SQLite 数据库路径 | `backend/db/data.db` |
| `CHROMA_DIR` | ChromaDB 持久化目录 | `backend/db/chroma` |
| `RSS_FEEDS` | RSS 聚合源列表（逗号分隔），当前含机器之心官方 RSS（免费配额，频繁请求会 429 限流）；其余中文源可填自托管 RSSHub 路由 | 空（不启用） |
| `GITHUB_TOPICS` | GitHub topics 活跃榜主题（逗号分隔 slug） | `llm,machine-learning,agent` |
| `COLLECTION_LIMIT` | 每源采集条数 | `20` |
| `COLLECTION_HOURS` | 定时采集间隔（小时） | `6` |

完整配置模板见 `.env.example`（每台设备 `cp .env.example .env` 后按本机填写）。

## 后续计划

- [x] Docker 部署（2026-09-06：单服务全栈，见上节）
- [ ] GitHub Actions 自动采集日报（复用 CLI）
- [ ] 更多中文数据源（自托管 RSSHub 后填入 `RSS_FEEDS`）
- [ ] ranking v2（LLM 质量因子）
