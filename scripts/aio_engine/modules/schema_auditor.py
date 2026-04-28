"""
Schema.org 审计器 (Schema Auditor)
==================================
审计页面现有 JSON-LD structured data，检测缺失和错误。
基于 geo-seo-claude 的 geo-schema 技能和 schema 模板。

输出格式:
    {
        "status": "success",
        "score": int,
        "score_details": {...},
        "schemas_found": [...],
        "issues": [...],
        "suggestions": [...],
        "recommended_actions": [...],
    }
"""

import json
import re
from typing import Dict, List, Optional


class SchemaAuditor:
    """Schema.org 结构化数据审计器。"""

    # 关键 Schema 类型优先级
    _PRIORITY_SCHEMAS = {
        "Organization": 15,
        "WebSite": 10,
        "WebPage": 10,
        "Article": 15,
        "Product": 15,
        "LocalBusiness": 15,
        "Person": 10,
        "BreadcrumbList": 5,
        "FAQPage": 5,
        "VideoObject": 5,
        "ImageObject": 3,
    }

    # 关键属性检查
    _CRITICAL_PROPS = {
        "Organization": ["name", "url", "logo", "sameAs"],
        "WebSite": ["name", "url", "potentialAction"],
        "Article": ["headline", "author", "datePublished", "publisher"],
        "Product": ["name", "offers", "aggregateRating", "review"],
        "LocalBusiness": ["name", "address", "telephone", "openingHoursSpecification"],
        "Person": ["name", "jobTitle", "sameAs", "worksFor"],
    }

    def audit(self, json_ld_scripts: List[str], page_type: str = "") -> dict:
        """
        审计页面 JSON-LD structured data。

        Args:
            json_ld_scripts: 页面中 <script type="application/ld+json"> 的内容列表
            page_type: 推断的页面类型（WebPage/Product/Article 等）

        Returns:
            标准模块结果格式
        """
        if not json_ld_scripts:
            return {
                "status": "success",
                "score": 0,
                "score_details": {"reason": "未检测到 JSON-LD structured data"},
                "fallback": False,
                "errors": [],
                "schemas_found": [],
                "issues": [{"severity": "critical", "message": "页面缺少 JSON-LD"}],
                "suggestions": ["添加基础 Organization + WebSite Schema"],
                "recommended_actions": [
                    {
                        "action": "添加 Organization + WebSite JSON-LD",
                        "priority": "high",
                        "target_module": "schema_generator",
                    }
                ],
            }

        schemas_found = []
        all_issues = []
        all_suggestions = []

        for script in json_ld_scripts:
            try:
                data = json.loads(script)
                if isinstance(data, list):
                    for item in data:
                        parsed = self._parse_schema(item)
                        if parsed:
                            schemas_found.append(parsed)
                else:
                    parsed = self._parse_schema(data)
                    if parsed:
                        schemas_found.append(parsed)
            except json.JSONDecodeError as e:
                all_issues.append({
                    "severity": "error",
                    "message": f"JSON-LD 解析失败: {str(e)[:80]}",
                })

        # 检查每个 schema 的完整性
        for schema in schemas_found:
            schema_type = schema.get("type", "")
            issues, suggestions = self._check_schema_completeness(schema_type, schema)
            all_issues.extend(issues)
            all_suggestions.extend(suggestions)

        # 检查 sameAs（GEO 关键信号）
        same_as_issues = self._check_same_as(schemas_found)
        all_issues.extend(same_as_issues)

        score, score_details = self._calculate_score(schemas_found, all_issues)
        actions = self._derive_actions(schemas_found, all_issues, page_type)

        return {
            "status": "success",
            "score": score,
            "score_details": score_details,
            "fallback": False,
            "errors": [],
            "schemas_found": schemas_found,
            "issues": all_issues,
            "suggestions": all_suggestions,
            "recommended_actions": actions,
        }

    def _parse_schema(self, data: dict) -> Optional[dict]:
        """解析单个 schema 对象。"""
        if not isinstance(data, dict):
            return None

        schema_type = data.get("@type", "")
        if isinstance(schema_type, list):
            schema_type = schema_type[0] if schema_type else ""

        if not schema_type:
            return None

        return {
            "type": schema_type,
            "context": data.get("@context", ""),
            "id": data.get("@id", ""),
            "has_sameAs": "sameAs" in data and bool(data["sameAs"]),
            "key_props": list(data.keys()),
        }

    def _check_schema_completeness(self, schema_type: str, schema: dict) -> tuple:
        """检查 schema 关键属性完整性。"""
        issues = []
        suggestions = []

        required = self._CRITICAL_PROPS.get(schema_type, [])
        if not required:
            return issues, suggestions

        key_props = schema.get("key_props", [])
        missing = [p for p in required if p not in key_props]

        if missing:
            issues.append({
                "severity": "warning",
                "schema_type": schema_type,
                "message": f"{schema_type} 缺少关键属性: {', '.join(missing)}",
            })
            suggestions.append(
                f"为 {schema_type} 添加: {', '.join(missing)}"
            )

        return issues, suggestions

    def _check_same_as(self, schemas_found: List[dict]) -> List[dict]:
        """检查 sameAs 链接（GEO 实体识别关键）。"""
        issues = []

        org_schemas = [s for s in schemas_found if s.get("type") in ("Organization", "LocalBusiness")]
        person_schemas = [s for s in schemas_found if s.get("type") == "Person"]

        for schema in org_schemas + person_schemas:
            if not schema.get("has_sameAs"):
                issues.append({
                    "severity": "warning",
                    "schema_type": schema.get("type"),
                    "message": (
                        f"{schema.get('type')} 缺少 sameAs 链接。"
                        "sameAs 是 GEO 实体识别的最强信号。"
                    ),
                })

        return issues

    def _calculate_score(self, schemas_found: List[dict], issues: List[dict]) -> tuple:
        """计算 schema 质量评分。"""
        score = 0
        details = {}

        found_types = {s.get("type", "") for s in schemas_found}

        for schema_type, points in self._PRIORITY_SCHEMAS.items():
            if schema_type in found_types:
                score += points
                details[schema_type] = "present"
            else:
                details[schema_type] = "missing"

        # 扣分
        critical_count = sum(1 for i in issues if i.get("severity") == "critical")
        error_count = sum(1 for i in issues if i.get("severity") == "error")
        warning_count = sum(1 for i in issues if i.get("severity") == "warning")

        score -= critical_count * 15
        score -= error_count * 10
        score -= warning_count * 3

        details["critical_issues"] = critical_count
        details["error_issues"] = error_count
        details["warning_issues"] = warning_count
        details["schema_count"] = len(schemas_found)
        details["unique_types"] = list(found_types)

        return max(0, min(score, 100)), details

    def _derive_actions(self, schemas_found: List[dict], issues: List[dict], page_type: str) -> List[dict]:
        """生成改进建议。"""
        actions = []
        found_types = {s.get("type", "") for s in schemas_found}

        if "Organization" not in found_types:
            actions.append({
                "action": "添加 Organization Schema（含 sameAs 链接到 Wikipedia/Wikidata/LinkedIn）",
                "priority": "high",
                "target_module": "schema_generator",
                "params": {"schema_type": "Organization"},
            })

        if "WebSite" not in found_types:
            actions.append({
                "action": "添加 WebSite Schema（含 SearchAction）",
                "priority": "medium",
                "target_module": "schema_generator",
                "params": {"schema_type": "WebSite"},
            })

        if page_type == "Product" and "Product" not in found_types:
            actions.append({
                "action": "添加 Product Schema（含 offers/aggregateRating/review）",
                "priority": "high",
                "target_module": "schema_generator",
                "params": {"schema_type": "Product"},
            })

        if page_type == "Article" and "Article" not in found_types:
            actions.append({
                "action": "添加 Article Schema（含 author/publisher/datePublished）",
                "priority": "high",
                "target_module": "schema_generator",
                "params": {"schema_type": "Article"},
            })

        # sameAs 缺失
        same_as_missing = any(
            "sameAs" in i.get("message", "") for i in issues
        )
        if same_as_missing:
            actions.append({
                "action": "为 Organization/Person 添加 sameAs 属性（Wikipedia, Wikidata, LinkedIn, Twitter）",
                "priority": "high",
                "target_module": "schema_generator",
                "params": {"property": "sameAs"},
            })

        return actions
