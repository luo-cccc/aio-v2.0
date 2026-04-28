"""
Output Schema Definitions
=========================
用 dataclasses 定义引擎输出的结构化模型，确保字段稳定、类型明确。

用法:
    from aio_engine.schemas import AnalysisResult, ModuleResult
    result = AnalysisResult.from_raw(await analyze(url))
    print(result.meta.version)
    print(result.module_results["schema"].score_details)
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class Meta:
    """分析元数据。"""

    url: str
    analyzed_at: str
    duration_ms: int
    version: str = "1.0.0"
    cache_hit: bool = False


@dataclass
class PageData:
    """页面基础信息。"""

    title: str
    description: str
    type: str
    existing_schemas: List[str] = field(default_factory=list)


@dataclass
class EntityLink:
    """实体链接信息，用于 GEO 实体识别。"""

    name: str
    same_as: List[str] = field(default_factory=list)
    wikidata: str = ""


@dataclass
class SemanticTopics:
    """语义主题覆盖分析。"""

    expected: List[str] = field(default_factory=list)
    covered: List[str] = field(default_factory=list)
    missing: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "expected": self.expected,
            "covered": self.covered,
            "missing": self.missing,
        }

    @classmethod
    def from_raw(cls, raw: dict) -> "SemanticTopics":
        return cls(
            expected=raw.get("expected", []),
            covered=raw.get("covered", []),
            missing=raw.get("missing", []),
        )


@dataclass
class ScoreDetails:
    """评分明细。兼容模块返回的任意 flat dict。"""

    raw: dict = field(default_factory=dict)

    def __post_init__(self):
        # 兼容旧格式 deductions/source
        if not self.raw:
            self.raw = {}

    def get(self, key: str, default=None):
        return self.raw.get(key, default)

    def to_dict(self) -> Optional[dict]:
        return self.raw if self.raw else None


@dataclass
class ModuleResult:
    """单个分析模块的标准化输出。"""

    status: str  # success | error | skipped | unavailable
    data: dict = field(default_factory=dict)
    score: Optional[int] = None
    score_details: Optional[ScoreDetails] = None
    errors: List[str] = field(default_factory=list)
    fallback: bool = False


@dataclass
class Action:
    """可执行的改进行动。"""

    action: str
    priority: str  # high | medium | low
    target_module: str = ""
    params: dict = field(default_factory=dict)
    reason: str = ""


@dataclass
class WorkflowStepInfo:
    """工作流步骤执行信息。"""

    status: str
    duration_ms: int
    error: str = ""


@dataclass
class WorkflowInfo:
    """工作流追踪信息。"""

    steps: Dict[str, WorkflowStepInfo] = field(default_factory=dict)


@dataclass
class AnalysisResult:
    """
    标准化分析结果。

    这是机器消费的核心契约，所有字段类型固定，null 和 "" 语义区分明确。
    """

    meta: Meta
    page_data: PageData
    module_results: Dict[str, ModuleResult]
    actions: List[Action]
    module_statuses: Dict[str, str]
    workflow: Optional[WorkflowInfo] = None

    @property
    def overall_score(self) -> Optional[int]:
        """计算综合评分。"""
        scores = [
            m.score for m in self.module_results.values()
            if m.score is not None
        ]
        if not scores:
            return None
        return round(sum(scores) / len(scores))

    @classmethod
    def from_raw(cls, raw: dict) -> "AnalysisResult":
        """
        从原始 dict（analyze/workflow 输出）构造标准化结果。

        兼容旧格式，同时支持新 moduleResults 格式。
        """
        meta = Meta(
            url=raw.get("meta", {}).get("url", ""),
            analyzed_at=raw.get("meta", {}).get("analyzedAt", ""),
            duration_ms=raw.get("meta", {}).get("durationMs", 0),
            version=raw.get("meta", {}).get("version", "1.0.0"),
            cache_hit=raw.get("meta", {}).get("cacheHit", False),
        )

        page_data = PageData(
            title=raw.get("pageData", {}).get("title", ""),
            description=raw.get("pageData", {}).get("description", ""),
            type=raw.get("pageData", {}).get("type", ""),
            existing_schemas=raw.get("pageData", {}).get("existingSchemas", []),
        )

        # 优先使用新的 moduleResults 格式，回退到旧格式
        module_results: Dict[str, ModuleResult] = {}
        raw_modules = raw.get("moduleResults", {})

        if raw_modules:
            for name, mod in raw_modules.items():
                score_details = None
                sd = mod.get("scoreDetails") or mod.get("score_details")
                if sd:
                    score_details = ScoreDetails(raw=sd)
                module_results[name] = ModuleResult(
                    status=mod.get("status", "error"),
                    data=mod.get("data", {}),
                    score=mod.get("score"),
                    score_details=score_details,
                    errors=mod.get("errors", []),
                    fallback=mod.get("fallback", False),
                )
        else:
            # 兼容旧格式：从各独立字段提取
            scores = raw.get("scores", {})
            statuses = raw.get("moduleStatuses", {})
            content = raw.get("content", {})
            schemas = raw.get("schemas", {})

            for name in (
                "schema", "semantic", "faq", "readability",
                "citability", "robots", "llmstxt", "schema_audit",
                "platform", "eeat",
            ):
                status = statuses.get(name, "error")
                data: dict = {}
                # 旧格式 score 命名规则：schemaScore, semanticScore, ...
                score = scores.get(f"{name}Score") if name != "schema_audit" else scores.get("schemaAuditScore")
                if name == "schema_audit" and score is None:
                    score = scores.get("schema_audit_score")

                if name == "schema" and schemas:
                    data = {"schemas": schemas}
                elif name == "semantic":
                    data = {"optimized_text": content.get("optimizedDescription", "")}
                elif name == "faq":
                    data = {"faq_html": content.get("faqHtml", "")}
                elif name == "readability":
                    data = {
                        "readability_metrics": content.get("readabilityMetrics", {}),
                    }
                elif name == "citability":
                    data = {
                        "blocks": content.get("citabilityBlocks", []),
                        "page_metrics": content.get("citabilityMetrics", {}),
                    }
                elif name == "robots":
                    data = {
                        "ai_crawler_status": content.get("aiCrawlerStatus", {}),
                        "sitemaps": content.get("sitemaps", []),
                    }
                elif name == "llmstxt":
                    data = {
                        "exists": content.get("llmsTxtExists", False),
                        "format_valid": content.get("llmsTxtValid", False),
                        "issues": content.get("llmsTxtIssues", []),
                        "suggestions": content.get("llmsTxtSuggestions", []),
                    }
                elif name == "schema_audit":
                    data = {
                        "schemas_found": content.get("schemasFound", []),
                        "issues": content.get("schemaIssues", []),
                        "suggestions": content.get("schemaSuggestions", []),
                    }
                elif name == "platform":
                    data = {
                        "platforms": content.get("platformScores", {}),
                        "universal_actions": content.get("universalActions", []),
                    }
                elif name == "eeat":
                    data = {
                        "dimensions": content.get("eeatDimensions", {}),
                        "content_quality": content.get("contentQuality", {}),
                    }

                module_results[name] = ModuleResult(
                    status=status,
                    data=data,
                    score=score,
                )

        actions = [
            Action(
                action=a.get("action", ""),
                priority=a.get("priority", "low"),
                target_module=a.get("targetModule", ""),
                params=a.get("params", {}),
                reason=a.get("reason", ""),
            )
            for a in raw.get("actions", [])
        ]

        # GEO 增强字段保留在 module_results.data 中，无需额外处理
        # - schema.data.entities
        # - semantic.data.cite_worthy_snippets
        # - semantic.data.semantic_topics

        workflow = None
        if "workflow" in raw:
            wf = raw["workflow"]
            steps = {
                name: WorkflowStepInfo(
                    status=s.get("status", ""),
                    duration_ms=s.get("durationMs", 0),
                    error=s.get("error", ""),
                )
                for name, s in wf.get("steps", {}).items()
            }
            workflow = WorkflowInfo(steps=steps)

        return cls(
            meta=meta,
            page_data=page_data,
            module_results=module_results,
            actions=actions,
            module_statuses=raw.get("moduleStatuses", {}),
            workflow=workflow,
        )

    def to_dict(self) -> dict:
        """序列化为 dict，保持字段稳定。"""
        result = {
            "meta": {
                "url": self.meta.url,
                "analyzedAt": self.meta.analyzed_at,
                "durationMs": self.meta.duration_ms,
                "version": self.meta.version,
                "cacheHit": self.meta.cache_hit,
            },
            "pageData": {
                "title": self.page_data.title,
                "description": self.page_data.description,
                "type": self.page_data.type,
                "existingSchemas": self.page_data.existing_schemas,
            },
            "moduleResults": {
                name: {
                    "status": m.status,
                    "data": m.data,
                    "score": m.score,
                    "scoreDetails": m.score_details.to_dict() if m.score_details else None,
                    "errors": m.errors,
                    "fallback": m.fallback,
                }
                for name, m in self.module_results.items()
            },
            "actions": [
                {
                    "action": a.action,
                    "priority": a.priority,
                    "targetModule": a.target_module,
                    "params": a.params,
                    "reason": a.reason,
                }
                for a in self.actions
            ],
            "moduleStatuses": self.module_statuses,
        }

        if self.workflow:
            result["workflow"] = {
                "steps": {
                    name: {
                        "status": s.status,
                        "durationMs": s.duration_ms,
                        "error": s.error,
                    }
                    for name, s in self.workflow.steps.items()
                }
            }

        return result
