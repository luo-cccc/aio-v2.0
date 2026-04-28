"""
模块独立入口
============
每个模块提供独立的异步函数，可直接调用，无需走完整 Workflow。
所有函数返回统一的 ModuleResult 格式（dict）。

用法:
    from aio_engine.modules import generate_faq, check_robots
    faq_result = await generate_faq("https://example.com")
    robots_result = await check_robots("https://example.com")

高级用法（共享 session）:
    import aiohttp
    from aio_engine.modules import generate_schema, check_robots

    async with aiohttp.ClientSession() as session:
        schema = await generate_schema("https://example.com", session=session)
        robots = await check_robots("https://example.com", session=session)
"""

import asyncio
from typing import Optional

import aiohttp

from ..lib.crawler import Crawler
from ..lib.llm_client import LLMClient
from ..lib.cache import Cache
from ..workflow import Workflow

from .page_parser import PageParser
from .schema_generator import SchemaGenerator
from .semantic_optimizer import SemanticOptimizer
from .faq_generator import FAQGenerator
from .citability_scorer import CitabilityScorer
from .robots_checker import RobotsChecker
from .llmstxt_checker import LLMsTxtChecker
from .schema_auditor import SchemaAuditor
from .platform_optimizer import PlatformOptimizer
from .eeat_scorer import EEATScorer


# ------------------------------------------------------------------
# 通用辅助：抓取并解析页面
# ------------------------------------------------------------------
async def _fetch_and_parse(
    url: str,
    crawler: Optional[Crawler] = None,
    session: Optional[aiohttp.ClientSession] = None,
) -> dict:
    """抓取 URL 并解析页面，返回 {page, html, headers}。

    若传入外部 crawler，使用之且不负责关闭。
    若仅传入 session，创建 Crawler(session=session) 并在完成后关闭。
    """
    own_crawler = False
    if crawler is not None:
        c = crawler
    elif session is not None:
        c = Crawler(session=session)
        own_crawler = True
    else:
        c = Crawler()
        own_crawler = True

    try:
        # PageParser.parse 内部会调用 crawler.fetch，无需预先 fetch
        parser = PageParser(None, c)
        page = await parser.parse(url)
        return {"page": page, "html": page._raw_html, "headers": page._headers}
    finally:
        if own_crawler:
            # Crawler 本身不持有 session 生命周期（外部传入时不关闭）
            # 但 Crawler 自己创建的 session 需要关闭
            # Crawler 没有 close 方法，session 由 Crawler._session_ctx 管理
            # 当 Crawler 自己创建 session 时，fetch 完成后 session 已关闭
            pass


# ------------------------------------------------------------------
# 1. Schema 生成
# ------------------------------------------------------------------
async def generate_schema(
    url: str,
    llm: Optional[LLMClient] = None,
    session: Optional[aiohttp.ClientSession] = None,
) -> dict:
    """
    推断页面 Schema.org 类型并生成 JSON-LD 框架。

    Returns ModuleResult dict with data.schemas, data.entities.
    """
    ctx = await _fetch_and_parse(url, session=session)
    page = ctx["page"]
    client = llm or LLMClient()
    try:
        gen = SchemaGenerator(client)
        return await gen.generate(page.derived_type, page)
    finally:
        if llm is None:
            await client.close()


# ------------------------------------------------------------------
# 2. 语义优化
# ------------------------------------------------------------------
async def optimize_semantic(
    url: str,
    llm: Optional[LLMClient] = None,
    session: Optional[aiohttp.ClientSession] = None,
) -> dict:
    """
    诊断并改写页面文案，生成 GEO 可引用片段和主题覆盖分析。

    Returns ModuleResult dict with data.optimized_text, data.cite_worthy_snippets, data.semantic_topics.
    """
    ctx = await _fetch_and_parse(url, session=session)
    page = ctx["page"]
    client = llm or LLMClient()
    try:
        opt = SemanticOptimizer(client)
        return await opt.optimize(page.text)
    finally:
        if llm is None:
            await client.close()


# ------------------------------------------------------------------
# 3. FAQ 生成
# ------------------------------------------------------------------
async def generate_faq(
    url: str,
    llm: Optional[LLMClient] = None,
    session: Optional[aiohttp.ClientSession] = None,
) -> dict:
    """
    围绕页面关键词自动生成 FAQ 内容。

    Returns ModuleResult dict with data.faq_html.
    """
    ctx = await _fetch_and_parse(url, session=session)
    page = ctx["page"]
    client = llm or LLMClient()
    try:
        gen = FAQGenerator(client)
        return await gen.generate(page.keyword)
    finally:
        if llm is None:
            await client.close()


