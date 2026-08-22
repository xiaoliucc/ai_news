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
│       ├── base.py           # SourcePlugin 抽象基类
│       ├── hackernews.py     # Hacker News（Firebase，并发拉详情）
│       ├── arxiv.py          # ArXiv 论文采集
│       ├── papers.py         # HuggingFace Papers 采集
│       └── rss.py            # 通用 RSS/Atom 聚合（中文源，RSS_FEEDS 配置）
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
| LLM | OpenAI 兼容端点（默认 DeepSeek v4-flash） |
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

## 配置

通过 `.env` 文件配置：

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `DEEPSEEK_API_KEY` | LLM API 密钥 | — |
| `LLM_MODEL_ID` | LLM 模型 ID | `deepseek-chat` |
| `LLM_BASE_URL` | LLM API 地址 | `https://api.deepseek.com/v1` |
| `LLM_TIMEOUT` | LLM 请求超时（秒） | `60` |
| `SQLITE_PATH` | SQLite 数据库路径 | `backend/db/articles.db` |
| `CHROMA_DIR` | ChromaDB 持久化目录 | `backend/db/chroma` |
| `RSS_FEEDS` | RSS 聚合源列表（逗号分隔），当前含机器之心官方 RSS（免费配额，频繁请求会 429 限流）；其余中文源可填自托管 RSSHub 路由 | 空（不启用） |
| `COLLECTION_LIMIT` | 每源采集条数 | `20` |
| `COLLECTION_HOURS` | 定时采集间隔（小时） | `6` |

## 后续计划

- [ ] 部署方案（Docker 编排 / GitHub Actions 自动采集日报）
- [ ] 更多中文数据源（自托管 RSSHub 后填入 `RSS_FEEDS`）
- [ ] Agent 对话真流式（SSE）改造（后期）：当前为非流式（后端整段返回，前端本地逐字重放模拟流式）；改造为后端 `StreamingResponse` 逐步推送 token 与工具事件，降低首 token 延迟并展示真实工具进度
