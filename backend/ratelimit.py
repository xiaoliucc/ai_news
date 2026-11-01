"""
进程内滑动窗口限流 — 保护「会花钱」的两个接口。

设计取舍：
- **只限 POST /api/collect 与 POST /api/agent/chat**：前者每轮抓 6 个源 + N 次
  LLM 判定，后者直接消耗部署者的 LLM/Tavily 额度；其余接口是 SQLite 只读查询，
  单用户自部署下限制它们只会误伤自己。
- **不用 Redis / SlowAPI**：单进程 uvicorn + 单用户，一把 `threading.Lock` 就够；
  多 worker 部署时每个 worker 各自计数（额度 × worker 数），这是已知边界。
- **滑动窗口而非固定窗口**：固定窗口在边界处能放过 2 倍额度（窗口末 + 下一窗口初）。

时钟可注入（`clock`），测试里用假时钟推进时间，避免 `time.sleep`。
"""

from __future__ import annotations

import math
import threading
import time
from collections import deque
from collections.abc import Callable

# 最多跟踪多少 (客户端, 路径) 组合；超过就清一次空桶，防止公网扫描把字典撑爆。
_MAX_KEYS = 4096


class SlidingWindowLimiter:
    """按 (客户端, 路径) 计数的内存滑动窗口限流器，线程安全。

    Attributes:
        _clock: 单调时钟函数，测试可注入假时钟。
        _hits: 每个键的命中时间戳队列（只保留窗口内的）。
        _lock: 保护 `_hits` 的互斥锁（中间件与后台线程可能并发调用）。
    """

    def __init__(self, clock: Callable[[], float] | None = None) -> None:
        self._clock = clock or time.monotonic
        self._hits: dict[tuple[str, str], deque[float]] = {}
        self._lock = threading.Lock()

    def hit(self, client: str, bucket: str, limit: int, window: int) -> tuple[bool, int]:
        """尝试占用一次配额。

        Args:
            client: 客户端标识（IP 或 X-Forwarded-For 首跳）。
            bucket: 配额分组，通常用请求路径，使不同接口各算各的。
            limit: 窗口内允许的次数；`<= 0` 表示不限制。
            window: 窗口长度（秒）；`<= 0` 时退化为不限制。

        Returns:
            tuple[bool, int]: `(是否放行, 建议重试等待秒数)`。
            放行时等待秒数为 0；拦截时为正整数（≥1，可直接放进 Retry-After）。
        """
        if limit <= 0 or window <= 0:
            return True, 0

        now = self._clock()
        key = (client, bucket)

        with self._lock:
            hits = self._hits.setdefault(key, deque())
            cutoff = now - window
            while hits and hits[0] <= cutoff:
                hits.popleft()

            if len(hits) >= limit:
                # 最早那次过期后就能再进一个
                retry_after = math.ceil(hits[0] + window - now)
                return False, max(retry_after, 1)

            hits.append(now)
            if len(self._hits) > _MAX_KEYS:
                self._prune(cutoff)
            return True, 0

    def reset(self) -> None:
        """清空所有计数（测试用）。"""
        with self._lock:
            self._hits.clear()

    def tracked_keys(self) -> int:
        """当前跟踪的键数量（测试/诊断用）。"""
        with self._lock:
            return len(self._hits)

    def _prune(self, cutoff: float) -> None:
        """丢弃窗口内已无命中的桶（调用方需已持锁）。"""
        stale = [k for k, v in self._hits.items() if not v or v[-1] <= cutoff]
        for k in stale:
            del self._hits[k]


def client_key(forwarded_for: str | None, host: str | None) -> str:
    """提取客户端标识：优先 `X-Forwarded-For` 首跳，退回直连地址。

    公网隧道（cpolar 等）会把来源统一改成 127.0.0.1，此时只有代理头能区分客户端。
    `X-Forwarded-For` 可被伪造，但伪造者需先通过 API_TOKEN 门禁；单用户语义下
    「提高绕过成本」已足够，不做可信代理白名单。

    Args:
        forwarded_for: 请求头 `X-Forwarded-For` 原始值（可为 None）。
        host: `request.client.host`（可为 None）。

    Returns:
        str: 用于计数的客户端标识。
    """
    if forwarded_for:
        first = forwarded_for.split(",")[0].strip()
        if first:
            return first
    return host or "unknown"
