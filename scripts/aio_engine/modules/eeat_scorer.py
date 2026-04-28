"""
E-E-A-T 内容评分器 (E-E-A-T Scorer)
====================================
4 维度内容质量评分：Experience, Expertise, Authoritativeness, Trustworthiness。
基于 geo-seo-claude 的 geo-content SKILL。

输出格式:
    {
        "status": "success",
        "score": int,
        "score_details": {...},
        "dimensions": {...},
        "content_quality": {...},
        "recommended_actions": [...],
    }
"""

import re
from typing import Dict, List


class EEATScorer:
    """E-E-A-T 内容质量评分器。"""

    def analyze(
        self,
        text: str,
        html: str,
        headings: List[dict],
        content_blocks: List[dict],
        has_author: bool,
        author_name: str,
        has_dates: bool,
        has_reviews: bool,
        word_count: int,
    ) -> dict:
        """
        基于页面内容评分 E-E-A-T。

        Args:
            text: 去标签后的纯文本
            html: 原始 HTML
            headings: heading 列表
            content_blocks: 内容块列表
            has_author: 是否有作者信息
            author_name: 作者名称
            has_dates: 是否有日期
            has_reviews: 是否有评价
            word_count: 总字数

        Returns:
            标准模块结果格式
        """
        safe_html = html or ""
        safe_text = text or ""
        dimensions = {
            "experience": self._score_experience(safe_text, content_blocks),
            "expertise": self._score_expertise(safe_text, has_author, author_name),
            "authoritativeness": self._score_authoritativeness(safe_text, headings),
            "trustworthiness": self._score_trustworthiness(safe_html, has_reviews, has_dates),
        }

        total = sum(d["score"] for d in dimensions.values())
        # 封顶 100
        score = min(total, 100)

        score_details = {
            "total_raw": total,
            "dimensions": {k: v["score"] for k, v in dimensions.items()},
        }

        content_quality = self._assess_content_quality(text, word_count, headings)
        actions = self._derive_actions(dimensions, content_quality)

        return {
            "status": "success",
            "score": score,
            "score_details": score_details,
            "fallback": False,
            "errors": [],
            "dimensions": dimensions,
            "content_quality": content_quality,
            "recommended_actions": actions,
        }

    def _score_experience(self, text: str, content_blocks: List[dict]) -> dict:
        """评分 Experience（25 pts）— 第一手经验。"""
        score = 0
        signals = {}

        # 第一人称叙述 (5 pts)
        first_person = len(re.findall(r"\b(I|we|our|my|me|us|mine|ours)\b", text, re.I))
        fp_score = 5 if first_person >= 3 else (3 if first_person >= 1 else 0)
        score += fp_score
        signals["first_person"] = fp_score

        # 原创研究/数据 (5 pts)
        original_data = bool(
            re.search(r"(survey|study|research|benchmark|data collected|we analyzed|we tested)", text, re.I)
        )
        od_score = 5 if original_data else 0
        score += od_score
        signals["original_data"] = od_score

        # 案例研究 (4 pts)
        case_study = bool(re.search(r"(case study|case-study|example: |for example, |instance)", text, re.I))
        cs_score = 4 if case_study else 0
        score += cs_score
        signals["case_study"] = cs_score

        # 截图/证据提及 (3 pts)
        evidence = bool(re.search(r"(screenshot|figure \d|image \d|as shown|see below)", text, re.I))
        ev_score = 3 if evidence else 0
        score += ev_score
        signals["evidence"] = ev_score

        # 具体示例 (4 pts)
        specific = len(re.findall(r"\b(in 20\d\d|January|February|March|April|May|June|July|August|September|October|November|December)\b", text))
        sp_score = 4 if specific >= 2 else (2 if specific >= 1 else 0)
        score += sp_score
        signals["specific_examples"] = sp_score

        # 过程演示 (4 pts)
        process = bool(re.search(r"(step \d|first, |second, |third, |finally, |next, )", text, re.I))
        pr_score = 4 if process else 0
        score += pr_score
        signals["process_demo"] = pr_score

        return {"score": min(score, 25), "max": 25, "signals": signals}

    def _score_expertise(self, text: str, has_author: bool, author_name: str) -> dict:
        """评分 Expertise（25 pts）— 专业知识深度。"""
        score = 0
        signals = {}

        # 作者资质 (5 pts)
        au_score = 5 if has_author else 0
        score += au_score
        signals["author_credentials"] = au_score

        # 技术深度 (5 pts)
        technical_terms = len(re.findall(
            r"\b(API|JSON|HTML|CSS|SEO|CTR|ROI|algorithm|framework|methodology|architecture)\b",
            text
        ))
        td_score = 5 if technical_terms >= 3 else (3 if technical_terms >= 1 else 0)
        score += td_score
        signals["technical_depth"] = td_score

        # 方法论说明 (4 pts)
        methodology = bool(re.search(r"(method|approach|process|how we|methodology|framework)", text, re.I))
        meth_score = 4 if methodology else 0
        score += meth_score
        signals["methodology"] = meth_score

        # 数据支撑 (4 pts)
        data_backed = len(re.findall(r"\b\d+(\.\d+)?%|\$\d+|\d+ (users|customers|visits|clicks|sales)\b", text))
        db_score = 4 if data_backed >= 2 else (2 if data_backed >= 1 else 0)
        score += db_score
        signals["data_backed"] = db_score

        # 行业术语正确使用 (3 pts)
        jargon = len(re.findall(r"\b(Schema\.org|JSON-LD|canonical|hreflang|noindex|sitemap|backlink)\b", text, re.I))
        ja_score = 3 if jargon >= 2 else (1 if jargon >= 1 else 0)
        score += ja_score
        signals["jargon"] = ja_score

        # 作者页面 (4 pts)
        ap_score = 4 if has_author and author_name else 0
        score += ap_score
        signals["author_page"] = ap_score

        return {"score": min(score, 25), "max": 25, "signals": signals}

    def _score_authoritativeness(self, text: str, headings: List[dict]) -> dict:
        """评分 Authoritativeness（25 pts）— 外部认可。"""
        score = 0
        signals = {}

        # 入站引用 (5 pts)
        citations = len(re.findall(r"(according to|cited by|source:|referenced in|as reported by)", text, re.I))
        ci_score = 5 if citations >= 2 else (3 if citations >= 1 else 0)
        score += ci_score
        signals["inbound_citations"] = ci_score

        # 媒体提及 (4 pts)
        media = bool(re.search(r"(featured in|mentioned in|quoted in|interviewed by|press coverage)", text, re.I))
        me_score = 4 if media else 0
        score += me_score
        signals["media_mentions"] = me_score

        # 奖项 (3 pts)
        awards = bool(re.search(r"(award|winner|recognized|honored|top \d|best \d+)", text, re.I))
        aw_score = 3 if awards else 0
        score += aw_score
        signals["awards"] = aw_score

        # 演讲/会议 (3 pts)
        speaking = bool(re.search(r"(speaker|conference|keynote|presented at|talk at)", text, re.I))
        sp_score = 3 if speaking else 0
        score += sp_score
        signals["speaking"] = sp_score

        # 出版物 (4 pts)
        published = bool(re.search(r"(published|peer-reviewed|journal|paper|research article)", text, re.I))
        pu_score = 4 if published else 0
        score += pu_score
        signals["publications"] = pu_score

        # 主题覆盖深度 (3 pts)
        topic_depth = len(headings)
        td_score = 3 if topic_depth >= 5 else (1 if topic_depth >= 3 else 0)
        score += td_score
        signals["topic_depth"] = td_score

        # Wikipedia (3 pts)
        wiki = bool(re.search(r"wikipedia", text, re.I))
        wi_score = 3 if wiki else 0
        score += wi_score
        signals["wikipedia"] = wi_score

        return {"score": min(score, 25), "max": 25, "signals": signals}

    def _score_trustworthiness(self, html: str, has_reviews: bool, has_dates: bool) -> dict:
        """评分 Trustworthiness（25 pts）— 可信度。"""
        score = 0
        signals = {}

        # 联系信息 (4 pts)
        contact = bool(re.search(r"(contact|email|phone|address|@\w+\.\w+)", html, re.I))
        co_score = 4 if contact else 0
        score += co_score
        signals["contact_info"] = co_score

        # 隐私政策 (2 pts)
        privacy = bool(re.search(r"privacy", html, re.I))
        pr_score = 2 if privacy else 0
        score += pr_score
        signals["privacy_policy"] = pr_score

        # 服务条款 (1 pt)
        tos = bool(re.search(r"(terms|tos|terms of service)", html, re.I))
        tos_score = 1 if tos else 0
        score += tos_score
        signals["terms_of_service"] = tos_score

        # HTTPS (2 pts)
        https = bool(re.search(r"https://", html))
        hs_score = 2 if https else 0
        score += hs_score
        signals["https"] = hs_score

        # 编辑标准 (3 pts)
        editorial = bool(re.search(r"(editorial|correction|update|revised|fact-check)", html, re.I))
        ed_score = 3 if editorial else 0
        score += ed_score
        signals["editorial_standards"] = ed_score

        # 商业模式透明 (3 pts)
        transparent = bool(re.search(r"(affiliate|sponsored|disclosure|advertising|partner)", html, re.I))
        tr_score = 3 if transparent else 0
        score += tr_score
        signals["transparency"] = tr_score

        # 评价/推荐 (3 pts)
        rv_score = 3 if has_reviews else 0
        score += rv_score
        signals["reviews"] = rv_score

        # 声明准确性 (4 pts)
        accuracy = len(re.findall(r"(study found|research shows|data indicates|according to)", html, re.I))
        ac_score = 4 if accuracy >= 2 else (2 if accuracy >= 1 else 0)
        score += ac_score
        signals["claim_accuracy"] = ac_score

        # 联盟披露 (3 pts)
        affiliate = bool(re.search(r"(affiliate link|affiliate disclosure|#ad|sponsored)", html, re.I))
        af_score = 3 if affiliate else 0
        score += af_score
        signals["affiliate_disclosure"] = af_score

        return {"score": min(score, 25), "max": 25, "signals": signals}

    def _assess_content_quality(self, text: str, word_count: int, headings: List[dict]) -> dict:
        """评估内容质量指标。"""
        safe_text = text or ""
        # 可读性估算（平均句长）
        sentences = re.split(r'[.!?]+', safe_text)
        sentences = [s.strip() for s in sentences if s.strip()]
        avg_sentence_len = sum(len(s.split()) for s in sentences) / max(len(sentences), 1)

        # 段落结构
        paragraphs = safe_text.split('\n\n')
        avg_para_len = sum(len(p.split()) for p in paragraphs) / max(len(paragraphs), 1)

        #  freshness
        has_fresh_dates = bool(re.search(r"20(2[4-9]|3\d)", safe_text))

        return {
            "word_count": word_count,
            "sentence_count": len(sentences),
            "avg_sentence_length": round(avg_sentence_len, 1),
            "avg_paragraph_length": round(avg_para_len, 1),
            "heading_count": len(headings),
            "has_fresh_dates": has_fresh_dates,
            "readability_estimate": "good" if 10 <= avg_sentence_len <= 20 else "needs_improvement",
        }

    def _derive_actions(self, dimensions: dict, content_quality: dict) -> List[dict]:
        """生成 E-E-A-T 改进建议。"""
        actions = []

        exp = dimensions.get("experience", {})
        if exp.get("score", 0) < 15:
            actions.append({
                "action": "增加第一人称经验叙述和具体案例（我测试了...、我们发现...）",
                "priority": "medium",
                "target_module": "eeat_scorer",
                "params": {"dimension": "experience"},
            })

        expert = dimensions.get("expertise", {})
        if expert.get("score", 0) < 15:
            actions.append({
                "action": "添加作者资质介绍和专业背景页面",
                "priority": "high",
                "target_module": "eeat_scorer",
                "params": {"dimension": "expertise"},
            })

        auth = dimensions.get("authoritativeness", {})
        if auth.get("score", 0) < 15:
            actions.append({
                "action": "引用权威来源，增加外部验证信号（奖项、媒体报道、演讲）",
                "priority": "medium",
                "target_module": "eeat_scorer",
                "params": {"dimension": "authoritativeness"},
            })

        trust = dimensions.get("trustworthiness", {})
        if trust.get("score", 0) < 15:
            actions.append({
                "action": "添加联系信息、隐私政策、编辑标准和联盟披露",
                "priority": "high",
                "target_module": "eeat_scorer",
                "params": {"dimension": "trustworthiness"},
            })

        cq = content_quality
        if cq.get("avg_sentence_length", 0) > 25:
            actions.append({
                "action": "缩短句子长度（目标 15-20 词），提升可读性",
                "priority": "low",
                "target_module": "semantic_optimizer",
            })

        if cq.get("word_count", 0) < 500:
            actions.append({
                "action": "扩充内容深度（当前字数不足 500）",
                "priority": "medium",
                "target_module": "semantic_optimizer",
            })

        return actions
