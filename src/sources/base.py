"""数据源抽象基类。"""

import os
from abc import ABC, abstractmethod

from src.models import Article

# 网络代理（全局生效）：墙外源（GitHub / HuggingFace）需要时填写本机代理地址。
# 读取 .env 的 HTTPS_PROXY（backend.config 加载 .env 后注入环境变量）；
# 留空 = 直连。多设备各自维护 .env，代理地址按设备填写。
# 注意：load_dotenv 不覆盖已存在的系统环境变量——系统已有 HTTPS_PROXY 时系统值优先。
PROXY_URL = os.getenv("HTTPS_PROXY", "").strip() or None


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
