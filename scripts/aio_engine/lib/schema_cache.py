"""
Schema.org 类型缓存管理器
=========================
复用项目根目录的 schemaorg-cache.jsonld，提供类型查找和描述。
"""

import json
import os
from typing import Any, Dict, List, Optional, Tuple

_CACHE_PATHS = [
    os.path.join(os.path.dirname(__file__), "..", "..", "schemaorg-cache.jsonld"),
    os.path.join(os.path.dirname(__file__), "..", "..", "schemaorg-all-http.jsonld"),
]


class SchemaCache:
    """
    加载 Schema.org 缓存，提供类型名到描述的映射。
    """

    def __init__(self):
        self._type_map: Dict[str, str] = {}
        self._loaded = False

    def _load(self) -> None:
        if self._loaded:
            return
        for path in _CACHE_PATHS:
            if os.path.exists(path):
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    self._parse_graph(data)
                    self._loaded = True
                    return
                except (json.JSONDecodeError, OSError):
                    continue
        # 若找不到缓存文件，使用内置精简映射作为 fallback
        self._type_map = _FALLBACK_TYPES
        self._loaded = True

    def _parse_graph(self, data: dict) -> None:
        graph = data.get("@graph", [])
        for node in graph:
            if not isinstance(node, dict):
                continue
            types = node.get("@type", [])
            if isinstance(types, str):
                types = [types]
            if "rdfs:Class" in types:
                name = _extract_text(node.get("rdfs:label", ""))
                if not name:
                    # 尝试从 @id 提取
                    node_id = _extract_text(node.get("@id", ""))
                    if node_id.startswith("schema:"):
                        name = node_id[7:]
                desc = _extract_text(node.get("rdfs:comment", ""))
                if name and isinstance(name, str):
                    self._type_map[name] = desc

    def get_description(self, type_name: str) -> Optional[str]:
        """获取指定 Schema.org 类型的描述。"""
        self._load()
        return self._type_map.get(type_name)

    def all_types(self) -> List[str]:
        """返回所有已知类型名列表。"""
        self._load()
        return list(self._type_map.keys())

    def local_match(self, query: str, top_k: int = 3) -> List[Tuple[str, str, int]]:
        """
        基于关键词的本地类型匹配（Levenshtein + 包含匹配）。

        返回: List[(type_name, description, score)]
        """
        self._load()
        keywords = [w for w in query.lower().split() if len(w) >= 2]
        if not keywords:
            return []

        scores: Dict[str, int] = {}
        for tname, desc in self._type_map.items():
            tlower = tname.lower()
            dlower = (desc or "").lower()
            score = 0
            for kw in keywords:
                if tlower == kw:
                    score += 100
                elif tlower.startswith(kw):
                    score += 60
                elif tlower.replace("schema:", "").startswith(kw):
                    score += 60
                elif tlower.endswith(kw):
                    score += 40
                elif kw in tlower:
                    score += 30
                if kw in dlower:
                    score += 20
                if len(kw) > 3 and len(tlower) > 3:
                    dist = _levenshtein(kw, tlower)
                    if dist <= 2:
                        score += 30
            if score > 0:
                scores[tname] = score

        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        return [
            (name, self._type_map.get(name, ""), sc)
            for name, sc in ranked[:top_k]
        ]


# ------------------------------------------------------------------
# 工具函数
# ------------------------------------------------------------------

def _levenshtein(a: str, b: str) -> int:
    """计算两个字符串的编辑距离。"""
    if len(a) < len(b):
        return _levenshtein(b, a)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    curr = [0] * (len(b) + 1)
    for i, ca in enumerate(a, 1):
        curr[0] = i
        for j, cb in enumerate(b, 1):
            curr[j] = min(
                curr[j - 1] + 1,
                prev[j] + 1,
                prev[j - 1] + (0 if ca == cb else 1),
            )
        prev, curr = curr, prev
    return prev[len(b)]


def _extract_text(value: Any) -> str:
    """从 JSON-LD 值中提取纯文本（处理 @value 对象）。"""
    if isinstance(value, dict):
        return value.get("@value", "")
    if isinstance(value, str):
        return value
    return str(value) if value is not None else ""


# 内置 fallback 映射（精简常用类型）
_FALLBACK_TYPES: Dict[str, str] = {
    "Product": "Any offered product or service.",
    "Article": "An article, such as a news article or piece of investigative report.",
    "BlogPosting": "A blog post.",
    "WebPage": "A web page.",
    "Organization": "An organization such as a school, NGO, corporation, club, etc.",
    "Person": "A person (alive, dead, undead, or fictional).",
    "Event": "An event happening at a certain time and location.",
    "Place": "Entities that have a somewhat fixed, physical extension.",
    "LocalBusiness": "A particular physical business or branch of an organization.",
    "Restaurant": "A restaurant.",
    "Store": "A retail good store.",
    "FAQPage": "A WebPage devoted to FAQ content.",
    "HowTo": "Instructions that explain how to achieve a result.",
    "VideoObject": "A video file.",
    "ImageObject": "An image file.",
    "Review": "A review of an item.",
    "AggregateRating": "The average rating based on multiple ratings or reviews.",
    "JobPosting": "A listing that describes a job opening.",
    "Course": "A description of an educational course.",
    "SoftwareApplication": "A software application.",
    "MobileApplication": "A software application designed specifically for mobile devices.",
}
