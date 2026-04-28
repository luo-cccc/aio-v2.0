"""
FAQ 内容自动生成器
==================
基于关键词生成高频问题及答案，输出 HTML 片段。
"""

from typing import List

from ..lib.llm_client import LLMClient, sanitize_user_content
from ..lib.json_utils import parse_json_array


class FAQGenerator:
    """
    围绕关键词自动生成 FAQ 内容。
    """

    def __init__(self, llm: LLMClient):
        self._llm = llm

    async def generate(self, keyword: str, count: int = 10) -> dict:
        """
        生成 FAQ 内容。

        返回标准模块结果格式:
            {"status": "success", "score": int, "faq_html": str, "recommended_actions": [...]}
        """
        if not keyword or keyword == "general":
            return {
                "status": "skipped",
                "score": 0,
                "faq_html": "",
                "score_details": {
                    "base_score": 0,
                    "reason": "关键词为空或 general，跳过 FAQ 生成",
                },
                "fallback": False,
                "errors": [],
                "recommended_actions": [
                    {
                        "action": "页面关键词不明确，无法生成 FAQ",
                        "priority": "low",
                        "target_module": "page_parser",
                        "params": {"issue": "keyword_missing"},
                    }
                ],
            }

        safe_keyword = sanitize_user_content(keyword, max_len=100)
        prompt = (
            f'你是一个电商内容运营专家。请围绕关键词"{safe_keyword}"，'
            f"从用户实际搜索的角度生成 {count} 个高频问题。\n\n"
            "要求：\n"
            "1. 问题覆盖：选购建议、使用场景、功能对比、常见问题、保养维护等维度\n"
            "2. 每个问题配 150-300 字的专业答案，内容要有实用价值\n"
            "3. 每个答案末尾补充一句'核心建议'\n"
            "4. 仅返回 JSON 数组，不要包含其他文字\n\n"
            "返回格式：\n"
            '[{"question": "问题文本", "answer": "答案正文", "key_takeaway": "一句话核心建议"}]'
        )

        try:
            text = await self._llm.chat(prompt)
            faqs = parse_json_array(text)
        except (RuntimeError, OSError, ValueError) as e:
            return {
                "status": "error",
                "score": 0,
                "faq_html": "",
                "score_details": {
                    "base_score": 0,
                    "reason": f"LLM 调用失败: {e}",
                },
                "fallback": True,
                "errors": [str(e)],
                "recommended_actions": [
                    {
                        "action": f"FAQ 生成失败: {e}",
                        "priority": "medium",
                        "target_module": "faq_generator",
                        "params": {"keyword": keyword, "count": count},
                    }
                ],
            }

        valid_faqs = []
        for item in faqs:
            if isinstance(item, dict) and item.get("question") and item.get("answer"):
                valid_faqs.append(item)

        if not valid_faqs:
            return {
                "status": "error",
                "score": 0,
                "faq_html": "",
                "score_details": {
                    "base_score": 0,
                    "reason": "LLM 返回的 FAQ 格式不正确或为空",
                },
                "fallback": True,
                "errors": ["LLM 返回的 FAQ 格式不正确或为空"],
                "recommended_actions": [
                    {
                        "action": "LLM 返回的 FAQ 格式不正确",
                        "priority": "medium",
                        "target_module": "faq_generator",
                        "params": {"keyword": keyword, "count": count},
                    }
                ],
            }

        valid_faqs = valid_faqs[:count]
        html = self._format_html(valid_faqs, keyword)

        # 自评：基于问题覆盖维度数量
        score = min(100, 40 + len(faqs) * 5)
        score_details = {
            "base_score": 40,
            "faq_count": len(faqs),
            "faq_count_bonus": len(faqs) * 5,
            "reason": f"基础分 40 + FAQ 数量 {len(faqs)} × 5 = {score}",
        }

        actions = []
        if len(faqs) < 5:
            actions.append({
                "action": f"FAQ 数量较少（{len(faqs)} 条），建议补充到 10 条以上",
                "priority": "medium",
                "target_module": "faq_generator",
                "params": {"keyword": keyword, "current_count": len(faqs), "target_count": 10},
            })

        return {
            "status": "success",
            "score": score,
            "faq_html": html,
            "score_details": score_details,
            "fallback": False,
            "errors": [],
            "recommended_actions": actions,
        }

    @staticmethod
    def _format_html(faqs: List[dict], keyword: str) -> str:
        """将 FAQ 数组格式化为 HTML。"""
        lines = [
            f'<div class="faq-section" data-keyword="{_escape_html(keyword)}">',
            "",
        ]
        for item in faqs:
            if not isinstance(item, dict):
                continue
            q = _escape_html(item.get("question", ""))
            a = _escape_html(item.get("answer", ""))
            t = _escape_html(item.get("key_takeaway", ""))
            lines.append(f"  <h3>{q}</h3>")
            lines.append(f"  <p>{a}</p>")
            if t:
                lines.append(f"  <p><strong>核心建议：</strong>{t}</p>")
            lines.append("")
        lines.append("</div>")
        return "\n".join(lines)


def _escape_html(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )
