"""
Schema.org 结构化数据生成器
============================
基于推断的类型生成 JSON-LD 代码框架。
复用 schema_lookup.py 的核心逻辑。
"""

import json
import os
from typing import Any, Dict, List, Optional, Tuple

from ..lib.llm_client import LLMClient, sanitize_user_content
from ..lib.schema_cache import SchemaCache
from ..lib.json_utils import parse_json_object

# 原始类型集合
_PRIMITIVE_TYPES = {
    "Text", "URL", "Number", "Integer", "Float",
    "Boolean", "Date", "DateTime", "Time", "Duration",
}

# 占位值
_PRIMITIVE_PLACEHOLDERS = {
    "Text": "",
    "URL": "https://example.com/",
    "Number": 0,
    "Integer": 0,
    "Float": 0,
    "Boolean": False,
    "Date": "2025-01-01",
    "DateTime": "2025-01-01T00:00:00+08:00",
    "Time": "00:00:00",
    "Duration": "PT1H30M",
}

_WEAK_PRIMITIVES = {"Text", "URL"}

# Google 富结果推荐属性
_GOOGLE_RICH_RESULTS = {
    "Article": {
        "required": {"headline", "image", "datePublished", "author"},
        "recommended": {"dateModified", "publisher"},
    },
    "Book": {
        "required": {"name", "author"},
        "recommended": {"isbn", "publisher", "datePublished", "url", "workExample"},
    },
    "BreadcrumbList": {
        "required": {"itemListElement"},
        "recommended": set(),
    },
    "Course": {
        "required": {"name", "description", "provider"},
        "recommended": {"offers", "hasCourseInstance"},
    },
    "Event": {
        "required": {"name", "startDate", "location"},
        "recommended": {"endDate", "description", "image", "offers",
                        "organizer", "performer", "eventStatus",
                        "previousStartDate"},
    },
    "FAQPage": {
        "required": {"mainEntity"},
        "recommended": set(),
    },
    "HowTo": {
        "required": {"name", "step"},
        "recommended": {"image", "description", "totalTime", "estimatedCost",
                        "supply", "tool"},
    },
    "JobPosting": {
        "required": {"title", "description", "datePosted", "hiringOrganization",
                     "jobLocation"},
        "recommended": {"baseSalary", "employmentType", "validThrough"},
    },
    "LocalBusiness": {
        "required": {"name", "address"},
        "recommended": {"image", "telephone", "url", "openingHoursSpecification",
                        "geo", "priceRange", "aggregateRating"},
    },
    "Movie": {
        "required": {"name", "image"},
        "recommended": {"director", "dateCreated", "aggregateRating", "review"},
    },
    "Person": {
        "required": {"name"},
        "recommended": {"image", "url", "jobTitle", "worksFor", "sameAs"},
    },
    "Product": {
        "required": {"name", "image"},
        "recommended": {"description", "brand", "sku", "gtin", "offers",
                        "aggregateRating", "review"},
    },
    "Recipe": {
        "required": {"name", "image"},
        "recommended": {"author", "datePublished", "description", "prepTime",
                        "cookTime", "totalTime", "recipeYield", "recipeIngredient",
                        "recipeInstructions", "recipeCategory",
                        "recipeCuisine", "video"},
    },
    "Restaurant": {
        "required": {"name", "address"},
        "recommended": {"image", "telephone", "servesCuisine", "priceRange",
                        "menu", "url", "openingHoursSpecification",
                        "acceptsReservations"},
    },
    "SoftwareApplication": {
        "required": {"name", "offers"},
        "recommended": {"operatingSystem", "applicationCategory",
                        "aggregateRating", "review"},
    },
    "VideoObject": {
        "required": {"name", "description", "thumbnailUrl", "uploadDate"},
        "recommended": {"contentUrl", "duration", "embedUrl",
                        "interactionStatistic"},
    },
    "WebSite": {
        "required": {"name", "url"},
        "recommended": {"potentialAction"},
    },
}

_ARRAY_PROPERTIES = {
    "actor", "author", "creator", "director", "performer", "organizer",
    "image", "sameAs", "review", "offers",
    "recipeIngredient", "recipeInstructions", "recipeCategory",
    "itemListElement", "step", "supply", "tool",
    "keywords", "genre", "mainEntity",
    "acceptedAnswer", "suggestedAnswer",
    "hasPart", "workExample", "citation",
}

