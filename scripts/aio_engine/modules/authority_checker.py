"""
外部权威信号建设器
==================
分析商品的外部权威信号覆盖情况，生成健康度报告和策略建议。
支持中英文平台检测。
"""

from typing import List, Optional

from ..lib.llm_client import LLMClient, sanitize_user_content
from ..lib.json_utils import parse_json_object


class AuthorityChecker:
    """
    基于 LLM 知识分析外部权威信号覆盖情况。
    支持中英文平台，自动根据商品名称判断检测范围。
    """

    # 中文平台列表
    _CN_PLATFORMS = [
        "什么值得买", "知乎", "小红书", "B站", "微博",
        "中关村在线", "太平洋电脑网", "IT之家",
        "京东", "天猫",
    ]

    # 英文平台列表
    _EN_PLATFORMS = [
        "Amazon", "Best Buy", "Newegg", "Walmart",
        "YouTube", "Reddit", "Twitter/X", "TechCrunch",
        "The Verge", "CNET", "Wired", "Engadget",
        "Tom's Hardware", "PCMag", "GSMArena",
    ]

    def __init__(self, llm: LLMClient):
        self._llm = llm

    @staticmethod
    def _is_chinese(text: str) -> bool:
        """检测文本是否包含中文字符。"""
        if not text:
            return False
        return bool(__import__("re").search(r"[\u4e00-\u9fff]", text))

    async def check(self, title: str, keyword: str, lang: Optional[str] = None) -> dict:
        """
        分析外部权威信号。

        返回标准模块结果格式:
            {"status": "success", "score": int, "platform_coverage": [...], "strategy": [...], "recommended_actions": [...]}
        """
        product = title or keyword
        if not product or product == "general":
            return {
                "status": "skipped",
                "score": 0,
                "platform_coverage": [],
                "strategy": [],
                "score_details": {
                    "base_score": 0,
                    "reason": "页面标题或关键词不明确，跳过权威信号分析",
                },
                "fallback": False,
                "errors": [],
                "recommended_actions": [
                    {
                        "action": "页面标题或关键词不明确，无法分析权威信号",
                        "priority": "low",
                        "target_module": "page_parser",
                        "params": {"issue": "title_or_keyword_missing"},
                    }
                ],
            }

        safe_product = sanitize_user_content(product, max_len=50)

        # 自动检测语言，或显式指定
        is_cn = lang == "zh" or (lang is None and self._is_chinese(safe_product))

        if is_cn:
            platform_list = "、".join(self._CN_PLATFORMS)
            prompt = (
                f'你是一位电商品牌口碑分析师。请针对商品"{safe_product}"，'
                "生成一份'外部权威信号健康度报告'。\n\n"
                f"请基于你的知识，分析该商品在以下中文平台的评测覆盖情况：\n"
                f"{platform_list}\n\n"
                "返回 JSON，不要包含其他文字：\n"
                "{\n"
                '  "authority_score": 0-100,\n'
                '  "platform_coverage": [\n'
                '    {"platform": "平台名", "status": "已覆盖/部分覆盖/未覆盖", '
                '"review_count": "估计数量", "quality": "高/中/低", "recency": "最新评测时间", "notes": "补充说明"}\n'
                '  ],\n'
                '  "comment_analysis": {"positive_ratio": 0-100, "negative_ratio": 0-100, '
                '"neutral_ratio": 0-100, "semantic_density": "高/中/低", "density_note": "..."},\n'
                '  "recommendations": [{"action": "具体行动", "priority": "高/中/低", "rationale": "理由"}]\n'
                "}"
            )
        else:
            platform_list = ", ".join(self._EN_PLATFORMS)
            prompt = (
                f'You are an e-commerce brand reputation analyst. For the product "{safe_product}", '
                "generate an 'External Authority Signal Health Report'.\n\n"
                f"Based on your knowledge, analyze the review coverage on the following English platforms:\n"
                f"{platform_list}\n\n"
                "Return JSON only, no other text:\n"
                "{\n"
                '  "authority_score": 0-100,\n'
                '  "platform_coverage": [\n'
                '    {"platform": "Platform Name", "status": "covered/partially covered/not covered", '
                '"review_count": "estimated count", "quality": "high/medium/low", "recency": "latest review time", "notes": "additional notes"}\n'
                '  ],\n'
                '  "comment_analysis": {"positive_ratio": 0-100, "negative_ratio": 0-100, '
                '"neutral_ratio": 0-100, "semantic_density": "high/medium/low", "density_note": "..."},\n'
                '  "recommendations": [{"action": "specific action", "priority": "high/medium/low", "rationale": "reason"}]\n'
                "}"
            )

        try:
            text = await self._llm.chat(prompt)
            report = parse_json_object(text)
        except (RuntimeError, OSError, ValueError) as e:
            return {
                "status": "error",
                "score": 0,
                "platform_coverage": [],
                "strategy": [],
                "score_details": {
                    "base_score": 0,
                    "reason": f"LLM 调用失败: {e}",
                },
                "fallback": True,
                "errors": [str(e)],
                "recommended_actions": [
                    {
                        "action": f"权威信号分析失败: {e}",
                        "priority": "medium",
                        "target_module": "authority_checker",
                        "params": {"product": product},
                    }
                ],
            }

        score = report.get("authority_score", 0)
        coverage = report.get("platform_coverage", [])
        recommendations = report.get("recommendations", [])
        comment_analysis = report.get("comment_analysis", {})

        # 兼容中英文状态值
        covered = sum(
            1 for p in coverage
            if p.get("status") in ("已覆盖", "covered")
        )
        partial = sum(
            1 for p in coverage
            if p.get("status") in ("部分覆盖", "partially covered")
        )
        total_platforms = max(len(coverage), 1)
        coverage_rate = int((covered + partial * 0.5) / total_platforms * 100)

        score_details = {
            "base_score": score,
            "platform_count": len(coverage),
            "covered_platforms": covered,
            "partial_platforms": partial,
            "coverage_rate": coverage_rate,
            "positive_ratio": comment_analysis.get("positive_ratio", 0),
            "lang": "zh" if is_cn else "en",
            "reason": f"LLM 评估得分 {score}，平台覆盖率 {coverage_rate}%（{covered}/{total_platforms}）",
        }

        actions = []
        for rec in recommendations:
            actions.append({
                "action": rec.get("action", ""),
                "priority": rec.get("priority", "low"),
                "target_module": "authority_checker",
                "params": {"product": product, "rationale": rec.get("rationale", "")},
            })

        if score < 50:
            actions.append({
                "action": f"权威信号得分较低（{score}/100），建议加强第三方评测覆盖",
                "priority": "high",
                "target_module": "authority_checker",
                "params": {"product": product, "current_score": score, "target_score": 70},
            })

        return {
            "status": "success",
            "score": score,
            "platform_coverage": coverage,
            "strategy": recommendations,
            "score_details": score_details,
            "fallback": False,
            "errors": [],
            "recommended_actions": actions,
        }

