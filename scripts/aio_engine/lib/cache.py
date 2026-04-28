"""
可选结果缓存层
==============
基于 URL 的内存缓存，支持 TTL 和显式失效。

用法:
    from aio_engine.lib.cache import Cache
    cache = Cache(ttl_seconds=300)
    cache.set(url, result)
    hit = cache.get(url)  # -> result or None
"""

import hashlib
import time
from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class _CacheEntry:
    """缓存条目。"""

    value: dict
    created_at: float
    url: str


class Cache:
    """
    简单的内存缓存，用于存储分析结果。

    特性:
    - TTL 过期自动失效
    - 基于 URL 的键生成（支持长 URL）
    - 线程/协程安全（单进程内）
    """

    def __init__(self, ttl_seconds: int = 300):
        self._ttl = ttl_seconds
        self._store: Dict[str, _CacheEntry] = {}

    @staticmethod
    def _make_key(url: str) -> str:
        """生成缓存键（对长 URL 使用 hash）。"""
        safe_url = str(url) if url is not None else ""
        if len(safe_url) <= 128:
            return safe_url
        return hashlib.sha256(safe_url.encode("utf-8")).hexdigest()

    def get(self, url: str) -> Optional[dict]:
        """获取缓存结果，若过期或不存在返回 None。"""
        key = self._make_key(url)
        entry = self._store.get(key)
        if entry is None:
            return None
        if time.time() - entry.created_at > self._ttl:
            del self._store[key]
            return None
        return entry.value

    def set(self, url: str, value: dict) -> None:
        """存入缓存结果。"""
        key = self._make_key(url)
        self._store[key] = _CacheEntry(
            value=value,
            created_at=time.time(),
            url=url,
        )

    def invalidate(self, url: str) -> bool:
        """手动失效指定 URL 的缓存。"""
        key = self._make_key(url)
        if key in self._store:
            del self._store[key]
            return True
        return False

    def clear(self) -> None:
        """清空所有缓存。"""
        self._store.clear()

    def stats(self) -> Dict[str, Any]:
        """返回缓存统计信息。"""
        now = time.time()
        total = len(self._store)
        expired = sum(1 for e in self._store.values() if now - e.created_at > self._ttl)
        return {
            "total_entries": total,
            "expired_entries": expired,
            "ttl_seconds": self._ttl,
        }
