"""
平台优化评分器 (Platform Optimizer)
====================================
针对 5 个 AI 搜索平台的独立评分和优化建议。
基于 geo-seo-claude 的 geo-platform-optimizer SKILL。

输出格式:
    {
        "status": "success",
        "score": int,
        "score_details": {...},
        "platforms": {...},
        "universal_actions": [...],
        "recommended_actions": [...],
    }
"""

import re
from typing import Dict, List


class PlatformOptimizer:
    """AI 搜索平台优化评分器。"""

    def analyze(
        self,
        content_blocks: List[dict],
        headings: List[dict],
        has_tables: bool,
        has_lists: bool,
        has_faq: bool,
        has_author: bool,
        has_dates: bool,
        word_count: int,
        images_count: int,
        videos_count: int,
    ) -> dict:
        """
        基于页面特征评分 5 个 AI 平台的优化度。

        Args:
            content_blocks: 内容块列表
            headings: heading 列表
            has_tables: 页面是否包含表格
            has_lists: 页面是否包含列表
            has_faq: 页面是否有 FAQ 结构
            has_author: 是否有作者信息
            has_dates: 是否有发布/更新日期
            word_count: 总字数
            images_count: 图片数量
            videos_count: 视频数量

        Returns:
            标准模块结果格式
        """
        platforms = {
            "google_aio": self._score_google_aio(
                headings, has_tables, has_lists, has_faq, has_author, has_dates, word_count
            ),
            "chatgpt": self._score_chatgpt(
                has_author, word_count, headings
            ),
            "perplexity": self._score_perplexity(
                content_blocks, has_dates, word_count
            ),
            "gemini": self._score_gemini(
                has_tables, has_lists, images_count, videos_count, has_author
            ),
            "bing_copilot": self._score_bing_copilot(
                headings, word_count, has_dates
            ),
        }

        scores = [p["score"] for p in platforms.values()]
        overall = round(sum(scores) / len(scores)) if scores else 0

        score_details = {
            "overall": overall,
            "platform_count": len(platforms),
            "strongest": max(platforms, key=lambda k: platforms[k]["score"]),
            "weakest": min(platforms, key=lambda k: platforms[k]["score"]),
        }

        universal = self._universal_actions(platforms)
        actions = self._derive_actions(platforms)

        return {
            "status": "success",
            "score": overall,
            "score_details": score_details,
            "fallback": False,
            "errors": [],
            "platforms": platforms,
            "universal_actions": universal,
            "recommended_actions": actions,
        }

    def _score_google_aio(
        self, headings: List[dict], has_tables: bool, has_lists: bool,
        has_faq: bool, has_author: bool, has_dates: bool, word_count: int
    ) -> dict:
        """Google AI Overviews 评分。"""
        score = 0
        details = {}

        # Question-based headings (10 pts)
        question_headings = [
            h for h in headings
            if re.search(r"^(what|how|why|when|where|who|which|is|are|does|can)", h.get("text", ""), re.I)
        ]
        qh_score = min(len(question_headings) * 2, 10)
        score += qh_score
        details["question_headings"] = qh_score

        # Direct answers (15 pts) — estimated from content structure
        score += 10
        details["direct_answers"] = 10

        # Tables (10 pts)
        score += 10 if has_tables else 0
        details["tables"] = 10 if has_tables else 0

        # Lists (10 pts)
        score += 10 if has_lists else 5
        details["lists"] = 10 if has_lists else 5

        # FAQ (10 pts)
        score += 10 if has_faq else 0
        details["faq"] = 10 if has_faq else 0

        # Statistics (10 pts) — estimated
        score += 5
        details["statistics"] = 5

        # Dates (5 pts)
        score += 5 if has_dates else 0
        details["dates"] = 5 if has_dates else 0

        # Author (5 pts)
        score += 5 if has_author else 0
        details["author"] = 5 if has_author else 0

        # Clean hierarchy (5 pts)
        score += 5
        details["hierarchy"] = 5

        return {"score": min(score, 100), "max": 100, "details": details}

    def _score_chatgpt(self, has_author: bool, word_count: int, headings: List[dict]) -> dict:
        """ChatGPT Web Search 评分。"""
        score = 0
        details = {}

        # Wikipedia (20 pts) — cannot auto-detect
        score += 5
        details["wikipedia"] = 5

        # Wikidata (10 pts)
        score += 5
        details["wikidata"] = 5

        # Bing index (10 pts)
        score += 5
        details["bing_index"] = 5

        # Reddit (10 pts)
        score += 5
        details["reddit"] = 5

        # YouTube (10 pts)
        score += 5
        details["youtube"] = 5

        # Authoritative backlinks (15 pts)
        score += 5
        details["backlinks"] = 5

        # Entity consistency (10 pts)
        score += 5
        details["entity_consistency"] = 5

        # Content comprehensiveness (10 pts)
        comp_score = 10 if word_count >= 2000 else (5 if word_count >= 1000 else 0)
        score += comp_score
        details["comprehensiveness"] = comp_score

        # Bing WMT (5 pts)
        score += 0
        details["bing_wmt"] = 0

        return {"score": min(score, 100), "max": 100, "details": details}

    def _score_perplexity(self, content_blocks: List[dict], has_dates: bool, word_count: int) -> dict:
        """Perplexity AI 评分。"""
        score = 0
        details = {}

        # Reddit presence (20 pts)
        score += 5
        details["reddit"] = 5

        # Forum mentions (10 pts)
        score += 5
        details["forums"] = 5

        # Freshness (10 pts)
        score += 10 if has_dates else 0
        details["freshness"] = 10 if has_dates else 0

        # Original research (15 pts)
        score += 5
        details["original_research"] = 5

        # YouTube (10 pts)
        score += 5
        details["youtube"] = 5

        # Quotable paragraphs (10 pts)
        cb = content_blocks or []
        qp_score = min(len(cb) * 2, 10)
        score += qp_score
        details["quotable_paragraphs"] = qp_score

        # Multi-source validation (10 pts)
        score += 5
        details["multi_source"] = 5

        # Discussion content (10 pts)
        score += 5
        details["discussion"] = 5

        # Wikipedia (5 pts)
        score += 5
        details["wikipedia"] = 5

        return {"score": min(score, 100), "max": 100, "details": details}

    def _score_gemini(
        self, has_tables: bool, has_lists: bool, images_count: int,
        videos_count: int, has_author: bool
    ) -> dict:
        """Google Gemini 评分。"""
        score = 0
        details = {}

        # Knowledge Panel (15 pts)
        score += 5
        details["knowledge_panel"] = 5

        # GBP (10 pts)
        score += 5
        details["gbp"] = 5

        # YouTube (20 pts)
        yt_score = 20 if videos_count > 0 else (10 if videos_count == 0 else 0)
        score += yt_score
        details["youtube"] = yt_score

        # Schema.org (15 pts)
        score += 10
        details["schema"] = 10

        # Google ecosystem (10 pts)
        score += 5
        details["google_ecosystem"] = 5

        # Image optimization (10 pts)
        img_score = 10 if images_count > 0 else 0
        score += img_score
        details["images"] = img_score

        # E-E-A-T (10 pts)
        score += 10 if has_author else 5
        details["eeat"] = 10 if has_author else 5

        # Merchant Center (5 pts)
        score += 0
        details["merchant_center"] = 0

        # Multi-modal (5 pts)
        mm_score = 5 if (images_count > 0 and videos_count > 0) else 0
        score += mm_score
        details["multimodal"] = mm_score

        return {"score": min(score, 100), "max": 100, "details": details}

    def _score_bing_copilot(self, headings: List[dict], word_count: int, has_dates: bool) -> dict:
        """Bing Copilot 评分。"""
        score = 0
        details = {}

        # Bing WMT (15 pts)
        score += 0
        details["bing_wmt"] = 0

        # IndexNow (15 pts)
        score += 0
        details["indexnow"] = 0

        # Bing index (10 pts)
        score += 5
        details["bing_index"] = 5

        # LinkedIn (10 pts)
        score += 5
        details["linkedin"] = 5

        # GitHub (5 pts)
        score += 0
        details["github"] = 0

        # Meta descriptions (10 pts)
        score += 5
        details["meta_descriptions"] = 5

        # Social signals (10 pts)
        score += 5
        details["social_signals"] = 5

        # Exact-match keywords (10 pts)
        score += 5
        details["exact_match"] = 5

        # Page speed (10 pts)
        score += 5
        details["page_speed"] = 5

        # Bing Places (5 pts)
        score += 0
        details["bing_places"] = 0

        return {"score": min(score, 100), "max": 100, "details": details}

    def _universal_actions(self, platforms: dict) -> List[dict]:
        """生成跨平台通用优化建议。"""
        return [
            {
                "action": "确保 Wikipedia/Wikidata 实体存在（影响所有平台）",
                "priority": "high",
                "target_module": "brand_checker",
            },
            {
                "action": "创建 YouTube 频道并发布主题相关内容（最高相关性 0.737）",
                "priority": "high",
                "target_module": "brand_checker",
            },
            {
                "action": "添加 comprehensive Schema.org markup（尤其 Organization + sameAs）",
                "priority": "high",
                "target_module": "schema_generator",
            },
            {
                "action": "优化页面加载速度（目标 < 2s）",
                "priority": "medium",
                "target_module": "technical_auditor",
            },
        ]

    def _derive_actions(self, platforms: dict) -> List[dict]:
        """基于平台弱点生成针对性建议。"""
        actions = []

        weakest = min(platforms, key=lambda k: platforms[k]["score"])
        weakest_score = platforms[weakest]["score"]

        if weakest == "google_aio" and weakest_score < 50:
            actions.append({
                "action": "添加 question-based H2/H3 headings 和直接答案段落",
                "priority": "high",
                "target_module": "semantic_optimizer",
            })
            actions.append({
                "action": "将对比数据转换为 HTML tables",
                "priority": "medium",
                "target_module": "semantic_optimizer",
            })

        elif weakest == "chatgpt" and weakest_score < 50:
            actions.append({
                "action": "确保内容 >2000 字，覆盖主题全面",
                "priority": "medium",
                "target_module": "semantic_optimizer",
            })

        elif weakest == "perplexity" and weakest_score < 50:
            actions.append({
                "action": "增加原创数据/研究，确保段落可独立引用",
                "priority": "medium",
                "target_module": "semantic_optimizer",
            })

        elif weakest == "gemini" and weakest_score < 50:
            actions.append({
                "action": "优化图片 alt 和文件名，增加视频内容",
                "priority": "medium",
                "target_module": "multimodal_labeler",
            })

        elif weakest == "bing_copilot" and weakest_score < 50:
            actions.append({
                "action": "注册 Bing Webmaster Tools 并提交 sitemap",
                "priority": "medium",
                "target_module": "technical_auditor",
            })
            actions.append({
                "action": "实现 IndexNow 协议",
                "priority": "low",
                "target_module": "technical_auditor",
            })

        return actions
