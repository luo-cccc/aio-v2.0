"""
Integration tests for Article-GEO Optimizer v2.0.0
Verifies module lists, dependencies, and result schemas.
"""

import sys

sys.path.insert(0, "scripts")

from aio_engine.workflow import Workflow, _MODULE_DEPENDENCIES
from aio_engine.schemas import AnalysisResult
from aio_engine.modules.readability_analyzer import ReadabilityAnalyzer


_EXPECTED_MODULES = {
    "schema", "semantic", "faq", "readability",
    "citability", "robots", "llmstxt",
    "schema_audit", "platform", "eeat",
}


def test_module_names_complete():
    """_MODULE_NAMES must contain exactly the 10 article-GEO modules."""
    actual = set(Workflow._MODULE_NAMES)
    assert actual == _EXPECTED_MODULES, f"Module mismatch: expected {_EXPECTED_MODULES}, got {actual}"


def test_module_dependencies_complete():
    """Each module must have declared input dependencies."""
    actual = set(_MODULE_DEPENDENCIES.keys())
    assert actual == _EXPECTED_MODULES, f"Dependency mismatch: expected {_EXPECTED_MODULES}, got {actual}"

    # Critical dependencies must not be empty
    assert "readability" in _MODULE_DEPENDENCIES
    assert "text" in _MODULE_DEPENDENCIES["readability"]
    assert "headings" in _MODULE_DEPENDENCIES["readability"]


def test_run_step_map_complete():
    """run_step must support all 10 modules."""
    wf = Workflow()
    step_map = {
        "schema": wf._step_schema,
        "semantic": wf._step_semantic,
        "faq": wf._step_faq,
        "readability": wf._step_readability,
        "citability": wf._step_citability,
        "robots": wf._step_robots,
        "llmstxt": wf._step_llmstxt,
        "schema_audit": wf._step_schema_audit,
        "platform": wf._step_platform,
        "eeat": wf._step_eeat,
    }
    actual = set(step_map.keys())
    assert actual == _EXPECTED_MODULES


def test_readability_module_result_format():
    """ReadabilityAnalyzer must return standard ModuleResult format."""
    text = "The quick brown fox jumps over the lazy dog. " * 20
    analyzer = ReadabilityAnalyzer()
    result = analyzer.analyze(text, [])

    assert result["status"] == "success"
    assert isinstance(result["score"], int)
    assert "score_details" in result
    assert "data" in result
    assert "errors" in result
    assert "fallback" in result
    assert "recommended_actions" in result

    data = result["data"]
    assert "flesch_reading_ease" in data
    assert "avg_sentence_length" in data
    assert "word_count" in data


def test_schemas_from_raw_includes_readability():
    """AnalysisResult.from_raw must handle readability module data."""
    raw = {
        "meta": {"url": "https://example.com", "analyzedAt": "2024-01-01T00:00:00Z", "durationMs": 1000},
        "pageData": {"title": "Test", "description": "Desc", "type": "Article"},
        "moduleResults": {
            "readability": {
                "status": "success",
                "score": 75,
                "data": {"flesch_reading_ease": 65.0, "word_count": 500},
                "errors": [],
                "fallback": False,
            },
            "schema": {
                "status": "success",
                "score": 80,
                "data": {"schemas": {}},
                "errors": [],
                "fallback": False,
            },
        },
        "actions": [],
        "moduleStatuses": {"readability": "success", "schema": "success"},
    }

    result = AnalysisResult.from_raw(raw)
    assert "readability" in result.module_results
    assert result.module_results["readability"].score == 75
    assert result.module_results["readability"].data["flesch_reading_ease"] == 65.0


def test_overall_score_calculation():
    """overall_score must average available module scores."""
    raw = {
        "meta": {"url": "https://example.com", "analyzedAt": "", "durationMs": 0},
        "pageData": {"title": "", "description": "", "type": ""},
        "moduleResults": {
            "schema": {"status": "success", "score": 80, "data": {}},
            "readability": {"status": "success", "score": 60, "data": {}},
            "robots": {"status": "success", "score": 100, "data": {}},
        },
        "actions": [],
        "moduleStatuses": {},
    }
    result = AnalysisResult.from_raw(raw)
    assert result.overall_score == 80  # (80 + 60 + 100) / 3


def test_deleted_modules_not_present():
    """Removed modules must not appear in _MODULE_NAMES."""
    deleted = {"multimodal", "authority", "monitor", "brand", "technical"}
    actual = set(Workflow._MODULE_NAMES)
    assert not (deleted & actual), f"Deleted modules still present: {deleted & actual}"
