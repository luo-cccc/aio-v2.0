"""
配置加载器
==========
优先级：config.json > 环境变量 > 代码默认值

用法:
    from .config import ConfigLoader
    cfg = ConfigLoader.load()
    provider = cfg["llm"]["provider"]
"""

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional


class ConfigLoader:
    """
    统一配置加载器。

    加载顺序（后面的覆盖前面的）：
        1. 代码默认值
        2. 环境变量
        3. config.json（最高优先级）
    """

    _DEFAULTS: Dict[str, Any] = {
        "llm": {
            "provider": "anthropic",
            "api_key": "",
            "model": "",
            "max_tokens": 300,
            "base_url": "",
        },
        "crawler": {
            "timeout": 30,
            "user_agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        },
        "cache": {
            "ttl_seconds": 300,
        },
    }

    @classmethod
    def _config_path(cls) -> Path:
        """返回 config.json 的路径（与包同级）。"""
        pkg_dir = Path(__file__).parent.parent
        return pkg_dir / "config.json"

    @classmethod
    def _load_json(cls) -> Dict[str, Any]:
        """加载 config.json，不存在则返回空 dict。"""
        path = cls._config_path()
        if not path.exists():
            return {}
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return {}

    @classmethod
    def _deep_update(cls, base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
        """递归合并两个字典，override 覆盖 base。"""
        result = dict(base)
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = cls._deep_update(result[key], value)
            else:
                result[key] = value
        return result

    @classmethod
    def _apply_env_fallback(cls, cfg: Dict[str, Any]) -> Dict[str, Any]:
        """应用环境变量作为 config.json 的降级补充（仅当 config.json 未提供有效值时）。"""
        result = cls._deep_update({}, cfg)

        def _is_empty(val) -> bool:
            return val is None or val == ""

        # LLM_PROVIDER
        if _is_empty(result.get("llm", {}).get("provider")):
            env_provider = os.environ.get("LLM_PROVIDER")
            if env_provider:
                result.setdefault("llm", {})
                result["llm"]["provider"] = env_provider.lower().strip()

        # API_KEY（根据当前 provider 选择对应的环境变量）
        if _is_empty(result.get("llm", {}).get("api_key")):
            provider = result.get("llm", {}).get("provider", "anthropic")
            key_env_map = {
                "anthropic": "ANTHROPIC_API_KEY",
                "openai": "OPENAI_API_KEY",
                "deepseek": "DEEPSEEK_API_KEY",
                "glm": "GLM_API_KEY",
                "minimax": "MINIMAX_API_KEY",
                "kimi": "KIMI_API_KEY",
                "qwen": "QWEN_API_KEY",
                "doubao": "DOUBAO_API_KEY",
                "openai-compatible": "OPENAI_API_KEY",
            }
            key_env = key_env_map.get(provider, "ANTHROPIC_API_KEY")
            env_key = os.environ.get(key_env)
            if env_key:
                result.setdefault("llm", {})
                result["llm"]["api_key"] = env_key

        # LLM_MODEL
        if _is_empty(result.get("llm", {}).get("model")):
            env_model = os.environ.get("LLM_MODEL")
            if env_model:
                result.setdefault("llm", {})
                result["llm"]["model"] = env_model

        # OPENAI_BASE_URL
        if _is_empty(result.get("llm", {}).get("base_url")):
            env_base_url = os.environ.get("OPENAI_BASE_URL")
            if env_base_url:
                result.setdefault("llm", {})
                result["llm"]["base_url"] = env_base_url

        return result

    @classmethod
    def load(cls) -> Dict[str, Any]:
        """
        加载完整配置。

        Returns:
            合并后的配置字典。
        """
        cfg = cls._deep_update({}, cls._DEFAULTS)
        json_cfg = cls._load_json()
        cfg = cls._deep_update(cfg, json_cfg)
        cfg = cls._apply_env_fallback(cfg)
        return cfg

    @classmethod
    def get(cls, *keys: str, default: Any = None) -> Any:
        """
        按路径获取配置值。

        用法:
            ConfigLoader.get("llm", "provider")  # -> "anthropic"
            ConfigLoader.get("crawler", "timeout", default=60)
        """
        cfg = cls.load()
        for key in keys:
            if not isinstance(cfg, dict):
                return default
            cfg = cfg.get(key, default)
            if cfg is None:
                return default
        return cfg
