"""
AI 爬虫访问检测模块 (Robots Checker)
=====================================
检测 robots.txt 中 AI 爬虫的访问状态，输出结构化 JSON。

输出格式:
    {
        "status": "success",
        "score": int,
        "score_details": {...},
        "ai_crawler_status": {...},
        "sitemaps": [...],
        "recommended_actions": [...],
    }
"""

from typing import Dict, List


class RobotsChecker:
    """检测 robots.txt 中 AI 爬虫的访问状态。"""

    # 关键 AI 爬虫列表
    AI_CRAWLERS = [
        "GPTBot", "OAI-SearchBot", "ChatGPT-User", "ClaudeBot",
        "anthropic-ai", "PerplexityBot", "CCBot", "Bytespider",
        "cohere-ai", "Google-Extended", "GoogleOther",
        "Applebot-Extended", "FacebookBot", "Amazonbot",
    ]

    # 关键爬虫（被阻断时扣分更多）
    CRITICAL_CRAWLERS = {"GPTBot", "ClaudeBot", "PerplexityBot", "OAI-SearchBot"}
    SECONDARY_CRAWLERS = set(AI_CRAWLERS) - CRITICAL_CRAWLERS

    def check(self, robots_result: dict) -> dict:
        """
        分析 robots.txt 结果，返回评分和状态。

        Args:
            robots_result: Crawler.fetch_robots_txt() 的返回结果

        Returns:
            标准模块结果格式
        """
        errors = robots_result.get("errors", [])
        if not robots_result.get("exists"):
            return {
                "status": "success",
                "score": 50,
                "score_details": {
                    "base_score": 50,
                    "reason": "robots.txt 不存在，AI 爬虫默认可访问但缺少站点地图指引",
                    "exists": False,
                },
                "fallback": False,
                "errors": errors,
                "recommended_actions": [
                    {
                        "action": "创建 robots.txt 文件，添加站点地图引用和 AI 爬虫访问规则",
                        "priority": "medium",
                        "target_module": "robots_checker",
                        "params": {"issue": "missing_robots_txt"},
                    }
                ],
                "data": {
                    "ai_crawler_status": {c: "NO_ROBOTS_TXT" for c in self.AI_CRAWLERS},
                    "sitemaps": [],
                },
            }

        ai_status = robots_result.get("ai_crawler_status", {})
        sitemaps = robots_result.get("sitemaps", [])

        # 计算评分
        score = self._calculate_score(ai_status, sitemaps)

        # 生成 actions
        actions = self._derive_actions(ai_status, sitemaps)

        blocked_critical = sum(
            1 for c in self.CRITICAL_CRAWLERS
            if ai_status.get(c) in ("BLOCKED", "BLOCKED_BY_WILDCARD")
        )
        blocked_secondary = sum(
            1 for c in self.SECONDARY_CRAWLERS
            if ai_status.get(c) in ("BLOCKED", "BLOCKED_BY_WILDCARD")
        )

        score_details = {
            "base_score": score,
            "reason": f"AI 爬虫访问评分 {score}/100，关键爬虫被阻 {blocked_critical} 个，次要爬虫被阻 {blocked_secondary} 个",
            "blocked_critical": blocked_critical,
            "blocked_secondary": blocked_secondary,
            "has_sitemap": len(sitemaps) > 0,
            "sitemap_count": len(sitemaps),
        }

        return {
            "status": "success",
            "score": score,
            "score_details": score_details,
            "fallback": False,
            "errors": errors,
            "recommended_actions": actions,
            "ai_crawler_status": ai_status,
            "sitemaps": sitemaps,
        }

    def _calculate_score(self, ai_status: Dict[str, str], sitemaps: List[str]) -> int:
        """计算 AI 爬虫访问评分 (0-100)。"""
        score = 100

        for crawler in self.CRITICAL_CRAWLERS:
            status = ai_status.get(crawler, "NOT_MENTIONED")
            if status in ("BLOCKED", "BLOCKED_BY_WILDCARD"):
                score -= 15

        for crawler in self.SECONDARY_CRAWLERS:
            status = ai_status.get(crawler, "NOT_MENTIONED")
            if status in ("BLOCKED", "BLOCKED_BY_WILDCARD"):
                score -= 5

        if not sitemaps:
            score -= 10

        return max(0, score)

    def _derive_actions(self, ai_status: Dict[str, str], sitemaps: List[str]) -> List[dict]:
        """根据爬虫状态生成改进行动。"""
        actions = []

        blocked_critical = [
            c for c in self.CRITICAL_CRAWLERS
            if ai_status.get(c) in ("BLOCKED", "BLOCKED_BY_WILDCARD")
        ]
        if blocked_critical:
            actions.append({
                "action": f"关键 AI 爬虫被阻断: {', '.join(blocked_critical)}，建议在 robots.txt 中移除 Disallow: / 或添加 Allow 规则",
                "priority": "high",
                "target_module": "robots_checker",
                "params": {"blocked": blocked_critical, "issue": "critical_crawlers_blocked"},
            })

        blocked_secondary = [
            c for c in self.SECONDARY_CRAWLERS
            if ai_status.get(c) in ("BLOCKED", "BLOCKED_BY_WILDCARD")
        ]
        if len(blocked_secondary) >= 3:
            actions.append({
                "action": f"多个次要 AI 爬虫被阻断 ({len(blocked_secondary)} 个)，建议评估是否允许访问",
                "priority": "medium",
                "target_module": "robots_checker",
                "params": {"blocked": blocked_secondary, "issue": "secondary_crawlers_blocked"},
            })

        if not sitemaps:
            actions.append({
                "action": "robots.txt 中未引用站点地图，建议添加 Sitemap 指令帮助 AI 爬虫发现内容",
                "priority": "medium",
                "target_module": "robots_checker",
                "params": {"issue": "missing_sitemap"},
            })

        wildcard_blocked = any(
            ai_status.get(c) == "BLOCKED_BY_WILDCARD" for c in self.AI_CRAWLERS
        )
        if wildcard_blocked:
            actions.append({
                "action": "robots.txt 中 User-agent: * 的 Disallow: / 规则阻断了所有爬虫，建议为 AI 爬虫添加专门的 Allow 规则",
                "priority": "high",
                "target_module": "robots_checker",
                "params": {"issue": "wildcard_block"},
            })

        return actions
