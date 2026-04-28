"""
品牌提及检测器 (Brand Checker)
=============================
检测品牌在 AI 引用平台的 presence。
基于 geo-seo-claude 的 brand_scanner.py，输出结构化 JSON。

输出格式:
    {
        "status": "success",
        "score": int,
        "score_details": {...},
        "platforms": {...},
        "recommended_actions": [...],
    }
"""

import re
from typing import Dict, List, Optional
from urllib.parse import quote_plus

import aiohttp


class BrandChecker:
    """品牌提及检测器：扫描 Wikipedia/Wikidata 等平台 presence。"""

    _WIKIPEDIA_API = "https://en.wikipedia.org/w/api.php"
    _WIKIDATA_API = "https://www.wikidata.org/w/api.php"
    _TIMEOUT = 15

    def __init__(self):
        self._session: Optional[aiohttp.ClientSession] = None

    async def check(self, brand_name: str, domain: str = "") -> dict:
        """
        检测品牌在主要平台的 presence。

        Args:
            brand_name: 品牌名称
            domain: 可选域名

        Returns:
            标准模块结果格式
        """
        if not brand_name:
            return {
                "status": "skipped",
                "score": 0,
                "score_details": {"reason": "品牌名称为空"},
                "fallback": False,
                "errors": [],
                "platforms": {},
                "recommended_actions": [],
            }

        async with aiohttp.ClientSession(
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
                ),
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
            }
        ) as session:
            self._session = session
            platforms = {
                "wikipedia": await self._check_wikipedia(brand_name),
                "wikidata": await self._check_wikidata(brand_name),
                "youtube": self._check_youtube(brand_name),
                "reddit": self._check_reddit(brand_name),
                "linkedin": self._check_linkedin(brand_name),
                "other": self._check_other(brand_name),
            }
        self._session = None

        score, score_details = self._calculate_score(platforms)
        actions = self._derive_actions(platforms, score)

        return {
            "status": "success",
            "score": score,
            "score_details": score_details,
            "fallback": False,
            "errors": [],
            "platforms": platforms,
            "recommended_actions": actions,
        }

    async def _check_wikipedia(self, brand_name: str) -> dict:
        """通过 Wikipedia API 检测品牌页面。"""
        result = {
            "has_page": False,
            "search_results_count": 0,
            "page_url": f"https://en.wikipedia.org/wiki/Special:Search?search={quote_plus(brand_name)}",
        }
        try:
            url = (
                f"{self._WIKIPEDIA_API}?action=query&list=search"
                f"&srsearch={quote_plus(brand_name)}&format=json"
            )
            async with self._session.get(url, timeout=self._TIMEOUT) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    search_results = data.get("query", {}).get("search", [])
                    result["search_results_count"] = len(search_results)
                    if search_results:
                        top_title = search_results[0].get("title", "").lower()
                        if brand_name.lower() in top_title:
                            result["has_page"] = True
                            result["page_title"] = search_results[0].get("title")
        except (aiohttp.ClientError, OSError, ValueError):
            pass
        return result

    async def _check_wikidata(self, brand_name: str) -> dict:
        """通过 Wikidata API 检测品牌实体。"""
        result = {
            "has_entry": False,
            "entity_id": "",
            "description": "",
            "url": f"https://www.wikidata.org/w/index.php?search={quote_plus(brand_name)}",
        }
        try:
            url = (
                f"{self._WIKIDATA_API}?action=wbsearchentities"
                f"&search={quote_plus(brand_name)}&language=en&format=json"
            )
            async with self._session.get(url, timeout=self._TIMEOUT) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    entities = data.get("search", [])
                    if entities:
                        result["has_entry"] = True
                        result["entity_id"] = entities[0].get("id", "")
                        result["description"] = entities[0].get("description", "")
        except (aiohttp.ClientError, OSError, ValueError):
            pass
        return result

    def _check_youtube(self, brand_name: str) -> dict:
        """YouTube presence 框架（需人工/API 确认）。"""
        return {
            "platform": "YouTube",
            "correlation": 0.737,
            "weight": 0.25,
            "search_url": f"https://www.youtube.com/results?search_query={quote_plus(brand_name)}",
            "check_instructions": [
                f"Search YouTube for '{brand_name}'",
                "Check for official channel, brand videos, reviews",
            ],
        }

    def _check_reddit(self, brand_name: str) -> dict:
        """Reddit presence 框架。"""
        return {
            "platform": "Reddit",
            "correlation": "high",
            "weight": 0.25,
            "search_url": f"https://www.reddit.com/search/?q={quote_plus(brand_name)}",
            "check_instructions": [
                f"Search Reddit for '{brand_name}'",
                "Check for subreddit, mentions, sentiment",
            ],
        }

    def _check_linkedin(self, brand_name: str) -> dict:
        """LinkedIn presence 框架。"""
        return {
            "platform": "LinkedIn",
            "correlation": "moderate",
            "weight": 0.15,
            "search_url": f"https://www.linkedin.com/search/results/companies/?keywords={quote_plus(brand_name)}",
            "check_instructions": [
                f"Search LinkedIn for '{brand_name}'",
                "Check company page, followers, activity",
            ],
        }

    def _check_other(self, brand_name: str) -> dict:
        """其他平台搜索链接。"""
        platforms = {
            "Quora": f"https://www.quora.com/search?q={quote_plus(brand_name)}",
            "Stack Overflow": f"https://stackoverflow.com/search?q={quote_plus(brand_name)}",
            "GitHub": f"https://github.com/search?q={quote_plus(brand_name)}",
            "Crunchbase": f"https://www.crunchbase.com/textsearch?q={quote_plus(brand_name)}",
            "Product Hunt": f"https://www.producthunt.com/search?q={quote_plus(brand_name)}",
            "G2": f"https://www.g2.com/search?utf8=&query={quote_plus(brand_name)}",
            "Trustpilot": f"https://www.trustpilot.com/search?query={quote_plus(brand_name)}",
        }
        return {
            "platform": "Other",
            "weight": 0.15,
            "platforms_checked": platforms,
        }

    def _calculate_score(self, platforms: dict) -> tuple:
        """计算品牌 presence 总分。"""
        score = 0
        details = {}

        wiki = platforms.get("wikipedia", {})
        if wiki.get("has_page"):
            score += 25
            details["wikipedia"] = "has_page"
        elif wiki.get("search_results_count", 0) > 0:
            score += 10
            details["wikipedia"] = "search_results_only"
        else:
            details["wikipedia"] = "not_found"

        wd = platforms.get("wikidata", {})
        if wd.get("has_entry"):
            score += 20
            details["wikidata"] = "has_entry"
        else:
            details["wikidata"] = "not_found"

        # YouTube/Reddit/LinkedIn 无法自动检测，给基础分
        score += 5
        details["social_presence"] = "manual_check_required"

        details["max_possible"] = 100
        return min(score, 100), details

    def _derive_actions(self, platforms: dict, score: int) -> List[dict]:
        """生成改进建议。"""
        actions = []

        if not platforms.get("wikipedia", {}).get("has_page"):
            actions.append({
                "action": "建立 Wikipedia 页面（需满足知名度标准）",
                "priority": "high",
                "target_module": "brand_checker",
                "params": {"platform": "wikipedia"},
            })

        if not platforms.get("wikidata", {}).get("has_entry"):
            actions.append({
                "action": "创建 Wikidata 实体条目",
                "priority": "high",
                "target_module": "brand_checker",
                "params": {"platform": "wikidata"},
            })

        if score < 50:
            actions.append({
                "action": "在 YouTube 发布教育/教程内容（AI 引用相关性最高 0.737）",
                "priority": "medium",
                "target_module": "brand_checker",
                "params": {"platform": "youtube"},
            })
            actions.append({
                "action": "在 Reddit 建立真实社区参与",
                "priority": "medium",
                "target_module": "brand_checker",
                "params": {"platform": "reddit"},
            })

        actions.append({
            "action": "在 Schema.org sameAs 中链接所有平台 profile",
            "priority": "medium",
            "target_module": "schema_generator",
            "params": {"property": "sameAs"},
        })

        return actions
