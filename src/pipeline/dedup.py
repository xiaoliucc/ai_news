"""
去重模块（预留）— 从 engine.py 移出 arxiv ID 指纹提取与去重逻辑。

计划对外接口：
    deduplicate(articles: list[Article]) -> list[Article]

从 engine.py 移出的内容：
    _strip_arxiv_version()
    _extract_arxiv_id()
    _dedup_key()
    NewsEngine._deduplicate()

说明：本文件当前为骨架，仅规划职责，实现代码在后续阶段从 engine.py 迁移。
"""
