
from dataclasses import dataclass
from datetime import datetime


@dataclass
class Article:
    """
    统一新闻格式/论文数据格式

    id: 唯一标识 (source:source_id)
    title: 标题
    url: 原文链接
    source: 来源名称 (hackernews / arxiv / huggingface_papers)
    summary: 摘要 / 简介
    author: 作者
    published_at: 发布时间
    score: 热度分数 (点赞数 / 引用数)
    tags: 标签 (AI / LLM / CV / NLP ...)
    language: 语言 (en / zh)
    """
    id: str                    # 唯一标识
    title: str                 
    url: str                   
    source: str                 
    summary: str | None        
    author: str | None         
    published_at: datetime | None  
    score: int                  
    tags: list[str]             
    language: str              