# ------------------------------------------------------------------
# 4. 多模态标注
# ------------------------------------------------------------------
async def analyze_multimodal(
    url: str,
    llm: Optional[LLMClient] = None,
    session: Optional[aiohttp.ClientSession] = None,
) -> dict:
    """
    检测图片 alt 缺失/无意义，生成 VideoObject Schema。

    Returns ModuleResult dict with data.alt_texts, data.video_objects.
    """
    ctx = await _fetch_and_parse(url, session=session)
    page = ctx["page"]
    client = llm or LLMClient()
    try:
        c = Crawler(session=session) if session else Crawler()
        labeler = MultimodalLabeler(client, c)
        return await labeler.analyze(page.images, page.videos)
    finally:
        if llm is None:
            await client.close()


# ------------------------------------------------------------------
# 5. 权威信号检查
# ------------------------------------------------------------------
async def check_authority(
    url: str,
    llm: Optional[LLMClient] = None,
    session: Optional[aiohttp.ClientSession] = None,
    lang: Optional[str] = None,
) -> dict:
    """
    分析外部权威信号覆盖情况（中文/英文平台自动检测）。

    Args:
        url: 要分析的网页 URL
        llm: 可选 LLMClient 实例
        session: 可选共享 aiohttp ClientSession
        lang: 可选语言指定 "zh" 或 "en"，默认自动检测

    Returns ModuleResult dict with data.platform_coverage, data.strategy.
    """
    ctx = await _fetch_and_parse(url, session=session)
    page = ctx["page"]
    client = llm or LLMClient()
    try:
        checker = AuthorityChecker(client)
        return await checker.check(page.title, page.keyword, lang=lang)
    finally:
        if llm is None:
            await client.close()


# ------------------------------------------------------------------
# 6. 可引用性评分
# ------------------------------------------------------------------
async def score_citability(
    url: str,
    session: Optional[aiohttp.ClientSession] = None,
) -> dict:
    """
    5 维度评分内容块的可被 AI 引用质量。

    Returns ModuleResult dict with data.blocks, data.page_metrics.
    """
    ctx = await _fetch_and_parse(url, session=session)
    page = ctx["page"]
    scorer = CitabilityScorer()
    return scorer.analyze(page.content_blocks)


# ------------------------------------------------------------------
# 7. AI 爬虫检测
# ------------------------------------------------------------------
async def check_robots(
    url: str,
    session: Optional[aiohttp.ClientSession] = None,
) -> dict:
    """
    检测 robots.txt 对 14 个 AI 爬虫的允许/封禁状态。

    Returns ModuleResult dict with data.ai_crawler_status, data.sitemaps.
    """
    c = Crawler(session=session) if session else Crawler()
    robots_raw = await c.fetch_robots_txt(url)
    checker = RobotsChecker()
    return checker.check(robots_raw)


# ------------------------------------------------------------------
# 8. LLMs.txt 验证
# ------------------------------------------------------------------
async def check_llmstxt(
    url: str,
    session: Optional[aiohttp.ClientSession] = None,
) -> dict:
    """
    检测 llms.txt / llms-full.txt 存在性和格式合规性。

    Returns ModuleResult dict with data.exists, data.format_valid, data.issues, data.suggestions.
    """
    c = Crawler(session=session) if session else Crawler()
    llms_raw = await c.fetch_llms_txt(url)
    checker = LLMsTxtChecker()
    return checker.check(llms_raw)


# ------------------------------------------------------------------
# 9. 品牌提及检测
# ------------------------------------------------------------------
async def check_brand(
    url: str,
    session: Optional[aiohttp.ClientSession] = None,
) -> dict:
    """
    检测品牌在 Wikipedia/Wikidata 等平台的 presence。

    Returns ModuleResult dict with data.platforms.
    """
    ctx = await _fetch_and_parse(url, session=session)
    page = ctx["page"]
    checker = BrandChecker()
    return await checker.check(page.title, url)


# ------------------------------------------------------------------
# 10. Schema 审计
# ------------------------------------------------------------------
async def audit_schema(
    url: str,
    session: Optional[aiohttp.ClientSession] = None,
) -> dict:
    """
    审计页面现有 JSON-LD structured data，检测缺失和错误。

    Returns ModuleResult dict with data.schemas_found, data.issues, data.suggestions.
    """
    ctx = await _fetch_and_parse(url, session=session)
    page = ctx["page"]
    auditor = SchemaAuditor()
    return auditor.audit(page.json_ld_scripts, page.derived_type)


