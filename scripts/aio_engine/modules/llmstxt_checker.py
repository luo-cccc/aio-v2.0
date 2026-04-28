"""
llms.txt 检测模块 (LLMsTxt Checker)
====================================
验证 llms.txt 的存在性和格式合规性，输出结构化 JSON。

输出格式:
    {
        "status": "success",
        "score": int,
        "score_details": {...},
        "exists": bool,
        "format_valid": bool,
        "issues": [...],
        "suggestions": [...],
        "recommended_actions": [...],
    }
"""

import re
from typing import List


class LLMsTxtChecker:
    """检测 llms.txt 的存在性和格式合规性。"""

    def check(self, llms_result: dict) -> dict:
        """
        分析 llms.txt 结果，返回评分和状态。

        Args:
            llms_result: Crawler.fetch_llms_txt() 的返回结果

        Returns:
            标准模块结果格式
        """
        errors = llms_result.get("errors", [])
        llms_txt = llms_result.get("llms_txt", {})
        llms_full = llms_result.get("llms_full_txt", {})

        exists = llms_txt.get("exists", False)
        content = llms_txt.get("content", "")

        if not exists:
            return {
                "status": "success",
                "score": 0,
                "score_details": {
                    "base_score": 0,
                    "reason": "llms.txt 不存在，AI 爬虫无法获取站点内容指引",
                    "exists": False,
                },
                "fallback": False,
                "errors": errors,
                "recommended_actions": [
                    {
                        "action": "创建 /llms.txt 文件，包含站点标题、描述、关键页面链接和分区结构",
                        "priority": "high",
                        "target_module": "llmstxt_checker",
                        "params": {"issue": "missing_llms_txt"},
                    }
                ],
                "exists": False,
                "format_valid": False,
                "has_title": False,
                "has_description": False,
                "has_sections": False,
                "has_links": False,
                "section_count": 0,
                "link_count": 0,
                "issues": ["llms.txt 不存在"],
                "suggestions": ["创建 llms.txt 文件，参考 llms.txt 标准格式"],
                "full_version_exists": llms_full.get("exists", False),
            }

        # 验证格式
        validation = self._validate_content(content)
        full_exists = llms_full.get("exists", False)

        # 计算评分
        score = self._calculate_score(validation, full_exists)

        score_details = {
            "base_score": score,
            "reason": f"llms.txt 评分 {score}/100，格式合规: {validation['format_valid']}，分区数: {validation['section_count']}，链接数: {validation['link_count']}",
            "exists": True,
            "format_valid": validation["format_valid"],
            "section_count": validation["section_count"],
            "link_count": validation["link_count"],
            "has_full_version": full_exists,
        }

        actions = self._derive_actions(validation, full_exists)

        return {
            "status": "success",
            "score": score,
            "score_details": score_details,
            "fallback": False,
            "errors": errors,
            "recommended_actions": actions,
            "exists": True,
            **validation,
            "full_version_exists": full_exists,
        }

    def _validate_content(self, content: str) -> dict:
        """验证 llms.txt 内容格式。"""
        safe_content = content or ""
        lines = safe_content.strip().split("\n")

        has_title = bool(lines) and lines[0].startswith("# ")

        has_description = False
        for line in lines:
            if line.startswith("> "):
                has_description = True
                break

        sections = [l for l in lines if l.startswith("## ")]
        has_sections = len(sections) > 0
        section_count = len(sections)

        links = re.findall(r"- \[.+?\]\(.+?\)", safe_content)
        has_links = len(links) > 0
        link_count = len(links)

        issues = []
        if not has_title:
            issues.append("Missing title (should start with '# Site Name')")
        if not has_description:
            issues.append("Missing description (use '> Brief description')")
        if not has_sections:
            issues.append("No sections found (use '## Section Name')")
        if not has_links:
            issues.append("No page links found (use '- [Page Title](url): Description')")

        suggestions = []
        if link_count < 5:
            suggestions.append("Consider adding more key pages (aim for 10-20)")
        if section_count < 2:
            suggestions.append("Add more sections to organize content types")
        if "contact" not in safe_content.lower():
            suggestions.append("Add a Contact section with email and location")
        if "key fact" not in safe_content.lower() and "about" not in safe_content.lower():
            suggestions.append("Add key facts about your business/service")

        format_valid = has_title and has_description and has_sections and has_links

        return {
            "format_valid": format_valid,
            "has_title": has_title,
            "has_description": has_description,
            "has_sections": has_sections,
            "has_links": has_links,
            "section_count": section_count,
            "link_count": link_count,
            "issues": issues,
            "suggestions": suggestions,
        }

    def _calculate_score(self, validation: dict, full_exists: bool) -> int:
        """计算 llms.txt 评分 (0-100)。"""
        if not validation["format_valid"]:
            if validation["has_title"] or validation["has_description"]:
                return 30
            return 0

        score = 50

        # 链接数加分
        link_count = validation["link_count"]
        if link_count >= 10:
            score += 20
        elif link_count >= 5:
            score += 10
        else:
            score += 5

        # 分区数加分
        section_count = validation["section_count"]
        if section_count >= 4:
            score += 10
        elif section_count >= 2:
            score += 5

        # 有完整版本加分
        if full_exists:
            score += 10

        # 无 issues 加分
        if not validation["issues"]:
            score += 10

        return min(100, score)

    def _derive_actions(self, validation: dict, full_exists: bool) -> List[dict]:
        """根据验证结果生成改进行动。"""
        actions = []

        for issue in validation["issues"]:
            actions.append({
                "action": f"llms.txt 格式问题: {issue}",
                "priority": "high",
                "target_module": "llmstxt_checker",
                "params": {"issue": issue, "type": "format"},
            })

        for suggestion in validation["suggestions"]:
            actions.append({
                "action": f"llms.txt 优化建议: {suggestion}",
                "priority": "medium",
                "target_module": "llmstxt_checker",
                "params": {"suggestion": suggestion, "type": "suggestion"},
            })

        if not full_exists:
            actions.append({
                "action": "创建 /llms-full.txt 完整版本，包含所有页面的详细描述",
                "priority": "low",
                "target_module": "llmstxt_checker",
                "params": {"issue": "missing_full_version"},
            })

        return actions
