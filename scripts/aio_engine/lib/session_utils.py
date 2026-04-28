"""
Session 工具
============
用于包装已存在的外部 aiohttp.ClientSession，使其支持 async with 语义。
"""

import aiohttp


class NullContextManager:
    """包装已存在的外部 session，使其支持 async with 语义但不关闭它。"""

    def __init__(self, session: aiohttp.ClientSession):
        self._session = session

    async def __aenter__(self):
        return self._session

    async def __aexit__(self, exc_type, exc, tb):
        pass
