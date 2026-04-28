"""
页面解析器 (Phase 1)
====================
抓取页面、提取关键词、推断 Schema.org 类型。
所有后续模块依赖此阶段的结果。
"""

import json
import re
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from ..lib.crawler import Crawler
from ..lib.llm_client import LLMClient
from ..lib.schema_cache import SchemaCache


@dataclass
class ParsedPage:
    """页面解析结果，供后续模块使用。"""

    url: str
    title: str
    description: str
    text: str  # 去标签后的正文（截断）
    keyword: str  # 提取的核心关键词
    derived_type: str  # 推断的 Schema.org 类型
    existing_schemas: List[str] = field(default_factory=list)
    images: List[str] = field(default_factory=list)
    videos: List[str] = field(default_factory=list)
    links: List[str] = field(default_factory=list)
    json_ld_scripts: List[str] = field(default_factory=list)
    canonical: str = ""
    og_type: str = ""
    content_blocks: List[dict] = field(default_factory=list)
    headings: List[dict] = field(default_factory=list)
    has_ssr: bool = True
    # 原始数据供 technical/platform/eeat 等模块使用
    _raw_html: str = ""
    _headers: dict = field(default_factory=dict)
    # 底座化元信息
    _meta: dict = field(default_factory=dict)


class PageParser:
    """
    阶段1 解析器：抓取并解析页面，完成关键词提取和类型推断。
    """

    _MAX_TEXT_LEN = 2000
    _STOPWORDS = {
        "the", "a", "an", "is", "are", "was", "were", "be", "been",
        "being", "have", "has", "had", "do", "does", "did", "will",
        "would", "could", "should", "may", "might", "must", "shall",
        "can", "need", "dare", "ought", "used", "to", "of", "in",
        "for", "on", "with", "at", "by", "from", "as", "into",
        "through", "during", "before", "after", "above", "below",
        "between", "under", "again", "further", "then", "once",
        "的", "了", "在", "是", "我", "有", "和", "就", "不", "人",
        "都", "一", "一个", "上", "也", "很", "到", "说", "要", "去",
        "你", "会", "着", "没有", "看", "好", "自己", "这",
    }

    def __init__(self, llm: LLMClient, crawler: Crawler):
        self._llm = llm
        self._crawler = crawler
        self._schema_cache = SchemaCache()

    async def parse(self, url: str) -> ParsedPage:
        """抓取并解析指定 URL。"""
        raw = await self._crawler.fetch(url)

        # 提取纯文本
        text = self._extract_text(raw.get("html", ""))

        # 提取已有 schema 类型
        existing = self._extract_existing_schemas(raw.get("json_ld_scripts", []))

        # 关键词提取（优先 LLM，失败则 fallback）
        keyword, keyword_fallback, keyword_errors = await self._extract_keyword(
            raw.get("title", ""), raw.get("description", ""), text
        )

        # 类型推断（优先 LLM，失败则本地匹配）
        derived_type, type_fallback, type_errors = await self._infer_type(
            raw.get("title", ""), raw.get("description", ""), text, keyword
        )

        page = ParsedPage(
            url=raw.get("url", url),
            title=raw.get("title", ""),
            description=raw.get("description", ""),
            text=text[: self._MAX_TEXT_LEN],
            keyword=keyword,
            derived_type=derived_type,
            existing_schemas=existing,
            images=raw.get("images", []),
            videos=raw.get("videos", []),
            links=raw.get("links", []),
            json_ld_scripts=raw.get("json_ld_scripts", []),
            canonical=raw.get("canonical"),
            og_type=raw.get("og_type"),
            content_blocks=raw.get("content_blocks", []),
            headings=raw.get("headings", []),
            has_ssr=raw.get("has_ssr", True),
            _raw_html=raw.get("html", ""),
            _headers=raw.get("headers", {}),
            _meta={
                "keyword_fallback": keyword_fallback,
                "keyword_errors": keyword_errors,
                "type_fallback": type_fallback,
                "type_errors": type_errors,
            },
        )
        return page

    # ------------------------------------------------------------------
    # 文本提取
    # ------------------------------------------------------------------
    @classmethod
    def _extract_text(cls, html: str) -> str:
        """移除 script/style 和标签，保留可读文本。"""
        import html as html_module

        text = re.sub(r"<script\b[^>]*>[\s\S]*?</script>", " ", html, flags=re.I)
        text = re.sub(r"<style\b[^>]*>[\s\S]*?</style>", " ", text, flags=re.I)
        text = re.sub(r"<[^>]+>", " ", text)
        text = html_module.unescape(text)
        text = re.sub(r"\s+", " ", text).strip()
        return text

    # ------------------------------------------------------------------
    # 已有 Schema 检测
    # ------------------------------------------------------------------
    @classmethod
    def _extract_existing_schemas(cls, json_ld_scripts: List[str]) -> List[str]:
        """从 JSON-LD 脚本中提取 @type 值。"""
        types = []
        for script in json_ld_scripts:
            try:
                data = json.loads(script)
                if isinstance(data, list):
                    for item in data:
                        t = item.get("@type")
                        if isinstance(t, str):
                            types.append(t)
                        elif isinstance(t, list):
                            types.extend(t)
                else:
                    t = data.get("@type")
                    if isinstance(t, str):
                        types.append(t)
                    elif isinstance(t, list):
                        types.extend(t)
            except (json.JSONDecodeError, AttributeError):
                continue
        return list(dict.fromkeys(types))  # 去重保序

    # ------------------------------------------------------------------
    # 关键词提取
    # ------------------------------------------------------------------
    async def _extract_keyword(
        self, title: str, description: str, text: str
    ) -> Tuple[str, bool, List[str]]:
        """提取页面核心关键词，用于 FAQ 等下游模块。

        Returns:
            (keyword, fallback, errors)
        """
        context = f"""标题: {title}
描述: {description}
正文前500字: {text[:500]}"""

        prompt = (
            "从以下网页内容中提取 1-3 个核心关键词（用逗号分隔），"
            "这些关键词将用于生成 FAQ 和权威信号分析。"
            "只返回关键词，不要解释。\n\n" + context
        )

        if self._llm is not None:
            try:
                result = await self._llm.chat(prompt)
                for part in result.strip().split(","):
                    kw = part.strip()
                    if kw:
                        return kw, False, []
            except (RuntimeError, OSError, ValueError) as e:
                return self._keyword_fallback(title, description, text), True, [str(e)]

        # fallback: 基于词频提取
        return self._keyword_fallback(title, description, text), True, []

    @classmethod
    def _keyword_fallback(
        cls, title: str, description: str, text: str
    ) -> str:
        """无 LLM 时的本地关键词提取。"""
        combined = f"{title} {description} {text[:1000]}"

        # 中文分词：优先提取 2-6 字的中文词组
        cn_words = re.findall(r"[\u4e00-\u9fff]{2,6}", combined)
        # 英文单词
        en_words = re.findall(r"[a-zA-Z]{3,}", combined)
        words = cn_words + en_words

        freq: dict = {}
        for w in words:
            w_lower = w.lower()
            if w_lower in cls._STOPWORDS or len(w_lower) < 2:
                continue
            freq[w_lower] = freq.get(w_lower, 0) + 1

        if not freq:
            return "general"

        # 优先选择标题中出现的词
        title_cn = re.findall(r"[\u4e00-\u9fff]{2,6}", title.lower())
        title_en = re.findall(r"[a-zA-Z]{3,}", title.lower())
        title_words = set(title_cn + title_en)
        ranked = sorted(freq.items(), key=lambda x: x[1], reverse=True)
        for word, _ in ranked:
            if word in title_words:
                return word
        return ranked[0][0]

    # ------------------------------------------------------------------
    # 类型推断
    # ------------------------------------------------------------------
    async def _infer_type(
        self, title: str, description: str, text: str, keyword: str
    ) -> Tuple[str, bool, List[str]]:
        """推断最匹配的 Schema.org 类型。

        Returns:
            (derived_type, fallback, errors)
        """
        all_types = self._schema_cache.all_types()
        if not all_types:
            return "WebPage", True, ["schema_cache 为空，无可用类型列表"]

        names_list = ", ".join(all_types[:500])  # 限制 token
        context = f"""页面标题: {title}
页面描述: {description}
核心关键词: {keyword}
正文前300字: {text[:300]}"""

        prompt = (
            f"根据以下网页内容，从 Schema.org 类型列表中选出最匹配的 1 个类型。\n\n"
            f"{context}\n\n"
            f"可选类型（部分）: {names_list}\n\n"
            f"要求:\n"
            f"1. 只返回类型名称，不要解释\n"
            f"2. 如果都不匹配，返回 WebPage"
        )

        if self._llm is not None:
            try:
                result = await self._llm.chat(prompt)
                parts = result.strip().split()
                if parts:
                    t = parts[0].strip("`\"'[]{}<>")
                    if t in all_types:
                        return t, False, []
            except (RuntimeError, OSError, ValueError):
                pass

        # fallback: 本地匹配
        query = f"{title} {description} {keyword}"
        matches = self._schema_cache.local_match(query, top_k=1)
        if matches:
            return matches[0][0], True, []
        return "WebPage", True, []
