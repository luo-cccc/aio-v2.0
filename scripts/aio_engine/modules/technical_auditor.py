"""
技术 SEO 审计器 (Technical Auditor)
====================================
8 维度技术 SEO 评分：可爬性、可索引性、安全、URL、移动、CWV、SSR、速度。
基于 geo-seo-claude 的 geo-technical SKILL。

输出格式:
    {
        "status": "success",
        "score": int,
        "score_details": {...},
        "categories": {...},
        "critical_issues": [...],
        "recommended_actions": [...],
    }
"""

import re
from typing import Dict, List


class TechnicalAuditor:
    """技术 SEO 审计器。"""

    def audit(
        self,
        html: str,
        headers: dict,
        has_ssr: bool,
        robots_result: dict,
        canonical: str,
        og_type: str,
    ) -> dict:
        """
        基于页面原始数据执行技术 SEO 审计。

        Args:
            html: 原始 HTML
            headers: HTTP 响应头
            has_ssr: 是否有服务端渲染
            robots_result: robots_checker 的结果（含 ai_crawler_status）
            canonical: canonical URL
            og_type: OG type

        Returns:
            标准模块结果格式
        """
        categories = {
            "crawlability": self._audit_crawlability(robots_result),
            "indexability": self._audit_indexability(html, canonical),
            "security": self._audit_security(headers),
            "url_structure": self._audit_url_structure(html),
            "mobile": self._audit_mobile(html),
            "core_web_vitals": self._audit_cwv(headers, html),
            "ssr": self._audit_ssr(has_ssr, html),
            "page_speed": self._audit_page_speed(headers, html),
        }

        total = sum(c["score"] for c in categories.values())
        max_total = sum(c["max"] for c in categories.values())
        score = round(total / max_total * 100) if max_total else 0

        score_details = {
            "total_raw": total,
            "max_raw": max_total,
            "category_scores": {k: v["score"] for k, v in categories.items()},
        }

        critical = self._collect_critical_issues(categories)
        actions = self._derive_actions(categories, robots_result)

        return {
            "status": "success",
            "score": score,
            "score_details": score_details,
            "fallback": False,
            "errors": [],
            "categories": categories,
            "critical_issues": critical,
            "recommended_actions": actions,
        }

    def _audit_crawlability(self, robots_result: dict) -> dict:
        """审计可爬性（15 pts）。"""
        score = 0
        issues = []

        # robots.txt 有效性 (3 pts)
        if robots_result and robots_result.get("status") != "error":
            score += 3
        else:
            issues.append("robots.txt 无法获取或无效")

        # AI 爬虫允许 (5 pts)
        ai_status = robots_result.get("ai_crawler_status", {})
        critical_crawlers = ["GPTBot", "ClaudeBot", "PerplexityBot", "Googlebot", "Bingbot"]
        allowed = sum(1 for c in critical_crawlers if ai_status.get(c) in ("ALLOWED", "ALLOWED_BY_DEFAULT"))
        if allowed >= 5:
            score += 5
        elif allowed >= 3:
            score += 3
            issues.append("部分关键 AI 爬虫被封禁")
        else:
            issues.append("多数 AI 爬虫被封禁，GEO 影响严重")

        # Sitemap (3 pts)
        sitemaps = robots_result.get("sitemaps", [])
        if sitemaps:
            score += 3
        else:
            issues.append("robots.txt 未引用 sitemap")

        # 假设其他检查通过
        score += 4

        return {"score": score, "max": 15, "issues": issues}

    def _audit_indexability(self, html: str, canonical: str) -> dict:
        """审计可索引性（12 pts）。"""
        score = 0
        issues = []

        # Canonical (3 pts)
        if canonical:
            score += 3
        else:
            issues.append("缺少 canonical 标签")

        # 检查 noindex (2 pts)
        if re.search(r'<meta[^>]*name=["\']?robots["\']?[^>]*content=["\']?[^"\']*noindex', html, re.I):
            issues.append("页面包含 noindex meta 标签")
        else:
            score += 2

        # 其他检查假设通过
        score += 7

        return {"score": score, "max": 12, "issues": issues}

    def _audit_security(self, headers: dict) -> dict:
        """审计安全性（10 pts）。"""
        score = 0
        issues = []
        h = {k.lower(): v for k, v in (headers or {}).items()}

        # HTTPS (4 pts)
        if h.get("strict-transport-security"):
            score += 4
        else:
            issues.append("缺少 HSTS 头")

        # X-Content-Type-Options (1 pt)
        if h.get("x-content-type-options"):
            score += 1
        else:
            issues.append("缺少 X-Content-Type-Options")

        # X-Frame-Options (1 pt)
        if h.get("x-frame-options"):
            score += 1
        else:
            issues.append("缺少 X-Frame-Options")

        # Referrer-Policy (1 pt)
        if h.get("referrer-policy"):
            score += 1
        else:
            issues.append("缺少 Referrer-Policy")

        # CSP (1 pt)
        if h.get("content-security-policy"):
            score += 1
        else:
            issues.append("缺少 Content-Security-Policy")

        # 其他 (2 pts)
        score += 2

        return {"score": score, "max": 10, "issues": issues}

    def _audit_url_structure(self, html: str) -> dict:
        """审计 URL 结构（8 pts）。"""
        score = 6
        issues = []

        # 简化：假设基本通过
        return {"score": score, "max": 8, "issues": issues}

    def _audit_mobile(self, html: str) -> dict:
        """审计移动优化（10 pts）。"""
        score = 0
        issues = []

        # Viewport (3 pts)
        if re.search(r'<meta[^>]*name=["\']?viewport["\']?', html, re.I):
            score += 3
        else:
            issues.append("缺少 viewport meta 标签")

        # 响应式 (3 pts)
        score += 3

        # Tap targets / font size (4 pts)
        score += 4

        return {"score": score, "max": 10, "issues": issues}

    def _audit_cwv(self, headers: dict, html: str) -> dict:
        """审计 Core Web Vitals（15 pts）。"""
        score = 10
        issues = []

        # 无真实性能数据，基于特征估算
        # 检查图片优化
        img_tags = re.findall(r'<img[^>]*>', html, re.I)
        imgs_without_dims = sum(
            1 for img in img_tags
            if not re.search(r'width\s*=|height\s*=', img, re.I)
        )
        if imgs_without_dims > len(img_tags) * 0.5:
            issues.append(f"{imgs_without_dims}/{len(img_tags)} 图片缺少 width/height 属性（影响 CLS）")
            score -= 3

        return {"score": max(0, score), "max": 15, "issues": issues}

    def _audit_ssr(self, has_ssr: bool, html: str) -> dict:
        """审计 SSR（15 pts）— GEO 关键。"""
        score = 0
        issues = []

        # 主内容在 raw HTML 中 (8 pts)
        if has_ssr:
            score += 8
        else:
            issues.append("页面可能依赖客户端渲染，AI 爬虫无法抓取内容")

        # Meta + structured data (4 pts)
        has_meta = bool(re.search(r'<meta[^>]*name=["\']?description["\']?', html, re.I))
        has_jsonld = bool(re.search(r'<script[^>]*type=["\']?application/ld\+json["\']?', html, re.I))
        if has_meta and has_jsonld:
            score += 4
        else:
            if not has_meta:
                issues.append("缺少 meta description")
            if not has_jsonld:
                issues.append("缺少 JSON-LD structured data")

        # 内部链接 (3 pts)
        internal_links = len(re.findall(r'<a[^>]*href=["\']?/', html, re.I))
        if internal_links >= 3:
            score += 3
        else:
            issues.append("内部链接数量不足")

        return {"score": score, "max": 15, "issues": issues}

    def _audit_page_speed(self, headers: dict, html: str) -> dict:
        """审计页面速度（15 pts）。"""
        score = 8
        issues = []

        # 检查压缩
        h = {k.lower(): v for k, v in (headers or {}).items()}
        encoding = h.get("content-encoding", "")
        if "gzip" in encoding or "br" in encoding:
            score += 2
        else:
            issues.append("未启用 gzip/brotli 压缩")

        # 检查缓存头
        cache = h.get("cache-control", "")
        if cache:
            score += 2
        else:
            issues.append("静态资源缺少 Cache-Control 头")

        # 估算页面大小
        page_size_kb = len(html.encode("utf-8")) / 1024
        if page_size_kb > 2000:
            issues.append(f"页面大小 {page_size_kb:.0f}KB，超过 2MB 建议值")
            score -= 2
        elif page_size_kb < 1000:
            score += 2

        # CDN 检测
        cdn_headers = ["cf-ray", "x-cache", "x-served-by", "x-amz-cf-id"]
        has_cdn = any(h.get(hdr) for hdr in cdn_headers)
        if has_cdn:
            score += 1

        return {"score": max(0, score), "max": 15, "issues": issues}

    def _collect_critical_issues(self, categories: dict) -> List[dict]:
        """收集所有严重问题。"""
        critical = []
        for cat_name, cat_data in categories.items():
            for issue in cat_data.get("issues", []):
                if isinstance(issue, str):
                    critical.append({"category": cat_name, "issue": issue})
        return critical

    def _derive_actions(self, categories: dict, robots_result: dict) -> List[dict]:
        """生成技术改进建议。"""
        actions = []

        ssr = categories.get("ssr", {})
        if ssr.get("score", 0) < 10:
            actions.append({
                "action": "实现服务端渲染（SSR）或预渲染，AI 爬虫不执行 JavaScript",
                "priority": "high",
                "target_module": "technical_auditor",
                "params": {"category": "ssr"},
            })

        crawl = categories.get("crawlability", {})
        if crawl.get("score", 0) < 10:
            actions.append({
                "action": "修复 robots.txt：允许 GPTBot/ClaudeBot/PerplexityBot 等 AI 爬虫",
                "priority": "high",
                "target_module": "robots_checker",
                "params": {"category": "crawlability"},
            })

        sec = categories.get("security", {})
        if sec.get("score", 0) < 6:
            actions.append({
                "action": "添加安全响应头：HSTS, X-Frame-Options, CSP",
                "priority": "medium",
                "target_module": "technical_auditor",
                "params": {"category": "security"},
            })

        mobile = categories.get("mobile", {})
        if mobile.get("score", 0) < 8:
            actions.append({
                "action": "添加 viewport meta 标签并确保移动响应式",
                "priority": "high",
                "target_module": "technical_auditor",
                "params": {"category": "mobile"},
            })

        # IndexNow
        actions.append({
            "action": "实现 IndexNow 协议以加速 Bing 索引",
            "priority": "low",
            "target_module": "technical_auditor",
            "params": {"protocol": "IndexNow"},
        })

        return actions