# ------------------------------------------------------------------
# 11. 平台优化评分
# ------------------------------------------------------------------
async def score_platform(
    url: str,
    session: Optional[aiohttp.ClientSession] = None,
) -> dict:
    """
    针对 5 个 AI 搜索平台（Google AIO、ChatGPT、Perplexity、Gemini、Bing Copilot）评分。

    Returns ModuleResult dict with data.platforms, data.universal_actions.
    """
    from ..lib.html_utils import extract_html_features
    ctx = await _fetch_and_parse(url, session=session)
    page = ctx["page"]
    features = extract_html_features(ctx["html"])
    optimizer = PlatformOptimizer()
    return optimizer.analyze(
        content_blocks=page.content_blocks,
        headings=page.headings,
        has_tables=features["has_tables"],
        has_lists=features["has_lists"],
        has_faq=features["has_faq"],
        has_author=features["has_author"],
        has_dates=features["has_dates"],
        word_count=len(page.text.split()) if page.text else 0,
        images_count=len(page.images),
        videos_count=len(page.videos),
    )


# ------------------------------------------------------------------
# 12. 技术 SEO 审计
# ------------------------------------------------------------------
async def audit_technical(
    url: str,
    session: Optional[aiohttp.ClientSession] = None,
) -> dict:
    """
    8 维度技术 SEO 审计（可爬性、可索引性、安全、URL、移动、CWV、SSR、速度）。

    Returns ModuleResult dict with data.categories, data.critical_issues.
    """
    ctx = await _fetch_and_parse(url, session=session)
    page = ctx["page"]
    html = ctx["html"]
    headers = ctx["headers"]
    c = Crawler(session=session) if session else Crawler()
    robots_raw = await c.fetch_robots_txt(url)
    robots_checker = RobotsChecker()
    robots_result = robots_checker.check(robots_raw)
    auditor = TechnicalAuditor()
    return auditor.audit(
        html=html,
        headers=headers,
        has_ssr=page.has_ssr,
        robots_result=robots_result,
        canonical=page.canonical,
        og_type=page.og_type,
    )


# ------------------------------------------------------------------
# 13. E-E-A-T 评分
# ------------------------------------------------------------------
async def score_eeat(
    url: str,
    session: Optional[aiohttp.ClientSession] = None,
) -> dict:
    """
    4 维度内容质量评分（Experience, Expertise, Authoritativeness, Trustworthiness）。

    Returns ModuleResult dict with data.dimensions, data.content_quality.
    """
    from ..lib.html_utils import extract_html_features
    ctx = await _fetch_and_parse(url, session=session)
    page = ctx["page"]
    features = extract_html_features(ctx["html"])
    scorer = EEATScorer()
    return scorer.analyze(
        text=page.text,
        html=ctx["html"],
        headings=page.headings,
        content_blocks=page.content_blocks,
        has_author=features["has_author"],
        author_name=features["author_name"],
        has_dates=features["has_dates"],
        has_reviews=features["has_reviews"],
        word_count=len(page.text.split()) if page.text else 0,
    )


# ------------------------------------------------------------------
# 14. GSC 监控（可选）
# ------------------------------------------------------------------
async def track_monitor(url: str) -> dict:
    """
    追踪 GSC 搜索数据（点击、展示、CTR、排名趋势）。

    Returns ModuleResult dict with data.metrics, data.trend.
    若 GSC 依赖未安装，返回 unavailable 状态。
    """
    if not _HAS_MONITOR:
        return {
            "status": "unavailable",
            "score": 0,
            "metrics": {},
            "trend": "unavailable",
            "fallback": False,
            "errors": [],
            "recommended_actions": [
                {"action": "Google API 客户端未安装，monitor 模块不可用", "priority": "low"}
            ],
        }
    tracker = MonitorTracker()
    return await tracker.track(url)


__all__ = [
    # 独立异步函数
    "generate_schema",
    "optimize_semantic",
    "generate_faq",
    "analyze_multimodal",
    "check_authority",
    "score_citability",
    "check_robots",
    "check_llmstxt",
    "check_brand",
    "audit_schema",
    "score_platform",
    "audit_technical",
    "score_eeat",
    "track_monitor",
]
