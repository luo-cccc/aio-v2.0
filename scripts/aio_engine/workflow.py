"""
Workflow Orchestrator
=====================
显式编排 SEO 分析流水线，支持：
- 阶段化执行（串行/并行）
- 条件分支（skip、fallback）
- 执行追踪与日志
- 自定义钩子（hooks）

用法:
    from aio_engine.workflow import Workflow
    wf = Workflow()
    result = await wf.run("https://example.com/product")
"""

import asyncio
import re
import time
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Dict, List, Optional

import aiohttp

from .lib.llm_client import LLMClient
from .lib.crawler import Crawler
from .lib.cache import Cache
from .modules.page_parser import PageParser, ParsedPage
from .modules.schema_generator import SchemaGenerator
from .modules.semantic_optimizer import SemanticOptimizer
from .modules.faq_generator import FAQGenerator
from .modules.citability_scorer import CitabilityScorer
from .modules.robots_checker import RobotsChecker
from .modules.llmstxt_checker import LLMsTxtChecker
from .modules.schema_auditor import SchemaAuditor
from .modules.platform_optimizer import PlatformOptimizer
from .modules.eeat_scorer import EEATScorer


@dataclass
class StepResult:
    """单个步骤的执行结果。"""

    name: str
    status: str  # success | error | skipped | unavailable
    duration_ms: int
    data: dict = field(default_factory=dict)
    error: str = ""


@dataclass
class WorkflowContext:
    """跨步骤共享的上下文数据。"""

    url: str
    page: Optional[ParsedPage] = None
    llm: Optional[LLMClient] = None
    crawler: Optional[Crawler] = None
    results: Dict[str, StepResult] = field(default_factory=dict)


StepHook = Callable[[str, WorkflowContext], Awaitable[None]]

# 模块输入依赖声明：key=模块名，value=依赖的字段列表（来自 ParsedPage）
_MODULE_DEPENDENCIES: Dict[str, List[str]] = {
    "schema": ["title", "description", "url"],
    "semantic": ["text"],
    "faq": ["keyword"],
    "citability": ["content_blocks"],
    "robots": ["url"],
    "llmstxt": ["url"],
    "schema_audit": ["json_ld_scripts"],
    "platform": ["content_blocks", "headings", "_raw_html", "text", "images", "videos"],
    "eeat": ["text", "content_blocks", "headings", "_raw_html"],
    "readability": ["text", "headings"],
}


