# 项目 Bug

> 最后更新: 2026-08-20

---

## 已知问题

### 机器之心 RSS 免费额度 429 限流（已实现源头退避）

- **官方守则**: 每个凭证**最多每 60 分钟请求一次，每日最多 25 次**，单次最多返回最近 10 条；超限返回 429，限额恢复后可用
- **影响**: RSS 源采集返回空，其他源不受影响（优雅降级）；不是代码问题
- **应对**: ✅ **2026-08-20 已实现 60 分钟退避**（`RSSSource._backoff_active` + 模块级 `_last_request_ts`）——两次请求间隔 <60min 直接跳过不发请求，24h 自然 ≤24 次落在每日预算内；当前 429 为前期测试+采集叠加消耗的残留，配额重置后自动恢复

---

## 已修复

### #14 LLM 语义过滤输出截断（推理模型 max_tokens 不足）

- **状态**: 已修复
- **发现时间**: 2026-08-20（手动采集日志刷屏"LLM 判断输出无法解析"）
- **修复时间**: 2026-08-20
- **原因**: `llm._llm_is_ai_related`/`score_quality` 使用 `max_tokens=64`，但 `.env` 的 `deepseek-v4-flash` 是**推理模型**——响应先输出 `reasoning_content`（思考）再输出 JSON。实测单次简单调用消耗 33 推理 + 6 JSON tokens；复杂文章推理更长，64 tokens 预算被思考占满 → `content` 为空（`''`）或 JSON 截断（`'{"relevant":'`），批量采集时几乎每篇解析失败并刷警告日志
- **解决**: max_tokens 64 → 256（留足推理 + JSON 预算）；`_chat_json` 空串归一化为 None（推理超长时静默走关键词降级，不再刷日志）；实测长中文标题/摘要正确判定、零解析警告

### #13 视图切换 Tab 激活平行四边形未覆盖矩形背景（左上角露三角）

- **状态**: 已修复
- **发现时间**: 2026-08-20（yellow 主题验收）
- **修复时间**: 2026-08-20
- **原因**: `.aview__views` 为直角矩形容器（背景 `var(--input-bg)`），激活态是独立 `skewX(-10deg)` 平行四边形指示块 `.aview__views-indicator`——平行四边形几何上无法盖满矩形四角，左上角露出深色直角三角
- **解决**: yellow 主题下改为按钮自带斜切背景（选中亮黄填充+黑字 / 未选中深炭灰），三个按钮斜边互相咬合无缝，容器背景透明、隐藏独立指示块（`display:none`，JS 计算的 left/width 逻辑不受影响）；青色主题滑动指示动画不受影响（`[data-theme='yellow'] html` 前缀特异性 0,2,1 压制 scoped）

### #12 趋势页折线图空白（Y 轴有刻度但无线条）

- **状态**: 已修复
- **发现时间**: 2026-08-19（前端联调验收）
- **修复时间**: 2026-08-19
- **原因**: ECharts `category` 轴要求 series 数据对的 key 与 `xAxis.data` **逐字一致**才能定位坐标点。TrendsView 中 `xAxis.data`（trendChartDates）用 `M/D` 格式（如 `8/13`），而 series 内联生成的数据 key 用 `YYYY-MM-DD`（如 `2026-08-13`）→ 所有数据点被静默丢弃，折线/散点/面积全部不绘制（Y 轴仍按丢弃前的数据 max 显示刻度，造成"有刻度无数据"的假象）
- **解决**: series 的日期 key 与筛选匹配 key 统一改为 `M/D` 格式，与 trendChartDates 输出一致；SQLite 实证 165 篇文章均在窗口内，数据层无问题

### #11 输入框纯白背景穿透（EP 变量默认值 vs 主题覆盖层叠失败）

- **状态**: 已修复
- **发现时间**: 2026-08-19（前端联调验收）
- **修复时间**: 2026-08-19
- **原因**: Element Plus 2.8 输入控件背景使用 `var(--el-input-bg-color, var(--el-fill-color-blank))`，默认值为白色 `#fff`；`endfield-theme.css` 的覆盖选择器（如 `.el-input__wrapper`）特异性 `(0,1,0)` 与 EP 默认规则相同，而 EP 组件样式由 unplugin-vue-components 按需注入、晚于 main.ts 静态 import → 同特异性后加载者胜 → **白色背景穿透**（顶栏搜索框 / 筛选框 / Agent 提问框全部纯白）
- **解决**: 三处加固——① `main.ts` 将 `endfield-theme.css` 改为动态导入（`import(...).then(mount)`，保证晚于 EP 组件样式注入）② 输入/下拉/弹层/消息等 51 处选择器加 `html` 前缀提特异性至 `(0,1,1)`（仍低于 yellow 主题 `[data-theme='yellow']` 的 0,2,0，不破坏黄色主题）③ `:root` 新增 46 条 EP CSS 变量映射兜底（`--el-input-bg-color`/`--el-fill-color-blank`/`--el-border-color` 等 → 项目令牌），双保险覆盖

### #10 趋势页图表从未渲染（v-chart 未注册）

- **状态**: 已修复
- **发现时间**: 2026-08-19（前端优化验收）
- **修复时间**: 2026-08-19
- **原因**: TrendsView 使用 `<v-chart>`（vue-echarts）但组件从未在任何位置注册（main.ts 无 `app.component('VChart', ...)`，组件内也无局部引入）；vue-tsc 不校验模板组件名，typecheck 通过但运行时 Vue 将 `<v-chart>` 当原生元素渲染为空
- **解决**: `main.ts` 全局注册 `app.component('VChart', VChart)` + `import '@/utils/echarts'`（按需注册）

### #9 采集按钮描边半成品（全局 .el-button 简写覆盖 EP 变量）

- **状态**: 已修复
- **发现时间**: 2026-08-19（yellow 主题验收）
- **修复时间**: 2026-08-19
- **原因**: `endfield-theme.css` 全局 `.el-button { background: transparent }`（简写）以同级特异性、后导入顺序覆盖 Element Plus 变量驱动的 `background-color`；scoped 里只设 `--el-button-bg-color` 变量不生效，只有长写 `border-color` 生效 → 按钮呈现"黄边框 + 透明底"，hover 时命中全局 `background: var(--surface-hover)`
- **解决**: scoped 样式直接写长写属性（`background-color`/`border-color`/`color`，特异性 0,3,0 全面压制全局规则），CSS 变量保留作双保险

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
