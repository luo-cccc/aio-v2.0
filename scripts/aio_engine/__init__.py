"""
aio-engine: 统一 SEO 分析引擎
===========================

统一入口，提供两种执行模式：

1. 简单模式 — analyze()
   适合大多数场景，一行代码完成分析：

       from aio_engine import analyze
       result = await analyze("https://example.com/product")

2. 工作流模式 — Workflow
   适合需要追踪、调试、自定义的场景：

       from aio_engine import Workflow
       wf = Workflow()
       result = await wf.run("https://example.com/product")
       print(result["workflow"]["steps"]["schema"]["durationMs"])

命令行:
    python -m aio_engine --url https://example.com/product
"""

from .lib.llm_client import LLMClient
from .lib.crawler import Crawler
from .lib.cache import Cache
from .lib.schema_cache import SchemaCache
from .modules.page_parser import PageParser, ParsedPage
from .modules.schema_generator import SchemaGenerator
from .modules.semantic_optimizer import SemanticOptimizer
from .modules.faq_generator import FAQGenerator
from .modules.multimodal_labeler import MultimodalLabeler
from .modules.authority_checker import AuthorityChecker
from .modules.citability_scorer import CitabilityScorer
from .modules.robots_checker import RobotsChecker
from .modules.llmstxt_checker import LLMsTxtChecker
from .modules.brand_checker import BrandChecker
from .modules.schema_auditor import SchemaAuditor
from .modules.platform_optimizer import PlatformOptimizer
from .modules.technical_auditor import TechnicalAuditor
from .modules.eeat_scorer import EEATScorer
from .workflow import Workflow, StepResult, WorkflowContext
from .schemas import (
    AnalysisResult,
    ModuleResult,
    Action,
    Meta,
    PageData,
    ScoreDetails,
    WorkflowInfo,
    WorkflowStepInfo,
    EntityLink,
    SemanticTopics,
)

try:
    from .modules.monitor import MonitorTracker
except ImportError:
    MonitorTracker = None

__all__ = [
    # 简单入口
    "analyze",
    # 工作流
    "Workflow",
    "StepResult",
    "WorkflowContext",
    # 输出 schema
    "AnalysisResult",
    "ModuleResult",
    "Action",
    "Meta",
    "PageData",
    "ScoreDetails",
    "WorkflowInfo",
    "WorkflowStepInfo",
    # 基础库
    "LLMClient",
    "Crawler",
    "Cache",
    "SchemaCache",
    # 模块
    "PageParser",
    "ParsedPage",
    "SchemaGenerator",
    "SemanticOptimizer",
    "FAQGenerator",
    "MultimodalLabeler",
    "AuthorityChecker",
    "CitabilityScorer",
    "RobotsChecker",
    "LLMsTxtChecker",
    "BrandChecker",
    "SchemaAuditor",
    "PlatformOptimizer",
    "TechnicalAuditor",
    "EEATScorer",
    "MonitorTracker",
]


async def analyze(url: str) -> dict:
    """
    分析指定 URL，返回完整的 SEO 优化数据集（AnalysisResult 格式）。

    输出包含 moduleResults、scoreDetails、fallback、errors 等底座化字段，
    可直接用 AnalysisResult.from_raw(result) 进行结构化访问。

    如需步骤追踪、hooks、单步调试，请直接使用 Workflow 类。
    """
    wf = Workflow()
    try:
        return await wf.run(url)
    finally:
        await wf.close()
