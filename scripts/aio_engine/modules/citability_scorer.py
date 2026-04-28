"""
AI 引用评分引擎 (Citability Scorer)
====================================
规则驱动的段落级引用评分，不依赖 LLM。
基于 geo-seo-claude 的 citability_scorer.py 算法，输出结构化 JSON。

输出格式:
    {
        "status": "success",
        "score": int,
        "score_details": {...},
        "blocks": [...],
        "page_metrics": {...},
        "recommended_actions": [...],
    }
"""

import re
from typing import List, Optional


class CitabilityScorer:
    """AI 引用评分器：分析内容块的可引用性。"""

    def analyze(self, content_blocks: List[dict]) -> dict:
        """
        分析所有内容块，返回页面级引用评分。

        Args:
            content_blocks: 来自 Crawler.extract_content_blocks() 的块列表
                [{"heading": str|None, "content": str, "word_count": int}, ...]

        Returns:
            标准模块结果格式，包含 blocks, page_metrics, recommended_actions
        """
        if not content_blocks:
            return {
                "status": "skipped",
                "score": 0,
                "score_details": {"reason": "无内容块可分析"},
                "fallback": False,
                "errors": [],
                "recommended_actions": [],
                "blocks": [],
                "page_metrics": {},
            }

        scored_blocks = []
        for block in content_blocks:
            score = self._score_block(block)
            scored_blocks.append(score)

        # 页面级指标
        if scored_blocks:
            avg_score = sum(b["total_score"] for b in scored_blocks) / len(scored_blocks)
            top_blocks = sorted(scored_blocks, key=lambda x: x["total_score"], reverse=True)[:5]
            bottom_blocks = sorted(scored_blocks, key=lambda x: x["total_score"])[:5]
            optimal_count = sum(1 for b in scored_blocks if 134 <= b["word_count"] <= 167)
            citation_ready = sum(1 for b in scored_blocks if b["total_score"] >= 70)
        else:
            avg_score = 0
            top_blocks = []
            bottom_blocks = []
            optimal_count = 0
            citation_ready = 0

        grade_dist = {"A": 0, "B": 0, "C": 0, "D": 0, "F": 0}
        for block in scored_blocks:
            grade_dist[block["grade"]] += 1

        page_score = round(avg_score)

        page_metrics = {
            "total_blocks": len(scored_blocks),
            "average_score": round(avg_score, 1),
            "optimal_length_passages": optimal_count,
            "citation_ready_blocks": citation_ready,
            "citation_ready_ratio": round(citation_ready / len(scored_blocks) * 100, 1) if scored_blocks else 0,
            "grade_distribution": grade_dist,
            "top_5": [{"heading": b["heading"], "score": b["total_score"], "grade": b["grade"]} for b in top_blocks],
            "bottom_5": [{"heading": b["heading"], "score": b["total_score"], "grade": b["grade"]} for b in bottom_blocks],
        }

        score_details = {
            "base_score": page_score,
            "reason": f"平均引用评分 {page_score}/100，{citation_ready} 个段落达到引用就绪标准",
            "total_blocks": len(scored_blocks),
            "citation_ready": citation_ready,
            "optimal_length": optimal_count,
        }

        actions = self._derive_actions(scored_blocks, page_metrics)

        return {
            "status": "success",
            "score": page_score,
            "score_details": score_details,
            "fallback": False,
            "errors": [],
            "recommended_actions": actions,
            "blocks": scored_blocks,
            "page_metrics": page_metrics,
        }

    def _score_block(self, block: dict) -> dict:
        """评分单个内容块，返回结构化结果。"""
        text = block.get("content", "")
        heading = block.get("heading")
        words = text.split()
        word_count = len(words)

        scores = {
            "answer_block_quality": 0,
            "self_containment": 0,
            "structural_readability": 0,
            "statistical_density": 0,
            "uniqueness_signals": 0,
        }

        # === 1. Answer Block Quality (30%) ===
        abq = 0
        definition_patterns = [
            r"\b\w+\s+is\s+(?:a|an|the)\s",
            r"\b\w+\s+refers?\s+to\s",
            r"\b\w+\s+means?\s",
            r"\b\w+\s+(?:can be |are )?defined\s+as\s",
            r"\bin\s+(?:simple|other)\s+(?:terms|words)\s*,",
        ]
        for pattern in definition_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                abq += 15
                break

        first_60 = " ".join(words[:60])
        if any(re.search(p, first_60, re.IGNORECASE) for p in [
            r"\b(?:is|are|was|were|means?|refers?)\b",
            r"\d+%",
            r"\$[\d,]+",
            r"\d+\s+(?:million|billion|thousand)",
        ]):
            abq += 15

        if heading and heading.endswith("?"):
            abq += 10

        sentences = re.split(r"[.!?]+", text)
        short_clear = sum(1 for s in sentences if 5 <= len(s.split()) <= 25)
        if sentences:
            abq += int((short_clear / len(sentences)) * 10)

        if re.search(
            r"(?:according to|research shows|studies? (?:show|indicate|suggest|found)|data (?:shows|indicates|suggests))",
            text, re.IGNORECASE,
        ):
            abq += 10

        scores["answer_block_quality"] = min(abq, 30)

        # === 2. Self-Containment (25%) ===
        sc = 0
        if 134 <= word_count <= 167:
            sc += 10
        elif 100 <= word_count <= 200:
            sc += 7
        elif 80 <= word_count <= 250:
            sc += 4
        elif word_count < 30 or word_count > 400:
            sc += 0
        else:
            sc += 2

        pronoun_count = len(re.findall(
            r"\b(?:it|they|them|their|this|that|these|those|he|she|his|her)\b",
            text, re.IGNORECASE,
        ))
        if word_count > 0:
            pronoun_ratio = pronoun_count / word_count
            if pronoun_ratio < 0.02:
                sc += 8
            elif pronoun_ratio < 0.04:
                sc += 5
            elif pronoun_ratio < 0.06:
                sc += 3

        proper_nouns = len(re.findall(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b", text))
        if proper_nouns >= 3:
            sc += 7
        elif proper_nouns >= 1:
            sc += 4

        scores["self_containment"] = min(sc, 25)

        # === 3. Structural Readability (20%) ===
        sr = 0
        if sentences:
            avg_sent_len = word_count / len(sentences)
            if 10 <= avg_sent_len <= 20:
                sr += 8
            elif 8 <= avg_sent_len <= 25:
                sr += 5
            else:
                sr += 2

        if re.search(r"(?:first|second|third|finally|additionally|moreover|furthermore)", text, re.IGNORECASE):
            sr += 4
        if re.search(r"(?:\d+[\.\)]\s|\b(?:step|tip|point)\s+\d+)", text, re.IGNORECASE):
            sr += 4
        if "\n" in text:
            sr += 4

        scores["structural_readability"] = min(sr, 20)

        # === 4. Statistical Density (15%) ===
        sd = 0
        pct_count = len(re.findall(r"\d+(?:\.\d+)?%", text))
        sd += min(pct_count * 3, 6)

        dollar_count = len(re.findall(r"\$[\d,]+(?:\.\d+)?(?:\s*(?:million|billion|M|B|K))?", text))
        sd += min(dollar_count * 3, 5)

        number_count = len(re.findall(
            r"\b\d+(?:,\d{3})*(?:\.\d+)?\s+(?:users|customers|pages|sites|companies|businesses|people|percent|times|x\b)",
            text, re.IGNORECASE,
        ))
        sd += min(number_count * 2, 4)

        year_count = len(re.findall(r"\b20(?:2[3-6]|1\d)\b", text))
        if year_count > 0:
            sd += 2

        source_patterns = [
            r"(?:according to|per|from|by)\s+[A-Z]",
            r"(?:Gartner|Forrester|McKinsey|Harvard|Stanford|MIT|Google|Microsoft|OpenAI|Anthropic)",
            r"\([A-Z][a-z]+(?:\s+\d{4})?\)",
        ]
        for pattern in source_patterns:
            if re.search(pattern, text):
                sd += 2
                break

        scores["statistical_density"] = min(sd, 15)

        # === 5. Uniqueness Signals (10%) ===
        us = 0
        if re.search(
            r"(?:our (?:research|study|data|analysis|survey|findings)|we (?:found|discovered|analyzed|surveyed|measured))",
            text, re.IGNORECASE,
        ):
            us += 5
        if re.search(
            r"(?:case study|for example|for instance|in practice|real-world|hands-on)",
            text, re.IGNORECASE,
        ):
            us += 3
        if re.search(r"(?:using|with|via|through)\s+[A-Z][a-z]+", text):
            us += 2

        scores["uniqueness_signals"] = min(us, 10)

        # === Total ===
        total = sum(scores.values())

        if total >= 80:
            grade, label = "A", "Highly Citable"
        elif total >= 65:
            grade, label = "B", "Good Citability"
        elif total >= 50:
            grade, label = "C", "Moderate Citability"
        elif total >= 35:
            grade, label = "D", "Low Citability"
        else:
            grade, label = "F", "Poor Citability"

        return {
            "heading": heading,
            "word_count": word_count,
            "total_score": total,
            "grade": grade,
            "label": label,
            "breakdown": scores,
            "preview": " ".join(words[:30]) + ("..." if word_count > 30 else ""),
        }

    def _derive_actions(self, blocks: List[dict], metrics: dict) -> List[dict]:
        """根据评分结果生成改进行动。"""
        actions = []
        avg = metrics.get("average_score", 0)
        optimal = metrics.get("optimal_length_passages", 0)
        ready = metrics.get("citation_ready_blocks", 0)
        total = metrics.get("total_blocks", 0)

        if avg < 50:
            actions.append({
                "action": "页面整体引用评分较低，建议重构内容结构，添加定义式开头段落",
                "priority": "high",
                "target_module": "citability_scorer",
                "params": {"issue": "low_average_score", "current": avg},
            })

        if optimal == 0 and total > 0:
            actions.append({
                "action": "无段落处于最优引用长度（134-167词），建议调整段落长度",
                "priority": "medium",
                "target_module": "citability_scorer",
                "params": {"issue": "no_optimal_length", "target_range": "134-167 words"},
            })

        if ready < total * 0.3 and total > 0:
            actions.append({
                "action": f"引用就绪段落比例过低（{ready}/{total}），建议增加事实数据、定义式语句和独立段落",
                "priority": "high",
                "target_module": "citability_scorer",
                "params": {"issue": "low_citation_ready_ratio", "ready": ready, "total": total},
            })

        # 为最低分段落生成具体建议
        bottom = sorted(blocks, key=lambda x: x["total_score"])[:3]
        for b in bottom:
            if b["total_score"] < 40:
                actions.append({
                    "action": f"段落 '{b['heading'] or '无标题'}' 引用评分仅 {b['total_score']} 分，建议重写为自包含的定义式段落",
                    "priority": "medium",
                    "target_module": "citability_scorer",
                    "params": {"heading": b["heading"], "score": b["total_score"], "grade": b["grade"]},
                })

        return actions
