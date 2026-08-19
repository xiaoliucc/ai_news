# 项目 Bug

> 最后更新: 2026-08-18

---

## 已知问题

### 机器之心 RSS 免费额度 429 限流

- **现象**: 频繁请求 `https://mcp.applications.jiqizhixin.com/rss?token=...` 返回 429 Too Many Requests（首个请求 200，随后被限流）
- **影响**: RSS 源采集返回空，其他源不受影响（优雅降级）；不是代码问题
- **应对**: scheduler 默认 6h 间隔（每天 4 次请求）应合规；避免频繁调用 `trigger_collection`；配额窗口恢复后自动可用

---

## 已修复

### #8 set_profile 直接调用时行不存在静默失败

- **状态**: 已修复
- **发现时间**: 2026-08-17（第 2 批测试暴露）
- **修复时间**: 2026-08-17
- **原因**: `set_profile()` 直接执行 `UPDATE user_profile SET ... WHERE id=1`，若从未调用过 `get_profile()`（其内部有 `INSERT OR IGNORE` 建行），UPDATE 影响 0 行静默失败，写入不生效
- **解决**: `set_profile()` 在 UPDATE 前加 `INSERT OR IGNORE` 确保单行存在

### #7 健壮性评审 11 项问题（H1-H4 / M1-M7）

- **状态**: 已修复
- **发现时间**: 2026-08-17（外部 AI 评审报告）
- **修复时间**: 2026-08-17
- **H1 数据库文件未 git 忽略**: `.gitignore` 只有 `data/`，实际库在 `backend/db/`（check-ignore 实证未忽略）→ 增加 `backend/db/` + `*.db*`
- **H2 多 key 配置丢失 base_url**: `kwargs = {"api_key": ...}` 整体替换 → 改为 `kwargs["api_key"] = ...` 只覆盖单字段
- **H3 LLM 客户端失败永不恢复**: 构建失败也缓存 `_client_loaded=True` → 失败不缓存，下次重试
- **H4 采集无并发锁**: 定时任务与 trigger_collection 可并发 → `asyncio.Lock`
- **M1 print 污染 stdout**: 3 个源文件 6 处 → 全部改 `logger.warning`
- **M3 docstring 与签名不符**: save_articles 写了不存在的参数；get_profile/set_profile 缺 docstring → 修复
- **M4 路由参数无边界校验**: articles.py days/limit 可传负数 → `Query(ge=1, le=365/200)`
- **M5 ChromaDB 挂掉无回退**: 检索空结果 → `_keyword_fallback()` SQLite 关键词回退
- **M6 对话历史无限制**: → ChatRequest 三重限制（20 轮 / 20000 字符 / message 4000）
- **M7 风格瑕疵**: config.py 缺空格、vector_store.py 多余缩进 → 修复

### #6 ChromaDB `$gte` 运算符不支持 ISO 字符串

- **状态**: 已修复
- **发现时间**: 2026-08-11
- **修复时间**: 2026-08-11
- **原因**: `vector_store._metadata()` 将 `published_at` 存为 ISO 字符串（如 `"2026-08-04T10:00:43+00:00"`），但 ChromaDB where 的 `$gte` 运算符要求数字类型，导致语义检索时间过滤报错
- **解决**: `_metadata()` 改为存 Unix 时间戳（`datetime.timestamp()`），`search()` 中 cutoff 也改为时间戳比较，返回时 `fromtimestamp()` 转回 ISO 字符串

### #5 Agent 搜索不返回摘要

- **状态**: 已修复
- **发现时间**: 2026-08-11
- **修复时间**: 2026-08-11
- **原因**: `_search_articles` 中 `summary` 字段硬编码为 `""`，LLM 只能看标题做判断，回答空洞
- **解决**: ChromaDB 搜到 ID 后去 SQLite 回填摘要（`db_get_article(h["id"])`），截取前 300 字符

### #4 未知数据源静默 return（退出码 0）

- **状态**: 已修复
- **发现时间**: 2026-08-02
- **修复时间**: 2026-08-02
- **原因**: `main.py` 遇到未知数据源时 `print` 错误后 `return`，进程退出码为 0，脚本化/CI 调用时被误判为成功
- **解决**: 改为 `raise click.ClickException(f"未知数据源: {name}")`，退出码 1，错误信息输出到 stderr

### #1 uv sync 清华镜像 403

- **状态**: 已修复
- **发现时间**: 2026-07-30
- **修复时间**: 2026-07-30
- **原因**: 系统环境变量 `UV_DEFAULT_INDEX` 指向 `https://pypi.tuna.tsinghua.edu.cn/simple/`，优先级高于 `pyproject.toml` 配置
- **解决**: 在 `pyproject.toml` 中配置 `[[tool.uv.index]]` 指向 `https://mirrors.aliyun.com/pypi/simple/`，终端中执行 `$env:UV_DEFAULT_INDEX = "https://mirrors.aliyun.com/pypi/simple/"` 覆盖系统变量

### #2 Papers With Code 官方 API 失效

- **状态**: 已修复
- **发现时间**: 2026-08-01
- **修复时间**: 2026-08-01
- **原因**: Papers With Code 已被 Hugging Face 收购，原 `paperswithcode.com/api/v1/papers/` 端点 302 跳转到 huggingface.co，接口失效
- **解决**: 改用 Hugging Face 官方 API `https://huggingface.co/api/papers`，参数 `limit` 控制返回条数；实现 `HuggingFacePaperSource`（源名 `huggingface_papers`）

### #3 CLI 报错 `Got unexpected extra argument (fetch)`

- **状态**: 已修复
- **发现时间**: 2026-08-01
- **修复时间**: 2026-08-01
- **原因**: `main.py` 把 `fetch` 实现成顶层单命令，而文档/计划按子命令用法（`python -m src.main fetch`）调用，`fetch` 被当作多余位置参数
- **解决**: 改为 click 命令组 `cli`，`fetch` 注册为子命令；`__main__` 与 pyproject.toml entry point（`ai-news = "src.main:cli"`）同步更新
