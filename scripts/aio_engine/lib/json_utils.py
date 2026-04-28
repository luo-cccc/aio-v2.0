"""
JSON 解析工具
============
从 LLM 响应中提取 JSON 对象/数组的容错解析器。
"""

import json
from typing import Any, List


def parse_json_object(text: str) -> dict:
    """从文本中提取 JSON 对象，支持容错。"""
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(text[start:end + 1])
        except json.JSONDecodeError:
            pass
    return {}


def parse_json_array(text: str) -> List[Any]:
    """从文本中提取 JSON 数组，支持容错。"""
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    start = text.find("[")
    end = text.rfind("]")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(text[start:end + 1])
        except json.JSONDecodeError:
            pass
    return []
