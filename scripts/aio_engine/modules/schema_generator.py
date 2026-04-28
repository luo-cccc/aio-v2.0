"""
Schema.org 结构化数据生成器 (Article-Only)
=============================================
专为文章专栏生成 Article JSON-LD 代码框架。
v2.0.0: 移除类型推断，直接生成 Article Schema。
"""

from typing import Dict, List

from ..lib.llm_client import LLMClient, sanitize_user_content
from ..lib.json_utils import parse_json_object


# Google 富结果 — Article 推荐属性
_ARTICLE_REQUIRED = {"headline", "image", "datePublished", "author"}
_ARTICLE_RECOMMENDED = {"dateModified", "publisher", "description", "url", "mainEntityOfPage"}


class SchemaGenerator:
    """Article 专用 Schema 生成器。"""

    def __init__(self, llm: LLMClient):
        self._llm = llm
        self._type_name = "Article"

    def generate(self, page) -> dict:
        """
        生成 Article JSON-LD 框架。

        Returns:
            标准模块结果格式
        """
        jsonld = self._build_article_jsonld(page)
        score, score_details = self._score_article(page)
        entities = self._extract_article_entities(jsonld)
        actions = self._derive_actions(jsonld, entities, page)

        return {
            "status": "success",
            "score": score,
            "schemas": {"Article": jsonld},
            "entities": entities,
            "score_details": score_details,
            "fallback": False,
            "errors": [],
            "recommended_actions": actions,
        }

    def _build_article_jsonld(self, page) -> dict:
        """构建 Article JSON-LD。"""
        result = {
            "@context": "https://schema.org",
            "@type": "Article",
            "headline": page.title or "",
            "description": page.description or "",
            "url": page.url,
        }

        # 自动填充字数
        if hasattr(page, "text") and page.text:
            wc = len(page.text.split())
            result["wordCount"] = wc

        return result

    def _extract_article_entities(self, jsonld: dict) -> dict:
        """提取文章实体。"""
        entities = {}
        if jsonld.get("headline"):
            entities["article"] = {"name": jsonld["headline"]}
        author = jsonld.get("author")
        if author:
            name = author.get("name", "") if isinstance(author, dict) else str(author)
            if name:
                entities["author"] = {"name": name}
        return entities

    def _score_article(self, page) -> tuple:
        """评分：基于 Google Article 必需属性覆盖率。"""
        score = 40  # 基础分

        # 基本信息
        title_bonus = 10 if page.title else 0
        desc_bonus = 10 if page.description else 0
        score += title_bonus + desc_bonus

        # 必需属性覆盖（基于本地生成的 JSON-LD）
        covered = set()
        if page.title:
            covered.add("headline")
        if page.description:
            covered.add("description")
        covered.add("url")

        coverage = int(len(covered & _ARTICLE_REQUIRED) / len(_ARTICLE_REQUIRED) * 40)
        score += min(40, coverage)
        score = min(100, score)

        score_details = {
            "base_score": 40,
            "title_bonus": title_bonus,
            "description_bonus": desc_bonus,
            "required_coverage": coverage,
            "required_total": len(_ARTICLE_REQUIRED),
            "required_covered": len(covered & _ARTICLE_REQUIRED),
            "reason": f"基础分 40 + 标题/描述 {title_bonus + desc_bonus} + 必需属性覆盖 {coverage}",
        }
        return score, score_details

    def _derive_actions(self, jsonld: dict, entities: dict, page) -> List[dict]:
        """生成改进行动。"""
        actions = []

        # 检查必需属性
        for req in _ARTICLE_REQUIRED:
            if req not in jsonld or not jsonld[req]:
                actions.append({
                    "action": f"为 Article 添加必需属性: {req}",
                    "priority": "high",
                    "target_module": "schema_generator",
                    "params": {"type_name": "Article", "property": req},
                })

        # 检查 sameAs
        if not jsonld.get("sameAs"):
            actions.append({
                "action": "为 Article 添加 sameAs 链接（如作者主页、出版机构）以提升实体识别度",
                "priority": "medium",
                "target_module": "schema_generator",
                "params": {"type_name": "Article", "entities": entities},
            })

        return actions

    async def _generate_llm_fallback(self, page) -> dict:
        """LLM fallback：让 LLM 直接生成 Article JSON-LD。"""
        safe_title = sanitize_user_content(page.title or "", max_len=200)
        safe_desc = sanitize_user_content(page.description or "", max_len=300)
        prompt = (
            "请为 Schema.org Article 类型生成一个 JSON-LD 代码框架。\n"
            f"页面标题: {safe_title}\n"
            f"页面描述: {safe_desc}\n"
            "仅返回 JSON 对象，不要解释。"
        )
        try:
            text = await self._llm.chat(prompt)
            schema = parse_json_object(text)
            return {
                "status": "success",
                "score": 50,
                "schemas": {"Article": schema},
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
                        "action": "验证 Article 的 JSON-LD 结构是否符合 Schema.org 规范",
                        "priority": "medium",
                        "target_module": "schema_generator",
                        "params": {"type_name": "Article"},
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
                    "reason": f"LLM fallback 失败: {e}",
                },
                "fallback": True,
                "errors": [str(e)],
                "recommended_actions": [
                    {
                        "action": "无法生成 Article Schema，请手动检查",
                        "priority": "high",
                        "target_module": "schema_generator",
                        "params": {"type_name": "Article"},
                    }
                ],
            }
