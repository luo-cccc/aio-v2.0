"""
HTML 特征提取工具
==================
供 workflow 和独立模块入口复用的通用 HTML 特征检测函数。
"""

import re
from typing import Optional


def extract_html_features(html: str) -> dict:
    """
    从原始 HTML 中提取常用特征，供 platform/eeat/technical 等模块使用。

    Returns:
        {
            "has_tables": bool,
            "has_lists": bool,
            "has_faq": bool,
            "has_author": bool,
            "author_name": str,
            "has_dates": bool,
            "has_reviews": bool,
        }
    """
    if not html:
        return {
            "has_tables": False,
            "has_lists": False,
            "has_faq": False,
            "has_author": False,
            "author_name": "",
            "has_dates": False,
            "has_reviews": False,
        }

    has_author = bool(
        re.search(r'<meta[^>]*name=["\']?(?:author|article:author)["\']?', html, re.I)
    )
    author_name_match = re.search(
        r'<meta[^>]*name=["\']?author["\']?[^>]*content=["\']([^"\']+)["\']',
        html,
        re.I,
    )
    author_name = author_name_match.group(1) if author_name_match else ""

    return {
        "has_tables": bool(re.search(r"<table", html, re.I)),
        "has_lists": bool(re.search(r"<(ul|ol)", html, re.I)),
        "has_faq": bool(re.search(r"faq|question", html, re.I)),
        "has_author": has_author,
        "author_name": author_name,
        "has_dates": bool(re.search(r"20\d{2}", html)),
        "has_reviews": bool(re.search(r"review|rating|stars", html, re.I)),
    }
