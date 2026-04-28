"""
统一 LLM 客户端 (aiohttp + Semaphore 限流)
============================================
支持 9 个提供商，提供 chat() 和 chat_vision() 接口。
"""

import asyncio
import base64
import json
import os
import re
from typing import Optional
from urllib.parse import urlparse

import aiohttp


# ------------------------------------------------------------------
# Prompt 注入防护
# ------------------------------------------------------------------
_MAX_USER_CONTENT_LEN = 3000  # 用户内容最大长度
_INJECTION_PATTERNS = [
    # OpenAI/Anthropic 系统消息分隔符
    r"<\|im_start\|>",
    r"<\|im_end\|>",
    r"<\|endoftext\|>",
    r"<\|startoftext\|>",
    # Anthropic 特定
    r"\n\nHuman:\s*",
    r"\n\nAssistant:\s*",
    # 通用指令注入
    r"\n\nSystem:\s*",
    r"\n\n(system|user|assistant)\s*instruction",
    # XML tag 风格注入
    r"<system>",
    r"</system>",
    r"<instruction>",
    r"</instruction>",
]
_INJECTION_RE = re.compile("|".join(_INJECTION_PATTERNS), re.IGNORECASE)


def sanitize_user_content(text: str, max_len: int = _MAX_USER_CONTENT_LEN) -> str:
    """
    清理用户可控内容，防止 Prompt 注入攻击。

    措施：
    1. 截断过长内容
    2. 移除/中和已知注入模式（系统消息分隔符、角色切换标记等）
    3. 去除控制字符（除常规换行/制表符外）
    """
    if not isinstance(text, str):
        text = str(text)

    # 截断
    if len(text) > max_len:
        text = text[:max_len] + "\n...[truncated]"

    # 中和注入模式：将匹配到的模式替换为无害占位符
    text = _INJECTION_RE.sub("[removed]", text)

    # 去除控制字符（保留 \t, \n, \r）
    text = "".join(ch for ch in text if ch == "\t" or ch == "\n" or ch == "\r" or (ord(ch) >= 32 and ord(ch) != 127))

    return text

def _validate_api_url(url: str) -> str:
    """校验 API base_url：仅允许 HTTPS，且必须有合法域名。"""
    parsed = urlparse(url)
    if parsed.scheme not in ("https",):
        raise ValueError(f"API base_url 必须使用 HTTPS: {url}")
    if not parsed.netloc:
        raise ValueError(f"无效的 API base_url: {url}")
    return url.rstrip("/")


# 提供商默认配置
_PROVIDER_CONFIG = {
    "anthropic": {
        "key_env": "ANTHROPIC_API_KEY",
        "default_model": "claude-sonnet-4-20250514",
        "max_tokens": 300,
        "base_url": None,
    },
    "openai": {
        "key_env": "OPENAI_API_KEY",
        "default_model": "gpt-4o",
        "max_tokens": 300,
        "base_url": "https://api.openai.com/v1",
    },
    "deepseek": {
        "key_env": "DEEPSEEK_API_KEY",
        "default_model": "deepseek-chat",
        "max_tokens": 300,
        "base_url": "https://api.deepseek.com/v1",
    },
    "glm": {
        "key_env": "GLM_API_KEY",
        "default_model": "glm-4v-flash",
        "max_tokens": 300,
        "base_url": "https://open.bigmodel.cn/api/paas/v4",
    },
    "minimax": {
        "key_env": "MINIMAX_API_KEY",
        "default_model": "abab6.5s-chat",
        "max_tokens": 300,
        "base_url": "https://api.minimax.chat/v1",
    },
    "kimi": {
        "key_env": "KIMI_API_KEY",
        "default_model": "moonshot-v1-8k",
        "max_tokens": 300,
        "base_url": "https://api.moonshot.cn/v1",
    },
    "qwen": {
        "key_env": "QWEN_API_KEY",
        "default_model": "qwen-vl-plus",
        "max_tokens": 300,
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    },
    "doubao": {
        "key_env": "DOUBAO_API_KEY",
        "default_model": "doubao-1.5-vision-pro-32k",
        "max_tokens": 300,
        "base_url": "https://ark.cn-beijing.volces.com/api/v3",
    },
    "openai-compatible": {
        "key_env": "OPENAI_API_KEY",
        "default_model": "gpt-4o",
        "max_tokens": 300,
        "base_url": None,  # 必须从 OPENAI_BASE_URL 读取
    },
}