class Workflow:
    """
    SEO 分析工作流编排器。

    默认执行 3 阶段流水线：
        Phase 1: fetch    -> 抓取并解析页面
        Phase 2: parallel -> schema / semantic / faq / multimodal / authority / monitor
        Phase 3: aggregate-> 聚合所有结果
    """

    def __init__(
        self,
        llm: Optional[LLMClient] = None,
        crawler: Optional[Crawler] = None,
        hooks: Optional[Dict[str, List[StepHook]]] = None,
        cache: Optional[Cache] = None,
        shared_session: bool = True,
    ):
        self._hooks = hooks or {}
        self._cache = cache
        self._shared_session = shared_session
        self._session: Optional[aiohttp.ClientSession] = None
        self._llm = llm
        self._crawler = crawler

    async def _ensure_clients(self) -> None:
        """延迟初始化：若启用共享 session，则创建并注入到 llm 和 crawler。"""
        if self._shared_session and self._session is None:
            self._session = aiohttp.ClientSession()
        if self._llm is None:
            self._llm = LLMClient(session=self._session)
        if self._crawler is None:
            self._crawler = Crawler(session=self._session)

    async def close(self) -> None:
        """关闭共享 session（若由 Workflow 自身创建）。"""
        if self._session is not None:
            await self._session.close()
            self._session = None

    # ------------------------------------------------------------------
    # 公共接口
    # ------------------------------------------------------------------
    async def run(self, url: str) -> dict:
        """
        执行完整工作流。

        若构造时传入了 cache 且命中，直接返回缓存结果。
        返回与 analyze() 兼容的标准化数据集。
        """
        await self._ensure_clients()
        start_time = time.time()

        # 缓存检查
        if self._cache is not None:
            cached = self._cache.get(url)
            if cached is not None:
                cached["meta"]["cacheHit"] = True
                return cached

        ctx = WorkflowContext(url=url, llm=self._llm, crawler=self._crawler)

        # Phase 1
        await self._execute_phase1(ctx)

        # Phase 2
        await self._execute_phase2(ctx)

        # Phase 3
        dataset = self._execute_phase3(ctx, start_time)
        dataset["meta"]["cacheHit"] = False

        # 写入缓存（仅成功时缓存）
        if self._cache is not None and dataset.get("moduleStatuses", {}).get("fetch") == "success":
            self._cache.set(url, dataset)

        return dataset

    async def run_step(self, url: str, step_name: str) -> StepResult:
        """
        单独执行某个步骤（用于调试或按需分析）。

        支持的 step_name:
            fetch, schema, semantic, faq, readability,
            citability, robots, llmstxt, schema_audit, platform, eeat
        """
        await self._ensure_clients()
        ctx = WorkflowContext(url=url, llm=self._llm, crawler=self._crawler)

        try:
            if step_name == "fetch":
                return await self._step_fetch(ctx)

            # 需要先执行 fetch
            await self._step_fetch(ctx)

            step_map = {
                "schema": self._step_schema,
                "semantic": self._step_semantic,
                "faq": self._step_faq,
                "citability": self._step_citability,
                "robots": self._step_robots,
                "llmstxt": self._step_llmstxt,
                "schema_audit": self._step_schema_audit,
                "platform": self._step_platform,
                "eeat": self._step_eeat,
                "readability": self._step_readability,
            }

            fn = step_map.get(step_name)
            if not fn:
                return StepResult(name=step_name, status="error", duration_ms=0, error=f"未知步骤: {step_name}")

            return await fn(ctx)
        finally:
            await self.close()

    # ------------------------------------------------------------------
    # Phase 1: Fetch & Parse
    # ------------------------------------------------------------------
    async def _execute_phase1(self, ctx: WorkflowContext) -> None:
        result = await self._step_fetch(ctx)
        ctx.results["fetch"] = result

    async def _step_fetch(self, ctx: WorkflowContext) -> StepResult:
        return await self._run_step("fetch", ctx, self._do_fetch)

    async def _do_fetch(self, ctx: WorkflowContext) -> dict:
        parser = PageParser(ctx.llm, ctx.crawler)
        ctx.page = await parser.parse(ctx.url)
        return {"page": ctx.page}

    # ------------------------------------------------------------------
    # Phase 2: Parallel Analysis
    # ------------------------------------------------------------------
    async def _execute_phase2(self, ctx: WorkflowContext) -> None:
        if not ctx.page:
            # Phase 1 失败，所有模块标记为依赖缺失
            for name in self._MODULE_NAMES:
                ctx.results[name] = StepResult(
                    name=name,
                    status="error",
                    duration_ms=0,
                    error="Phase 1 fetch 失败，无法执行分析",
                )
            return

        # 基于依赖声明，检查每个模块的输入是否可用
        tasks = {}
        for name in self._MODULE_NAMES:
            missing = self._check_dependencies(name, ctx.page)
            if missing:
                ctx.results[name] = StepResult(
                    name=name,
                    status="skipped",
                    duration_ms=0,
                    error=f"依赖缺失: {', '.join(missing)}",
                )
                continue
            step_fn = getattr(self, f"_step_{name}")
            tasks[name] = step_fn(ctx)

        if tasks:
            results = await asyncio.gather(*tasks.values(), return_exceptions=True)
            for name, result in zip(tasks.keys(), results):
                if isinstance(result, Exception):
                    ctx.results[name] = StepResult(
                        name=name, status="error", duration_ms=0, error=str(result)
                    )
                else:
                    ctx.results[name] = result

    def _check_dependencies(self, name: str, page: ParsedPage) -> List[str]:
        """检查模块输入依赖是否满足，返回缺失字段列表。

        空列表不视为缺失（模块内部自行处理空输入）。
        """
        deps = _MODULE_DEPENDENCIES.get(name, [])
        missing = []
        for field in deps:
            value = getattr(page, field, None)
            if value is None or value == "":
                missing.append(field)
        return missing

    _MODULE_NAMES: tuple = (
        "schema", "semantic", "faq",
        "citability", "robots", "llmstxt",
        "schema_audit", "platform", "eeat", "readability",
    )

    async def _step_schema(self, ctx: WorkflowContext) -> StepResult:
        return await self._run_step("schema", ctx, self._do_schema)

    async def _do_schema(self, ctx: WorkflowContext) -> dict:
        gen = SchemaGenerator(ctx.llm)
        return gen.generate(ctx.page)

    async def _step_semantic(self, ctx: WorkflowContext) -> StepResult:
        return await self._run_step("semantic", ctx, self._do_semantic)

    async def _do_semantic(self, ctx: WorkflowContext) -> dict:
        opt = SemanticOptimizer(ctx.llm)
        return await opt.optimize(ctx.page.text)

    async def _step_faq(self, ctx: WorkflowContext) -> StepResult:
        return await self._run_step("faq", ctx, self._do_faq)

    async def _do_faq(self, ctx: WorkflowContext) -> dict:
        gen = FAQGenerator(ctx.llm)
        return await gen.generate(ctx.page.keyword)

    async def _step_citability(self, ctx: WorkflowContext) -> StepResult:
        return await self._run_step("citability", ctx, self._do_citability)

    async def _do_citability(self, ctx: WorkflowContext) -> dict:
        scorer = CitabilityScorer()
        return scorer.analyze(ctx.page.content_blocks)

    async def _step_robots(self, ctx: WorkflowContext) -> StepResult:
        return await self._run_step("robots", ctx, self._do_robots)

    async def _do_robots(self, ctx: WorkflowContext) -> dict:
        robots_raw = await ctx.crawler.fetch_robots_txt(ctx.url)
        checker = RobotsChecker()
        return checker.check(robots_raw)

    async def _step_llmstxt(self, ctx: WorkflowContext) -> StepResult:
        return await self._run_step("llmstxt", ctx, self._do_llmstxt)

    async def _do_llmstxt(self, ctx: WorkflowContext) -> dict:
        llms_raw = await ctx.crawler.fetch_llms_txt(ctx.url)
        checker = LLMsTxtChecker()
        return checker.check(llms_raw)

    async def _step_schema_audit(self, ctx: WorkflowContext) -> StepResult:
        return await self._run_step("schema_audit", ctx, self._do_schema_audit)

    async def _do_schema_audit(self, ctx: WorkflowContext) -> dict:
        auditor = SchemaAuditor()
        return auditor.audit(ctx.page.json_ld_scripts, ctx.page.derived_type)

    async def _step_platform(self, ctx: WorkflowContext) -> StepResult:
        return await self._run_step("platform", ctx, self._do_platform)

    async def _do_platform(self, ctx: WorkflowContext) -> dict:
        from .lib.html_utils import extract_html_features
        optimizer = PlatformOptimizer()
        html = ctx.page._raw_html
        features = extract_html_features(html)
        return optimizer.analyze(
            content_blocks=ctx.page.content_blocks,
            headings=ctx.page.headings,
            has_tables=features["has_tables"],
            has_lists=features["has_lists"],
            has_faq=features["has_faq"],
            has_author=features["has_author"],
            has_dates=features["has_dates"],
            word_count=len(ctx.page.text.split()) if ctx.page.text else 0,
            images_count=len(ctx.page.images),
            videos_count=len(ctx.page.videos),
        )

    async def _step_eeat(self, ctx: WorkflowContext) -> StepResult:
        return await self._run_step("eeat", ctx, self._do_eeat)

    async def _do_eeat(self, ctx: WorkflowContext) -> dict:
        from .lib.html_utils import extract_html_features
        scorer = EEATScorer()
        html = ctx.page._raw_html
        features = extract_html_features(html)
        return scorer.analyze(
            text=ctx.page.text,
            html=html,
            headings=ctx.page.headings,
            content_blocks=ctx.page.content_blocks,
            has_author=features["has_author"],
            author_name=features["author_name"],
            has_dates=features["has_dates"],
            has_reviews=features["has_reviews"],
            word_count=len(ctx.page.text.split()) if ctx.page.text else 0,
        )

    async def _step_readability(self, ctx: WorkflowContext) -> StepResult:
        return await self._run_step("readability", ctx, self._do_readability)

    async def _do_readability(self, ctx: WorkflowContext) -> dict:
        from .modules.readability_analyzer import ReadabilityAnalyzer
        analyzer = ReadabilityAnalyzer()
        return analyzer.analyze(ctx.page.text, ctx.page.headings)

    # ------------------------------------------------------------------
    # Phase 3: Aggregate
    # ------------------------------------------------------------------
    def _execute_phase3(self, ctx: WorkflowContext, start_time: float) -> dict:
        module_results: Dict[str, dict] = {}
        actions: List[dict] = []
        module_statuses: Dict[str, str] = {}

        for name, step_result in ctx.results.items():
            if name == "fetch":
                continue

            status = step_result.status
            result = step_result.data
            module_statuses[name] = status

            # 构建 moduleResults 条目
            mod_entry: dict = {
                "status": status,
                "data": {},
                "score": result.get("score") if result else None,
                "scoreDetails": result.get("score_details") if result else None,
                "errors": result.get("errors", []) if result else [],
                "fallback": result.get("fallback", False) if result else False,
            }

            if status == "success" and result:
                actions.extend(result.get("recommended_actions", []))

                # 将模块特有数据放入 data 字段
                if name == "schema":
                    mod_entry["data"] = {
                        "schemas": result.get("schemas", {}),
                        "entities": result.get("entities", {}),
                    }
                elif name == "semantic":
                    mod_entry["data"] = {
                        "optimized_text": result.get("optimized_text", ""),
                        "diagnosis": result.get("diagnosis", {}),
                        "scenarios": result.get("scenarios", []),
                        "cite_worthy_snippets": result.get("cite_worthy_snippets", []),
                        "semantic_topics": result.get("semantic_topics", {}),
                    }
                elif name == "faq":
                    mod_entry["data"] = {"faq_html": result.get("faq_html", "")}
                elif name == "citability":
                    mod_entry["data"] = {
                        "blocks": result.get("blocks", []),
                        "page_metrics": result.get("page_metrics", {}),
                    }
                elif name == "robots":
                    mod_entry["data"] = {
                        "ai_crawler_status": result.get("ai_crawler_status", {}),
                        "sitemaps": result.get("sitemaps", []),
                    }
                elif name == "llmstxt":
                    mod_entry["data"] = {
                        "exists": result.get("exists", False),
                        "format_valid": result.get("format_valid", False),
                        "issues": result.get("issues", []),
                        "suggestions": result.get("suggestions", []),
                        "section_count": result.get("section_count", 0),
                        "link_count": result.get("link_count", 0),
                        "full_version_exists": result.get("full_version_exists", False),
                    }
                elif name == "schema_audit":
                    mod_entry["data"] = {
                        "schemas_found": result.get("schemas_found", []),
                        "issues": result.get("issues", []),
                        "suggestions": result.get("suggestions", []),
                    }
                elif name == "platform":
                    mod_entry["data"] = {
                        "platforms": result.get("platforms", {}),
                        "universal_actions": result.get("universal_actions", []),
                    }
                elif name == "eeat":
                    mod_entry["data"] = {
                        "dimensions": result.get("dimensions", {}),
                        "content_quality": result.get("content_quality", {}),
                    }
                elif name == "readability":
                    mod_entry["data"] = {
                        "flesch_reading_ease": result.get("flesch_reading_ease", 0),
                        "flesch_kincaid_grade": result.get("flesch_kincaid_grade", 0),
                        "avg_sentence_length": result.get("avg_sentence_length", 0),
                        "avg_paragraph_length": result.get("avg_paragraph_length", 0),
                        "passive_voice_ratio": result.get("passive_voice_ratio", 0),
                        "long_sentences_count": result.get("long_sentences_count", 0),
                        "complex_words_ratio": result.get("complex_words_ratio", 0),
                        "sentence_count": result.get("sentence_count", 0),
                        "word_count": result.get("word_count", 0),
                    }
            elif status in ("skipped", "unavailable", "error") and result:
                # 保留 error/skipped 状态下的 data（如 monitor 的 unavailable 数据）
                mod_entry["data"] = {k: v for k, v in result.items()
                                     if k not in ("status", "score", "score_details",
                                                  "errors", "fallback", "recommended_actions")}

            module_results[name] = mod_entry

        # 自动派生 GEO actions：扫描 semanticTopics.missing 和实体链接状态
        geo_actions = self._derive_geo_actions(module_results)
        actions.extend(geo_actions)

        # 去重 + 排序 actions
        priority_order = {"high": 0, "medium": 1, "low": 2}
        actions.sort(key=lambda a: priority_order.get(a.get("priority", "low"), 2))
        seen = set()
        unique_actions = []
        for a in actions:
            key = a.get("action", "")
            if key not in seen:
                seen.add(key)
                unique_actions.append(a)

        duration_ms = round((time.time() - start_time) * 1000)

        # 计算 overall score
        scores = [m["score"] for m in module_results.values() if m.get("score") is not None]
        overall = round(sum(scores) / len(scores)) if scores else None

        # 组装 GEO 字段（从 moduleResults 中提取）
        semantic_mod = module_results.get("semantic", {}).get("data", {})
        schema_mod = module_results.get("schema", {}).get("data", {})
        geo = {
            "citeWorthySnippets": semantic_mod.get("cite_worthy_snippets", []),
            "semanticTopics": semantic_mod.get("semantic_topics", {}),
            "entities": schema_mod.get("entities", {}),
        }

        return {
            "meta": {
                "url": ctx.url,
                "analyzedAt": self._iso_now(),
                "durationMs": duration_ms,
                "version": "2.0.0",
            },
            "pageData": {
                "title": ctx.page.title if ctx.page else "",
                "description": ctx.page.description if ctx.page else "",
                "type": ctx.page.derived_type if ctx.page else "",
                "existingSchemas": ctx.page.existing_schemas if ctx.page else [],
            },
            "moduleResults": module_results,
            "geo": geo,
            "actions": unique_actions,
            "moduleStatuses": module_statuses,
            "scores": {"overall": overall},
            "workflow": {
                "steps": {
                    name: {
                        "status": r.status,
                        "durationMs": r.duration_ms,
                        "error": r.error,
                    }
                    for name, r in ctx.results.items()
                }
            },
        }

    # ------------------------------------------------------------------
    # 通用执行封装
    # ------------------------------------------------------------------
    async def _run_step(
        self,
        name: str,
        ctx: WorkflowContext,
        fn: Callable[[WorkflowContext], Awaitable[dict]],
    ) -> StepResult:
        await self._call_hooks("before", name, ctx)
        t0 = time.time()
        try:
            data = await fn(ctx)
            status = data.get("status", "success")
            duration_ms = round((time.time() - t0) * 1000)
            result = StepResult(name=name, status=status, duration_ms=duration_ms, data=data)
        except (RuntimeError, OSError, ValueError, aiohttp.ClientError) as e:
            duration_ms = round((time.time() - t0) * 1000)
            result = StepResult(
                name=name, status="error", duration_ms=duration_ms, error=str(e)
            )
        await self._call_hooks("after", name, ctx)
        return result

    async def _call_hooks(self, timing: str, step_name: str, ctx: WorkflowContext) -> None:
        key = f"{timing}:{step_name}"
        for hook in self._hooks.get(key, []):
            await hook(step_name, ctx)

    @staticmethod
    def _derive_geo_actions(module_results: Dict[str, dict]) -> List[dict]:
        """扫描模块结果，自动派生 GEO 特化 actions。"""
        geo_actions = []

        # 1. 扫描 semanticTopics.missing，为每个缺失主题生成 action
        semantic_mod = module_results.get("semantic", {})
        if semantic_mod.get("status") == "success":
            topics = semantic_mod.get("data", {}).get("semantic_topics", {})
            for topic in topics.get("missing", []):
                geo_actions.append({
                    "action": f"补充关于 '{topic}' 的内容段落，提升主题覆盖度",
                    "priority": "medium",
                    "target_module": "semantic_optimizer",
                    "params": {"missing_topic": topic},
                })

        # 2. 扫描 entities，提示补充 sameAs/identifier
        schema_mod = module_results.get("schema", {})
        if schema_mod.get("status") == "success":
            entities = schema_mod.get("data", {}).get("entities", {})
            for entity_type, entity_info in entities.items():
                if not entity_info.get("sameAs") and not entity_info.get("wikidata"):
                    name = entity_info.get("name") or "未命名"
                    geo_actions.append({
                        "action": f"为 {entity_type} '{name}' 添加 sameAs/Wikidata 链接",
                        "priority": "medium",
                        "target_module": "schema_generator",
                        "params": {"entity_type": entity_type, "entity_name": name},
                    })

        return geo_actions

    @staticmethod
    def _iso_now() -> str:
        from datetime import datetime, timezone
        return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