_PARENT_USEFUL_PROPS = {
    "CreativeWork": [
        "author", "datePublished", "dateModified", "publisher",
        "aggregateRating", "review", "inLanguage", "genre",
        "keywords", "offers", "headline", "copyrightYear",
    ],
    "Organization": [
        "address", "telephone", "email", "logo", "contactPoint",
        "foundingDate", "numberOfEmployees",
    ],
    "Place": [
        "address", "geo", "telephone", "hasMap",
        "openingHoursSpecification",
    ],
    "Action": ["target", "agent", "object", "result"],
    "Event": [
        "startDate", "endDate", "location", "organizer",
        "performer", "offers", "eventStatus",
    ],
    "Product": [
        "brand", "sku", "gtin", "mpn", "offers",
        "aggregateRating", "review", "color", "material",
    ],
    "MedicalEntity": ["code", "guideline", "relevantSpecialty"],
}

_COMPLEX_TYPE_DEFAULTS = {
    "AggregateRating": {
        "@type": "AggregateRating",
        "ratingValue": "",
        "reviewCount": "",
    },
}

_URL_FIRST_PROPERTIES = {"image", "thumbnailUrl", "contentUrl", "embedUrl"}


class SchemaGenerator:
    """
    根据推断的 Schema.org 类型生成 JSON-LD 代码框架。
    """

    def __init__(self, llm: LLMClient):
        self._llm = llm
        self._schema_cache = SchemaCache()
        self._classes: Dict[str, dict] = {}
        self._properties: Dict[str, dict] = {}
        self._load_full_schema()

    def _load_full_schema(self) -> None:
        """加载完整的 Schema.org 数据以获取类和属性关系。"""
        paths = [
            os.path.join(os.path.dirname(__file__), "..", "..", "schemaorg-cache.jsonld"),
            os.path.join(os.path.dirname(__file__), "..", "..", "schemaorg-all-http.jsonld"),
        ]
        for path in paths:
            if os.path.exists(path):
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    self._classes, self._properties = self._parse_schema(data)
                    return
                except (json.JSONDecodeError, OSError):
                    continue

    @staticmethod
    def _parse_schema(raw: dict) -> Tuple[Dict[str, dict], Dict[str, dict]]:
        graph = raw.get("@graph", [])
        classes: Dict[str, dict] = {}
        properties: Dict[str, dict] = {}

        for node in graph:
            node_types = node.get("@type", [])
            if isinstance(node_types, str):
                node_types = [node_types]
            node_id = _extract_name(node.get("@id", ""))
            comment = node.get("rdfs:comment", "")
            if isinstance(comment, dict):
                comment = comment.get("@value", str(comment))

            if "rdfs:Class" in node_types:
                parents = [_extract_name(p) for p in _ensure_list(node.get("rdfs:subClassOf"))]
                classes[node_id] = {"comment": comment, "parents": parents}

            if "rdf:Property" in node_types:
                domains = [_extract_name(d) for d in _ensure_list(node.get("schema:domainIncludes"))]
                ranges = [_extract_name(r) for r in _ensure_list(node.get("schema:rangeIncludes"))]
                properties[node_id] = {"comment": comment, "domains": domains, "ranges": ranges}

        return classes, properties

    async def generate(self, type_name: str, page) -> dict:
        """
        生成指定类型的 JSON-LD 框架。

        返回标准模块结果格式:
            {"status": "success", "score": int, "schemas": {...},
             "score_details": {...}, "fallback": bool, "errors": [...],
             "recommended_actions": [...]}
        """
        if not self._classes or type_name not in self._classes:
            # fallback: 尝试用 LLM 生成基础框架
            return await self._generate_llm_fallback(type_name, page)

        direct_props = self._get_direct_properties(type_name)
        jsonld = self._build_jsonld(type_name, direct_props, page)

        # 自评分数：基于属性覆盖率
        score, score_details = self._score_schema(type_name, direct_props, page)

        actions = []
        google = _GOOGLE_RICH_RESULTS.get(type_name, {"required": set(), "recommended": set()})
        for req in google.get("required", set()):
            if req not in jsonld:
                actions.append({
                    "action": f"为 {type_name} 添加必需属性: {req}",
                    "priority": "high",
                    "target_module": "schema_generator",
                    "params": {"type_name": type_name, "property": req},
                })

        # 提取核心实体用于 GEO 实体链接
        entities = self._extract_entities(type_name, jsonld, page)

        # 检查 sameAs/identifier 缺失，生成 GEO 动作
        if not jsonld.get("sameAs"):
            actions.append({
                "action": f"为 {type_name} 添加 sameAs 链接（如 Wikidata、百度百科）以提升实体识别度",
                "priority": "medium",
                "target_module": "schema_generator",
                "params": {"type_name": type_name, "entities": entities},
            })
        if type_name == "Product" and not (jsonld.get("sku") or jsonld.get("gtin")):
            actions.append({
                "action": "为 Product 添加 SKU 或 GTIN 标识符，帮助 AI 引擎唯一识别商品",
                "priority": "high",
                "target_module": "schema_generator",
                "params": {"type_name": type_name, "missing": "identifier"},
            })

        return {
            "status": "success",
            "score": score,
            "schemas": {type_name: jsonld},
            "entities": entities,
            "score_details": score_details,
            "fallback": False,
            "errors": [],
            "recommended_actions": actions,
        }

    async def _generate_llm_fallback(self, type_name: str, page) -> dict:
        safe_title = sanitize_user_content(page.title or "", max_len=200)
        safe_desc = sanitize_user_content(page.description or "", max_len=300)
        safe_type = sanitize_user_content(type_name, max_len=50)
        prompt = (
            f"请为 Schema.org 类型 '{safe_type}' 生成一个 JSON-LD 代码框架。\n"
            f"页面标题: {safe_title}\n"
            f"页面描述: {safe_desc}\n"
            f"仅返回 JSON 对象，不要解释。"
        )
        try:
            text = await self._llm.chat(prompt)
            schema = parse_json_object(text)
            return {
                "status": "success",
                "score": 50,
                "schemas": {type_name: schema},
                "score_details": {
                    "base_score": 50,
                    "title_bonus": 10 if page.title else 0,
                    "description_bonus": 10 if page.description else 0,
                    "required_coverage": 0,
                    "reason": "本地 schema 数据缺失，使用 LLM fallback 生成",
                },
                "fallback": True,
                "errors": [],
                "recommended_actions": [
                    {
                        "action": f"验证 {type_name} 的 JSON-LD 结构是否符合 Schema.org 规范",
                        "priority": "medium",
                        "target_module": "schema_generator",
                        "params": {"type_name": type_name},
                    }
                ],
            }
        except (RuntimeError, OSError, ValueError) as e:
            return {
                "status": "error",
                "score": 0,
                "schemas": {},
                "score_details": {
                    "base_score": 0,
                    "reason": f"LLM fallback 也失败: {e}",
                },
                "fallback": True,
                "errors": [str(e)],
                "recommended_actions": [
                    {
                        "action": f"无法生成 {type_name} 的 Schema，请手动检查类型名称",
                        "priority": "high",
                        "target_module": "schema_generator",
                        "params": {"type_name": type_name},
                    }
                ],
            }

    def _get_direct_properties(self, class_name: str) -> List[Tuple[str, dict]]:
        result = []
        for prop_name, prop_info in self._properties.items():
            if class_name in prop_info["domains"]:
                result.append((prop_name, prop_info))
        result.sort(key=lambda x: x[0].lower())
        return result

    def _get_parent_chain(self, class_name: str) -> List[str]:
        chain = []
        visited = set()
        current = class_name
        max_depth = 50  # 防止循环引用导致无限循环
        depth = 0
        while current and current in self._classes and current not in visited and depth < max_depth:
            visited.add(current)
            parents = self._classes[current]["parents"]
            if parents:
                parent = parents[0]
                chain.append(parent)
                current = parent
                depth += 1
            else:
                break
        return chain

    def _build_jsonld(self, class_name: str, direct_props: List[Tuple[str, dict]], page) -> dict:
        google = _GOOGLE_RICH_RESULTS.get(class_name, {"required": set(), "recommended": set()})
        google_all = google["required"] | google["recommended"]
        direct_names = {name for name, _ in direct_props}

        chain = self._get_parent_chain(class_name)
        parent_name = None
        parent_props_to_add = []
        for ancestor in chain:
            if ancestor == "Thing":
                continue
            if ancestor in _PARENT_USEFUL_PROPS:
                parent_name = ancestor
                useful = _PARENT_USEFUL_PROPS[ancestor]
                for pname in useful:
                    if pname in self._properties and pname not in direct_names and pname not in ("name", "description", "url"):
                        parent_props_to_add.append((pname, self._properties[pname]))
                break
            parent_name = ancestor
            ancestor_direct = self._get_direct_properties(ancestor)
            for pname, pinfo in ancestor_direct:
                if pname in google_all and pname not in direct_names and pname not in ("name", "description", "url"):
                    parent_props_to_add.append((pname, pinfo))
            break

        result = {
            "@context": "https://schema.org",
            "@type": class_name,
        }

        # 基本信息
        fill = {}
        if page.title:
            fill["name"] = page.title
        if page.description:
            fill["description"] = page.description
        fill["url"] = page.url

        for key in ("name", "description", "url"):
            result[key] = fill.get(key, _PRIMITIVE_PLACEHOLDERS.get("Text", ""))

        # 直接属性
        for prop_name, prop_info in direct_props:
            if prop_name in ("name", "description", "url"):
                continue
            value = self._get_placeholder(prop_info["ranges"], prop_name)
            if prop_name in _ARRAY_PROPERTIES:
                value = [value] if not isinstance(value, list) else value
            result[prop_name] = value

        # 父类属性
        for prop_name, prop_info in parent_props_to_add:
            value = self._get_placeholder(prop_info["ranges"], prop_name)
            if prop_name in _ARRAY_PROPERTIES:
                value = [value] if not isinstance(value, list) else value
            result[prop_name] = value

        # Google 推荐补全
        already_added = set(result.keys())
        for gp in sorted(google_all):
            if gp not in already_added and gp in self._properties:
                value = self._get_placeholder(self._properties[gp]["ranges"], gp)
                if gp in _ARRAY_PROPERTIES:
                    value = [value] if not isinstance(value, list) else value
                result[gp] = value

        return result

    def _get_placeholder(self, ranges: List[str], prop_name: str = "") -> Any:
        first_complex = None
        first_primitive = None
        has_url = False

        for r in ranges:
            if first_complex is None and r in self._classes and r not in _PRIMITIVE_TYPES:
                first_complex = r
            if first_primitive is None and r in _PRIMITIVE_TYPES:
                first_primitive = r
            if r == "URL":
                has_url = True

        if prop_name in _URL_FIRST_PROPERTIES and has_url:
            return _PRIMITIVE_PLACEHOLDERS["URL"]

        if first_complex and first_primitive:
            if first_primitive in _WEAK_PRIMITIVES:
                return _COMPLEX_TYPE_DEFAULTS.get(first_complex, {"@type": first_complex, "name": ""})
            else:
                return _PRIMITIVE_PLACEHOLDERS[first_primitive]
        elif first_complex:
            return _COMPLEX_TYPE_DEFAULTS.get(first_complex, {"@type": first_complex, "name": ""})
        elif first_primitive:
            return _PRIMITIVE_PLACEHOLDERS[first_primitive]
        return ""

    def _extract_entities(self, type_name: str, jsonld: dict, page) -> dict:
        """提取核心实体及其标识符，用于 GEO 实体链接。"""
        entities = {}

        if type_name == "Product":
            brand = jsonld.get("brand")
            brand_name = ""
            if isinstance(brand, dict):
                brand_name = brand.get("name", "")
            elif isinstance(brand, str):
                brand_name = brand
            if brand_name:
                entities["brand"] = {"name": brand_name}
            if jsonld.get("name"):
                entities["product"] = {"name": jsonld["name"]}
        elif type_name == "Article":
            if jsonld.get("author"):
                author = jsonld["author"]
                name = author.get("name", "") if isinstance(author, dict) else str(author)
                if name:
                    entities["author"] = {"name": name}
        elif type_name in ("Person", "Organization"):
            if jsonld.get("name"):
                entities["entity"] = {"name": jsonld["name"]}

        return entities

    def _score_schema(
        self, type_name: str, direct_props: List[Tuple[str, dict]], page
    ) -> Tuple[int, dict]:
        """自评分数：基于 Google 必需属性覆盖率和基本信息完整度。"""
        google = _GOOGLE_RICH_RESULTS.get(type_name, {"required": set(), "recommended": set()})
        required = google.get("required", set())
        score = 40  # 基础分

        # 基本信息
        title_bonus = 10 if page.title else 0
        desc_bonus = 10 if page.description else 0
        score += title_bonus + desc_bonus

        # 必需属性覆盖
        direct_names = {name for name, _ in direct_props}
        coverage = 0
        covered_count = 0
        if required:
            covered_count = len(required & direct_names)
            coverage = int(covered_count / len(required) * 40)
            score += min(40, coverage)

        score = min(100, score)
        score_details = {
            "base_score": 40,
            "title_bonus": title_bonus,
            "description_bonus": desc_bonus,
            "required_coverage": coverage,
            "required_total": len(required),
            "required_covered": covered_count,
            "reason": f"基础分 40 + 标题/描述 {title_bonus + desc_bonus} + 必需属性覆盖 {coverage}",
        }
        return score, score_details


# ------------------------------------------------------------------
# 工具函数
# ------------------------------------------------------------------

def _extract_name(value) -> str:
    if isinstance(value, str):
        for prefix in ("schema:", "https://schema.org/", "http://schema.org/"):
            if value.startswith(prefix):
                return value[len(prefix):]
        return value
    if isinstance(value, dict):
        return _extract_name(value.get("@id", ""))
    return str(value)


def _ensure_list(value) -> list:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]
