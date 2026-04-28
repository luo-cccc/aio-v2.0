"""
语义化内容优化器
================
三阶段 LLM 流水线：诊断 → 场景 → 改写。
"""

from typing import List

from ..lib.llm_client import LLMClient, sanitize_user_content
from ..lib.json_utils import parse_json_object, parse_json_array


class SemanticOptimizer:
    """
    语义化内容优化器，将参数堆砌型文案改写为场景体验型文案。
    """

    def __init__(self, llm: LLMClient):
        self._llm = llm

    async def optimize(self, text: str) -> dict:
        """
        对页面文本进行语义优化。

        返回标准模块结果格式:
            {"status": "success", "score": int, "optimized_text": str, "recommended_actions": [...]}
        """
        if len(text) < 50:
            return {
                "status": "skipped",
                "score": 0,
                "optimized_text": "",
                "score_details": {
                    "base_score": 0,
                    "reason": "页面文本过短（<50 字符），跳过语义优化",
                },
                "fallback": False,
                "errors": [],
                "recommended_actions": [
                    {
                        "action": "页面文本过短，无需语义优化",
                        "priority": "low",
                        "target_module": "semantic_optimizer",
                        "params": {"text_length": len(text), "threshold": 50},
                    }
                ],
            }

        # 阶段1：诊断
        try:
            diagnosis = await self._diagnose(text)
        except (RuntimeError, OSError, ValueError) as e:
            return {
                "status": "error",
                "score": 0,
                "optimized_text": "",
                "score_details": {
                    "base_score": 0,
                    "reason": f"语义诊断阶段失败: {e}",
                },
                "fallback": True,
                "errors": [str(e)],
                "recommended_actions": [
                    {
                        "action": f"语义诊断失败: {e}",
                        "priority": "medium",
                        "target_module": "semantic_optimizer",
                        "params": {"stage": "diagnose"},
                    }
                ],
            }

        # 阶段2：生成场景
        params = diagnosis.get("parameter_list", [])
        try:
            scenarios = await self._generate_scenarios(params) if params else []
        except (RuntimeError, OSError, ValueError):
            scenarios = []

        # 阶段3：改写
        try:
            rewrite = await self._rewrite(text, scenarios)
        except (RuntimeError, OSError, ValueError) as e:
            return {
                "status": "error",
                "score": 0,
                "optimized_text": "",
                "score_details": {
                    "base_score": 0,
                    "reason": f"文案改写阶段失败: {e}",
                },
                "fallback": True,
                "errors": [str(e)],
                "recommended_actions": [
                    {
                        "action": f"文案改写失败: {e}",
                        "priority": "medium",
                        "target_module": "semantic_optimizer",
                        "params": {"stage": "rewrite"},
                    }
                ],
            }

        optimized = rewrite.get("optimized_text", "")
        changes = rewrite.get("changes_summary", [])
        cite_worthy = rewrite.get("cite_worthy_snippets", [])
        semantic_topics = rewrite.get("semantic_topics", {})

        # 自评：基于机器不友好分数的改善程度 + GEO 加分
        try:
            unfriendly = float(diagnosis.get("machine_unfriendly_score", 50))
        except (TypeError, ValueError):
            unfriendly = 50
        geo_bonus = 10 if cite_worthy else 0
        score = max(0, min(100, 100 - unfriendly + (10 if changes else 0) + geo_bonus))
        score_details = {
            "base_score": 100 - unfriendly,
            "machine_unfriendly_score": unfriendly,
            "changes_bonus": 10 if changes else 0,
            "changes_count": len(changes),
            "cite_worthy_count": len(cite_worthy),
            "geo_bonus": geo_bonus,
            "reason": f"机器不友好分 {unfriendly}，改善加分 {10 if changes else 0}，GEO 加分 {geo_bonus}，最终 {score}",
        }

        actions = []
        if unfriendly > 60:
            actions.append({
                "action": f"原文机器不友好指数较高（{unfriendly}/100），建议采用优化版本",
                "priority": "high",
                "target_module": "semantic_optimizer",
                "params": {"machine_unfriendly_score": unfriendly},
            })
        for change in changes[:3]:
            actions.append({
                "action": f"语义优化: {change}",
                "priority": "medium",
                "target_module": "semantic_optimizer",
                "params": {"change": change},
            })
        if cite_worthy:
            actions.append({
                "action": f"植入 {len(cite_worthy)} 条高引用潜力片段，提升 AI 引擎引用概率",
                "priority": "medium",
                "target_module": "semantic_optimizer",
                "params": {"snippets": cite_worthy},
            })

        return {
            "status": "success",
            "score": score,
            "optimized_text": optimized,
            "diagnosis": diagnosis,
            "scenarios": scenarios,
            "cite_worthy_snippets": cite_worthy,
            "semantic_topics": semantic_topics,
            "score_details": score_details,
            "fallback": False,
            "errors": [],
            "recommended_actions": actions,
        }

    async def _diagnose(self, content: str) -> dict:
        safe_content = sanitize_user_content(content, max_len=1500)
        prompt = (
            "你是一位电商文案诊断专家。请分析以下商品描述文案，"
            '找出"只堆砌参数、缺乏场景体验描述"的问题。\n\n'
            f"原文：\n---\n{safe_content}\n---\n\n"
            "请返回 JSON，不要包含其他文字：\n"
            '{"machine_unfriendly_score": 0-100, '
            '"issues": [{"type": "问题类型", "example": "原文片段", "suggestion": "改进建议"}], '
            '"parameter_list": ["参数1: 值", "参数2: 值"]}'
        )
        text = await self._llm.chat(prompt)
        return parse_json_object(text)

    async def _generate_scenarios(self, parameter_list: List[str]) -> List[dict]:
        params_text = "\n".join(sanitize_user_content(p, max_len=200) for p in parameter_list)
        prompt = (
            "你是一位电商内容运营专家。基于以下商品参数，生成 3 个具体使用场景。\n"
            "每个场景必须包含：用户画像、使用情境、痛点、参数如何转化为体验描述。\n\n"
            f"参数：\n{params_text}\n\n"
            "要求：\n"
            "1. 场景要具体、真实，让用户能代入\n"
            "2. 将参数翻译为'用户能感知到的体验'\n"
            "3. 仅返回 JSON 数组，不要包含其他文字\n\n"
            '返回格式：[{"user_profile": "...", "scenario": "...", '
            '"pain_point": "...", "parameter_translation": "..."}]'
        )
        text = await self._llm.chat(prompt)
        result = parse_json_array(text)
        return result[:5] if isinstance(result, list) else []

    async def _rewrite(self, content: str, scenarios: List[dict]) -> dict:
        safe_content = sanitize_user_content(content, max_len=1500)
        scenarios_text = "\n".join(
            f"{i+1}. {sanitize_user_content(s.get('user_profile', ''), max_len=100)}"
            f"：{sanitize_user_content(s.get('scenario', ''), max_len=200)}"
            f" → {sanitize_user_content(s.get('parameter_translation', ''), max_len=200)}"
            for i, s in enumerate(scenarios)
        )
        prompt = (
            "你是一位资深电商文案策划。请改写以下商品描述文案，并同时生成 GEO 优化素材。\n\n"
            "要求：\n"
            "1. 保留所有原始参数（不能删除任何参数）\n"
            '2. 在每个参数前后添加场景体验描述，让读者感受到"这个参数对我有什么用"\n'
            '3. 让文案读起来像"懂用户的人在推荐"，而不是"说明书"\n'
            "4. 输出一段完整的、可直接用于商品详情页的文案\n"
            "5. 同时生成 3-5 句'可引用片段'——每句必须是一个独立、信息密度高的单句，"
            "方便 AI 搜索引擎直接摘取作为推荐理由\n"
            "6. 分析原文覆盖的主题，列出该商品类型用户最关心的 5-8 个主题，"
            "并标注哪些已覆盖、哪些缺失\n\n"
            f"原文：\n---\n{safe_content}\n---\n\n"
            f"场景参考：\n{scenarios_text}\n\n"
            "请返回 JSON，不要包含其他文字：\n"
            '{\n'
            '  "optimized_text": "优化后的完整文案",\n'
            '  "changes_summary": ["改动1说明", "改动2说明"],\n'
            '  "cite_worthy_snippets": [\n'
            '    "一句信息密度高的可引用单句",\n'
            '    "另一句可引用单句"\n'
            '  ],\n'
            '  "semantic_topics": {\n'
            '    "expected": ["主题1", "主题2", "主题3"],\n'
            '    "covered": ["主题1"],\n'
            '    "missing": ["主题2", "主题3"]\n'
            '  }\n'
            '}'
        )
        text = await self._llm.chat(prompt)
        return parse_json_object(text)
