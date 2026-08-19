"""数据源抽象基类。"""

from abc import ABC, abstractmethod

from src.models import Article


class SourcePlugin(ABC):
    """数据源插件的抽象基类。

    所有数据源必须实现 fetch() 方法，返回统一的 Article 列表。
    name 类属性用于日志标识和用户选择。

    Attributes:
        name: 数据源名称（如 "hackernews"）。
    """

    name: str = "Base"

    @abstractmethod
    async def fetch(self, limit: int = 20) -> list[Article]:
        """从数据源拉取文章。

        Args:
            limit: 最多拉取的条数。

        Returns:
            list[Article]: 采集到的文章列表。
        """
        pass