_NO_VISION_PROVIDERS = {"deepseek", "minimax", "kimi"}


from .session_utils import NullContextManager

class LLMClient:
    """
    异步 LLM 客户端，内置 Semaphore 限流（默认并发 3）。
    支持无配置初始化（用于 has_valid_config 检测和 fallback 场景）。
    支持外部传入 aiohttp.ClientSession 以复用连接池。
    """

    def __init__(self, semaphore_value: int = 3, session: Optional[aiohttp.ClientSession] = None):
        self._sem = asyncio.Semaphore(semaphore_value)
        self._config: Optional[dict] = None
        self._session = session
        self._own_session = session is None

    def _session_ctx(self):
        """返回 session 上下文管理器：若已传入外部 session 则直接 yield，否则新建。"""
        if self._session is not None:
            return NullContextManager(self._session)
        return aiohttp.ClientSession()

    async def close(self) -> None:
        """关闭由本实例创建的 aiohttp session（外部传入的不关闭）。"""
        if self._own_session and self._session is not None:
            await self._session.close()
            self._session = None

    # ------------------------------------------------------------------
    # 配置解析（优先级：config.json > 环境变量 > 默认值）
    # ------------------------------------------------------------------
    @staticmethod
    def _resolve_config() -> dict:
        from .config import ConfigLoader

        cfg = ConfigLoader.load()
        llm_cfg = cfg.get("llm", {})

        provider = llm_cfg.get("provider", "anthropic").lower().strip()
        prov_defaults = _PROVIDER_CONFIG.get(provider)
        if prov_defaults is None:
            raise ValueError(
                f'不支持的 LLM 提供商: "{provider}"。'
                f"支持的: {', '.join(_PROVIDER_CONFIG)}"
            )

        api_key = llm_cfg.get("api_key", "")
        if not api_key:
            raise ValueError(
                f'使用 "{provider}" 需要设置 api_key（config.json 或环境变量 {prov_defaults["key_env"]}）。'
            )

        raw_base_url = llm_cfg.get("base_url") or prov_defaults["base_url"]
        if provider == "openai-compatible" and not raw_base_url:
            raise ValueError(
                '使用 "openai-compatible" 需要设置 base_url（config.json 或环境变量 OPENAI_BASE_URL）。'
            )

        base_url = _validate_api_url(raw_base_url) if raw_base_url else None

        model = llm_cfg.get("model") or prov_defaults["default_model"]
        max_tokens = llm_cfg.get("max_tokens") or prov_defaults["max_tokens"]
        return {
            "provider": provider,
            "api_key": api_key,
            "model": model,
            "max_tokens": max_tokens,
            "base_url": base_url,
        }

    @classmethod
    def has_valid_config(cls) -> bool:
        """检查当前是否有可用的 LLM 配置。"""
        try:
            cls._resolve_config()
            return True
        except ValueError:
            return False

    def _ensure_config(self) -> dict:
        if self._config is None:
            self._config = self._resolve_config()
        return self._config

    # ------------------------------------------------------------------
    # 公共接口
    # ------------------------------------------------------------------
    async def chat(self, prompt: str) -> str:
        """发送文本 prompt，返回 LLM 响应。"""
        cfg = self._ensure_config()
        async with self._sem:
            if cfg["provider"] == "anthropic":
                return await self._call_anthropic(cfg, prompt)
            return await self._call_openai_compatible(cfg, prompt)

    async def chat_vision(self, prompt: str, image_data: bytes, mime_type: str) -> str:
        """发送 prompt + 图片，返回 LLM 响应。"""
        cfg = self._ensure_config()
        if cfg["provider"] in _NO_VISION_PROVIDERS:
            raise ValueError(
                f'"{cfg["provider"]}" 默认模型不支持视觉输入。'
                f'请切换到 anthropic、openai、glm、qwen、doubao 之一，'
                f'或通过 LLM_MODEL 指定视觉模型。'
            )

        async with self._sem:
            if cfg["provider"] == "anthropic":
                return await self._call_anthropic_vision(cfg, prompt, image_data, mime_type)
            return await self._call_openai_compatible_vision(cfg, prompt, image_data, mime_type)

    # ------------------------------------------------------------------
    # Anthropic 实现
    # ------------------------------------------------------------------
    async def _call_anthropic(self, cfg: dict, prompt: str) -> str:
        url = f"{cfg['base_url']}/v1/messages" if cfg.get("base_url") else "https://api.anthropic.com/v1/messages"
        headers = {
            "x-api-key": cfg["api_key"],
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }
        payload = {
            "model": cfg["model"],
            "max_tokens": cfg["max_tokens"],
            "messages": [{"role": "user", "content": prompt}],
        }
        text = await self._post_json(url, headers, payload)
        return self._extract_anthropic_text(text)

    async def _call_anthropic_vision(
        self, cfg: dict, prompt: str, image_data: bytes, mime_type: str
    ) -> str:
        url = f"{cfg['base_url']}/v1/messages" if cfg.get("base_url") else "https://api.anthropic.com/v1/messages"
        headers = {
            "x-api-key": cfg["api_key"],
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }
        b64 = base64.b64encode(image_data).decode("ascii")
        payload = {
            "model": cfg["model"],
            "max_tokens": cfg["max_tokens"],
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": mime_type,
                                "data": b64,
                            },
                        },
                    ],
                }
            ],
        }
        text = await self._post_json(url, headers, payload)
        return self._extract_anthropic_text(text)

    @staticmethod
    def _extract_anthropic_text(raw: str) -> str:
        data = json.loads(raw)
        content = data.get("content")
        if not isinstance(content, list) or not content:
            raise RuntimeError(f"Anthropic 响应结构异常: {raw[:200]}")
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                text = block.get("text")
                if isinstance(text, str):
                    return text.strip()
        return ""

    # ------------------------------------------------------------------
    # OpenAI-compatible 实现
    # ------------------------------------------------------------------
    async def _call_openai_compatible(self, cfg: dict, prompt: str) -> str:
        url = f"{cfg['base_url']}/chat/completions"
        headers = {
            "Authorization": f"Bearer {cfg['api_key']}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": cfg["model"],
            "max_tokens": cfg["max_tokens"],
            "messages": [{"role": "user", "content": prompt}],
        }
        text = await self._post_json(url, headers, payload)
        return self._extract_openai_text(text)

    async def _call_openai_compatible_vision(
        self, cfg: dict, prompt: str, image_data: bytes, mime_type: str
    ) -> str:
        url = f"{cfg['base_url']}/chat/completions"
        headers = {
            "Authorization": f"Bearer {cfg['api_key']}",
            "Content-Type": "application/json",
        }
        b64 = base64.b64encode(image_data).decode("ascii")
        payload = {
            "model": cfg["model"],
            "max_tokens": cfg["max_tokens"],
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{mime_type};base64,{b64}",
                            },
                        },
                    ],
                }
            ],
        }
        text = await self._post_json(url, headers, payload)
        return self._extract_openai_text(text)

    @staticmethod
    def _extract_openai_text(raw: str) -> str:
        data = json.loads(raw)
        choices = data.get("choices")
        if not isinstance(choices, list) or not choices:
            raise RuntimeError(f"OpenAI 响应结构异常: {raw[:200]}")
        first = choices[0]
        if not isinstance(first, dict):
            raise RuntimeError(f"OpenAI 响应结构异常: {raw[:200]}")
        message = first.get("message") or {}
        if not isinstance(message, dict):
            raise RuntimeError(f"OpenAI 响应结构异常: {raw[:200]}")
        content = message.get("content")
        return content.strip() if isinstance(content, str) else ""

    # ------------------------------------------------------------------
    # 底层 HTTP
    # ------------------------------------------------------------------
    async def _post_json(self, url: str, headers: dict, payload: dict) -> str:
        timeout = aiohttp.ClientTimeout(total=300, connect=10)
        async with self._session_ctx() as session:
            async with session.post(
                url, headers=headers, json=payload, timeout=timeout
            ) as resp:
                text = await resp.text()
                if resp.status != 200:
                    raise RuntimeError(
                        f"API 请求失败 ({resp.status}): {text[:500]}"
                    )
                return text
