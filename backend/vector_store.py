from datetime import datetime, timedelta, timezone
import logging
import threading

from chromadb.utils import embedding_functions

from backend.config import CHROMA_DIR
from src.models import Article

logger = logging.getLogger(__name__)

COLLECTION_NAME = "articles"
_embedding_fn = None
_embedding_failed = False  # 失败哨兵：初始化失败后不再重试下载


def _get_embedding_fn():
    """惰性初始化 SentenceTransformer 嵌入函数。

    初始化失败后缓存失败状态（_embedding_failed），后续调用直接返回
    None，避免每次都触发网络重试阻塞调用方。

    Returns:
        SentenceTransformerEmbeddingFunction | None: 嵌入函数实例，初始化失败则 None。
    """
    global _embedding_fn, _embedding_failed
    if _embedding_fn is not None:
        return _embedding_fn
    if _embedding_failed:
        return None
    try:
        _embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name="paraphrase-multilingual-MiniLM-L12-v2"
        )
    except Exception as e:
        logger.warning("SentenceTransformer 初始化失败: %s", e)
        _embedding_failed = True
        return None
    return _embedding_fn
try:
    from chromadb import PersistentClient
except ImportError:
    PersistentClient = None
 
_collection = None 
_collection_lock = threading.Lock()

def _get_collection():
    """获取或创建 ChromaDB 持久化 collection（双重检查锁定惰性初始化）。

    首次调用时在 CHROMA_DIR 下创建 PersistentClient，获取或新建 collection
    并绑定 SentenceTransformer 嵌入函数。后续调用返回缓存的全局 instance。
    chromadb 未安装或初始化失败时返回 None，调用方应优雅降级。

    Returns:
        chromadb.Collection | None: collection 实例，不可用时返回 None。
    """
    global _collection
    if _collection is not None:
        return _collection
    with _collection_lock:
        if _collection is not None:
            return _collection
        if PersistentClient is None:
            logger.warning("chromadb 未安装，向量检索不可用")
            return None
        try:
            CHROMA_DIR.mkdir(parents=True, exist_ok=True)
            client = PersistentClient(path=str(CHROMA_DIR))
            ef = _get_embedding_fn()
            if ef is None:
                logger.warning("嵌入函数不可用，向量检索功能降级")
                return None
            _collection = client.get_or_create_collection(
                name=COLLECTION_NAME,
                embedding_function=ef,
            )
        except Exception as e:
            logger.warning("ChromaDB 初始化失败: %s", e)
            return None
        return _collection

def _document(article: Article) -> str:
    """构建用于向量化的文本（标题 + 摘要 + 标签）。

    Args:
        article: 待处理的文章对象。

    Returns:
        str: 拼接后的纯文本，用换行分隔。
    """
    parts = [article.title]
    if article.summary:
        parts.append(article.summary)
    if article.tags:
        parts.append(" ".join(article.tags))
    return "\n".join(parts)

def _metadata(article: Article) -> dict:
    """构建 ChromaDB metadata（不参与向量检索但随结果返回）。

    Args:
        article: 待处理的文章对象。

    Returns:
        dict: 含 title / source / score / published_at / url 的字典。
    """
    return {
        "title": article.title,
        "source": article.source,
        "score": article.score,
        "published_at": article.published_at.timestamp() if article.published_at else 0.0,
        "url": article.url,
    }

def add_articles(articles: list[Article]) -> int:
    """将文章批量写入向量库（upsert 语义，同 ID 覆盖）。

    先调用 _get_collection() 惰性初始化，再按 ids / documents / metadatas
    三列批量 upsert。collection 不可用或无数据时返回 0。

    Args:
        articles: 待写入的 Article 列表。

    Returns:
        int: 成功写入的条数。
    """
    collection = _get_collection()
    if collection is None or not articles:
        return 0
    try:
        collection.upsert(
            ids=[a.id for a in articles],
            documents=[_document(a) for a in articles],
            metadatas=[_metadata(a) for a in articles],
        )
        return len(articles)
    except Exception as e:
        logger.warning("向量索引写入失败: %s", e)
        return 0

def delete_article(article_id: str) -> None:
    """从向量库中删除单篇文章。

    collection 不可用时静默返回，不抛异常。

    Args:
        article_id: 文章 ID（与 add_articles 时使用的 id 一致）。
    """
    collection = _get_collection()
    if collection is None:
        return 
    try:
        collection.delete(ids=[article_id])
    except Exception as e:
        logger.warning("删除向量失败 %s: %s", article_id, e)

def search(
        query: str,
        limit: int = 10,
        source: str | None = None,
        days: int | None = None,
) -> list[dict]:
    """语义检索文章，按余弦相似度降序返回。

    支持按 source 和时间范围过滤（ChromaDB where 条件）。
    collection 不可用或 query 为空时返回空列表。

    Args:
        query: 自然语言查询（如"多模态论文"）。
        limit: 最多返回条数，默认 10。
        source: 可选，按来源过滤（如 "arxiv"）。
        days: 可选，按 published_at 过滤最近 N 天。

    Returns:
        list[dict]: 匹配文章列表，每项含 id / title / source / score / url /
            published_at / distance。
    """
    collection = _get_collection()
    if collection is None or not query.strip():
        return []
    where=None
    filters = []
    if source:
        filters.append({"source":source})
    if days is not None:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).timestamp()
        filters.append({"published_at": {"$gte": cutoff}})
    if len(filters) == 1:
        where = filters[0]
    elif len(filters) > 1:
        where = {"$and" : filters}
    try:
        result = collection.query(
            query_texts=[query.strip()],
            n_results=limit,
            where=where
        )
    except Exception as e:
        logger.warning('向量检索失败:%s', e)
        return []
    ids = result.get("ids",[[]])[0]
    metadatas = result.get("metadatas", [[]])[0]
    distances = result.get("distances", [[]])[0]
    hits = []
    for i, article_id in enumerate(ids):
        meta = metadatas[i] if i < len(metadatas) else {}
        pub_ts = meta.get("published_at")
        published_at = (
            datetime.fromtimestamp(pub_ts, tz=timezone.utc).isoformat()
            if pub_ts else None
        )
        hits.append({
            "id": article_id,
            "title": meta.get("title"),
            "source": meta.get("source"),
            "score": meta.get("score", 0),
            "published_at": published_at,
            "url": meta.get("url"),
            "distance": distances[i] if i < len(distances) else None,
        })
    return hits

def clear() -> int:
    """清空集合内所有向量，返回删除条数。"""
    collection = _get_collection()
    if collection is None:
        return 0
    try:
        ids = collection.get().get("ids", [])
        if ids:
            collection.delete(ids=ids)
        return len(ids)
    except Exception as exc:
        logger.warning("清空向量失败: %s", exc)
        return 0
    
def _reset() -> None:
    """清空全局 collection 缓存，下次 _get_collection() 会重新初始化。

    同时重置嵌入函数失败哨兵，允许下次重新尝试初始化。
    主要用于测试 teardown，避免持久化数据在用例间泄漏。
    """
    global _collection, _embedding_failed
    _collection = None
    _embedding_failed = False