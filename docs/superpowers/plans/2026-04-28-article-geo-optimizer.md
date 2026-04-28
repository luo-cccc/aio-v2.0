# Article SEO + GEO Optimizer — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Slim down the 14-module generic SEO AIO Engine into a focused article-column SEO + GEO optimization engine with 10 analysis modules + 1 new readability module.

**Architecture:** Remove 5 non-article modules, refactor SchemaGenerator to Article-only, add ReadabilityAnalyzer, simplify infrastructure layer (workflow, schemas, exports), bump version to 2.0.0.

**Tech Stack:** Python 3.10+, aiohttp, standard library only for new module

---

## File Structure

### Files to Delete
- `scripts/aio_engine/modules/authority_checker.py`
- `scripts/aio_engine/modules/brand_checker.py`
- `scripts/aio_engine/modules/monitor.py`
- `scripts/aio_engine/modules/multimodal_labeler.py`
- `scripts/aio_engine/modules/technical_auditor.py`

### Files to Create
- `scripts/aio_engine/modules/readability_analyzer.py` — Pure rule-driven readability scoring

### Files to Modify
- `scripts/aio_engine/modules/schema_generator.py` — Refactor to Article-only
- `scripts/aio_engine/modules/page_parser.py` — Simplify keyword extraction for articles
- `scripts/aio_engine/workflow.py` — Reduce module list from 14 to 11
- `scripts/aio_engine/schemas.py` — Remove compatibility code for deleted modules
- `scripts/aio_engine/__init__.py` — Reduce exports
- `scripts/aio_engine/modules/__init__.py` — Remove standalone functions for deleted modules

---

## Task 1: Delete Non-Article Modules

**Files:**
- Delete: `scripts/aio_engine/modules/authority_checker.py`
- Delete: `scripts/aio_engine/modules/brand_checker.py`
- Delete: `scripts/aio_engine/modules/monitor.py`
- Delete: `scripts/aio_engine/modules/multimodal_labeler.py`
- Delete: `scripts/aio_engine/modules/technical_auditor.py`

- [ ] **Step 1: Delete the 5 module files**

```bash
rm scripts/aio_engine/modules/authority_checker.py
rm scripts/aio_engine/modules/brand_checker.py
rm scripts/aio_engine/modules/monitor.py
rm scripts/aio_engine/modules/multimodal_labeler.py
rm scripts/aio_engine/modules/technical_auditor.py
```

- [ ] **Step 2: Verify files are gone**

```bash
ls scripts/aio_engine/modules/
```

Expected: The 5 deleted files should NOT appear in the listing. Remaining files should be:
`__init__.py`, `citability_scorer.py`, `eeat_scorer.py`, `faq_generator.py`, `llmstxt_checker.py`, `page_parser.py`, `platform_optimizer.py`, `robots_checker.py`, `schema_auditor.py`, `schema_generator.py`, `semantic_optimizer.py`

---

## Task 2: Add ReadabilityAnalyzer Module

**Files:**
- Create: `scripts/aio_engine/modules/readability_analyzer.py`
- Test: `scripts/aio_engine/modules/test_readability.py`

- [ ] **Step 1: Write the failing test**

Create `scripts/aio_engine/modules/test_readability.py`:

```python
import sys
sys.path.insert(0, "scripts")

import asyncio
from aio_engine.modules.readability_analyzer import ReadabilityAnalyzer


def test_readability_basic():
    text = "The quick brown fox jumps over the lazy dog. " * 20
    analyzer = ReadabilityAnalyzer()
    result = analyzer.analyze(text, [])
    assert result["status"] == "success"
    assert "score" in result
    assert "data" in result
    assert "flesch_reading_ease" in result["data"]
    assert "avg_sentence_length" in result["data"]
    assert "passive_voice_ratio" in result["data"]


def test_readability_empty_text():
    analyzer = ReadabilityAnalyzer()
    result = analyzer.analyze("", [])
    assert result["status"] == "skipped"


def test_readability_short_text():
    analyzer = ReadabilityAnalyzer()
    result = analyzer.analyze("Hello world.", [])
    assert result["status"] == "skipped"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd c:/Users/Msi/Desktop/aio/aio-main
python -m pytest scripts/aio_engine/modules/test_readability.py -v 2>&1 || true
```

Expected: ImportError — `readability_analyzer` module does not exist.

- [ ] **Step 3: Implement ReadabilityAnalyzer**

Create `scripts/aio_engine/modules/readability_analyzer.py`:

```python
"""
Readability Analyzer
====================
Pure rule-driven readability scoring for articles.
No LLM dependency. Evaluates Flesch-Kincaid, sentence length,
paragraph length, passive voice density, and complex word ratio.
"""

import re
from typing import List


class ReadabilityAnalyzer:
    """AI readability scorer: analyzes text readability metrics."""

    def analyze(self, text: str, headings: List[dict]) -> dict:
        """
        Analyze text readability and return ModuleResult format.

        Args:
            text: Article body text
            headings: List of {"level": int, "text": str}

        Returns:
            Standard module result dict with readability metrics
        """
        word_count = len(text.split())
        if word_count < 30:
            return {
                "status": "skipped",
                "score": 0,
                "score_details": {"reason": "Text too short for readability analysis"},
                "fallback": False,
                "errors": [],
                "recommended_actions": [],
                "data": {},
            }

        sentences = self._split_sentences(text)
        words = text.split()

        # Flesch Reading Ease
        flesch_re = self._flesch_reading_ease(text, sentences, words)
        flesch_kg = self._flesch_kincaid_grade(text, sentences, words)
        avg_sent_len = len(words) / len(sentences) if sentences else 0
        avg_para_len = self._avg_paragraph_length(text)
        passive_ratio = self._passive_voice_ratio(text, sentences)
        long_sentences = sum(1 for s in sentences if len(s.split()) > 25)
        complex_ratio = self._complex_word_ratio(words)

        # Scoring
        scores = {
            "flesch": self._score_flesch(flesch_re),
            "sentence_length": self._score_sentence_length(avg_sent_len),
            "paragraph_length": self._score_paragraph_length(avg_para_len),
            "passive_voice": self._score_passive_voice(passive_ratio),
            "complex_words": self._score_complex_words(complex_ratio),
        }
        total_score = sum(scores.values())

        score_details = {
            "base_score": total_score,
            "reason": f"Readability score {total_score}/100: Flesch {flesch_re:.1f}, avg sentence {avg_sent_len:.1f} words",
            **scores,
        }

        actions = self._derive_actions(
            total_score, flesch_re, avg_sent_len, passive_ratio, long_sentences
        )

        return {
            "status": "success",
            "score": total_score,
            "score_details": score_details,
            "fallback": False,
            "errors": [],
            "recommended_actions": actions,
            "data": {
                "flesch_reading_ease": round(flesch_re, 1),
                "flesch_kincaid_grade": round(flesch_kg, 1),
                "avg_sentence_length": round(avg_sent_len, 1),
                "avg_paragraph_length": round(avg_para_len, 1),
                "passive_voice_ratio": round(passive_ratio, 3),
                "long_sentences_count": long_sentences,
                "complex_words_ratio": round(complex_ratio, 3),
                "sentence_count": len(sentences),
                "word_count": word_count,
            },
        }

    @staticmethod
    def _split_sentences(text: str) -> List[str]:
        """Split text into sentences."""
        raw = re.split(r'[.!?]+', text)
        return [s.strip() for s in raw if s.strip()]

    @staticmethod
    def _flesch_reading_ease(text: str, sentences: List[str], words: List[str]) -> float:
        """Calculate Flesch Reading Ease score."""
        if not sentences or not words:
            return 0.0
        total_syllables = sum(ReadabilityAnalyzer._count_syllables(w) for w in words)
        return 206.835 - 1.015 * (len(words) / len(sentences)) - 84.6 * (total_syllables / len(words))

    @staticmethod
    def _flesch_kincaid_grade(text: str, sentences: List[str], words: List[str]) -> float:
        """Calculate Flesch-Kincaid Grade Level."""
        if not sentences or not words:
            return 0.0
        total_syllables = sum(ReadabilityAnalyzer._count_syllables(w) for w in words)
        return 0.39 * (len(words) / len(sentences)) + 11.8 * (total_syllables / len(words)) - 15.59

    @staticmethod
    def _count_syllables(word: str) -> int:
        """Estimate syllable count for a word."""
        word = word.lower().strip(".,!?;:\"'")
        if not word:
            return 0
        # Remove trailing e
        if word.endswith("e"):
            word = word[:-1]
        vowels = "aeiouy"
        count = 0
        prev_was_vowel = False
        for ch in word:
            is_vowel = ch in vowels
            if is_vowel and not prev_was_vowel:
                count += 1
            prev_was_vowel = is_vowel
        if count == 0:
            count = 1
        return count

    @staticmethod
    def _avg_paragraph_length(text: str) -> float:
        """Average sentences per paragraph."""
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        if not paragraphs:
            return 0.0
        total_sentences = sum(len(re.split(r'[.!?]+', p)) for p in paragraphs)
        return total_sentences / len(paragraphs)

    @staticmethod
    def _passive_voice_ratio(text: str, sentences: List[str]) -> float:
        """Estimate passive voice ratio."""
        if not sentences:
            return 0.0
        passive_patterns = [
            r'\b(?:is|are|was|were|been|be|being)\s+\w+ed\b',
            r'\b(?:has|have|had)\s+been\s+\w+ed\b',
        ]
        passive_count = 0
        for sentence in sentences:
            for pattern in passive_patterns:
                if re.search(pattern, sentence, re.IGNORECASE):
                    passive_count += 1
                    break
        return passive_count / len(sentences)

    @staticmethod
    def _complex_word_ratio(words: List[str]) -> float:
        """Ratio of words with 3+ syllables."""
        if not words:
            return 0.0
        complex_count = sum(
            1 for w in words
            if ReadabilityAnalyzer._count_syllables(w) >= 3
        )
        return complex_count / len(words)

    @staticmethod
    def _score_flesch(flesch_re: float) -> int:
        """Score Flesch Reading Ease (target 60-70 = standard)."""
        if 60 <= flesch_re <= 70:
            return 30
        elif 50 <= flesch_re < 60 or 70 < flesch_re <= 80:
            return 22
        elif 40 <= flesch_re < 50 or 80 < flesch_re <= 90:
            return 15
        elif 30 <= flesch_re < 40:
            return 8
        return 4

    @staticmethod
    def _score_sentence_length(avg_len: float) -> int:
        """Score average sentence length (target 15-20 words)."""
        if 15 <= avg_len <= 20:
            return 25
        elif 12 <= avg_len < 15 or 20 < avg_len <= 25:
            return 18
        elif 10 <= avg_len < 12 or 25 < avg_len <= 30:
            return 12
        return 6

    @staticmethod
    def _score_paragraph_length(avg_len: float) -> int:
        """Score average paragraph length (target 3-5 sentences)."""
        if 3 <= avg_len <= 5:
            return 20
        elif 2 <= avg_len < 3 or 5 < avg_len <= 7:
            return 14
        elif 1 <= avg_len < 2:
            return 8
        return 4

    @staticmethod
    def _score_passive_voice(ratio: float) -> int:
        """Score passive voice ratio (target <10%)."""
        if ratio < 0.05:
            return 15
        elif ratio < 0.10:
            return 11
        elif ratio < 0.15:
            return 7
        return 3

    @staticmethod
    def _score_complex_words(ratio: float) -> int:
        """Score complex word density (target <15%)."""
        if ratio < 0.10:
            return 10
        elif ratio < 0.15:
            return 7
        elif ratio < 0.20:
            return 4
        return 2

    @staticmethod
    def _derive_actions(score, flesch_re, avg_sent, passive_ratio, long_count) -> List[dict]:
        actions = []
        if score < 50:
            actions.append({
                "action": "Readability score is low. Consider simplifying vocabulary and shortening sentences.",
                "priority": "high",
                "target_module": "readability_analyzer",
                "params": {"current_score": score},
            })
        if flesch_re < 50:
            actions.append({
                "action": f"Flesch Reading Ease ({flesch_re:.1f}) is difficult. Target 60-70 for standard readability.",
                "priority": "medium",
                "target_module": "readability_analyzer",
                "params": {"flesch_re": flesch_re, "target": "60-70"},
            })
        if avg_sent > 25:
            actions.append({
                "action": f"Average sentence length ({avg_sent:.1f} words) is high. Break into shorter sentences (target 15-20).",
                "priority": "medium",
                "target_module": "readability_analyzer",
                "params": {"avg_sentence_length": avg_sent, "target": "15-20"},
            })
        if long_count > 5:
            actions.append({
                "action": f"Found {long_count} sentences over 25 words. Consider breaking them up.",
                "priority": "medium",
                "target_module": "readability_analyzer",
                "params": {"long_sentences": long_count},
            })
        if passive_ratio > 0.15:
            actions.append({
                "action": f"Passive voice ratio ({passive_ratio:.1%}) is high. Use active voice where possible.",
                "priority": "low",
                "target_module": "readability_analyzer",
                "params": {"passive_ratio": passive_ratio},
            })
        return actions
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd c:/Users/Msi/Desktop/aio/aio-main
python -m pytest scripts/aio_engine/modules/test_readability.py -v
```

Expected: All 3 tests PASS.

---

## Task 3: Refactor SchemaGenerator to Article-Only

**Files:**
- Modify: `scripts/aio_engine/modules/schema_generator.py`
- Test: `scripts/aio_engine/modules/test_schema_article.py`

- [ ] **Step 1: Write test for Article-only generation**

Create `scripts/aio_engine/modules/test_schema_article.py`:

```python
import sys
sys.path.insert(0, "scripts")

from aio_engine.modules.schema_generator import SchemaGenerator
from aio_engine.lib.llm_client import LLMClient


def test_schema_generator_article_only():
    # Mock LLM client
    class MockLLM:
        pass

    gen = SchemaGenerator(MockLLM())
    # Verify internal state: should be Article-only
    assert gen._type_name == "Article"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python -m pytest scripts/aio_engine/modules/test_schema_article.py -v 2>&1 || true
```

Expected: AttributeError — `_type_name` does not exist.

- [ ] **Step 3: Modify SchemaGenerator to be Article-only**

Modify `scripts/aio_engine/modules/schema_generator.py`:

**Changes needed:**
1. Remove `_load_full_schema()` and `_parse_schema()` methods
2. Remove `SchemaCache` dependency
3. Remove `os` import and JSON-LD schema file loading
4. Change `generate()` signature from `generate(self, type_name, page)` to `generate(self, page)`
5. Set `self._type_name = "Article"` in `__init__`
6. Replace `self._classes` and `self._properties` with hardcoded Article property list
7. Update all internal references from `type_name` to `"Article"`

Key code changes in `schema_generator.py`:

```python
# In __init__:
def __init__(self, llm: LLMClient):
    self._llm = llm
    self._type_name = "Article"
    # Hardcoded Article properties (subset of most useful ones)
    self._article_properties = {
        "headline", "description", "image", "author", "datePublished",
        "dateModified", "publisher", "articleSection", "articleBody",
        "wordCount", "keywords", "url", "mainEntityOfPage",
    }

# In generate():
async def generate(self, page) -> dict:
    """Generate Article JSON-LD with article-specific properties."""
    jsonld = self._build_article_jsonld(page)
    score, score_details = self._score_article(page)
    entities = self._extract_article_entities(jsonld, page)
    actions = self._derive_article_actions(jsonld, entities)
    return {
        "status": "success",
        "score": score,
        "schemas": {"Article": jsonld},
        "entities": entities,
        "score_details": score_details,
        "fallback": False,
        "errors": [],
        "recommended_actions": actions,
    }

# New _build_article_jsonld():
def _build_article_jsonld(self, page) -> dict:
    result = {
        "@context": "https://schema.org",
        "@type": "Article",
        "headline": page.title or "",
        "description": page.description or "",
        "url": page.url,
    }
    # Auto-populate from page data where available
    if hasattr(page, 'text') and page.text:
        wc = len(page.text.split())
        result["wordCount"] = wc
        result["articleBody"] = page.text[:500]  # truncated
    return result

# Update _extract_entities to _extract_article_entities:
def _extract_article_entities(self, jsonld: dict, page) -> dict:
    entities = {}
    if jsonld.get("headline"):
        entities["article"] = {"name": jsonld["headline"]}
    author = jsonld.get("author")
    if author:
        name = author.get("name", "") if isinstance(author, dict) else str(author)
        if name:
            entities["author"] = {"name": name}
    return entities
```

**Also remove:** `_generate_llm_fallback()`, `_get_direct_properties()`, `_get_parent_chain()`, `_get_placeholder()`, `_score_schema()`, and all helper functions `_extract_name()`, `_ensure_list()` if they become unused.

Actually, keep `_generate_llm_fallback()` but simplify it to generate Article schema.

- [ ] **Step 4: Run test to verify it passes**

```bash
python -m pytest scripts/aio_engine/modules/test_schema_article.py -v
```

Expected: PASS.

---

## Task 4: Simplify PageParser

**Files:**
- Modify: `scripts/aio_engine/modules/page_parser.py`

- [ ] **Step 1: Modify keyword extraction for articles**

In `page_parser.py`, modify `_extract_keyword()`:

```python
async def _extract_keyword(
    self, title: str, description: str, text: str
) -> Tuple[str, bool, List[str]]:
    """Extract article core topics/entities."""
    context = f"""Title: {title}
Description: {description}
First 500 chars: {text[:500]}"""

    prompt = (
        "Extract 3-5 key topics/entities from this article. "
        "Return as comma-separated list. No explanation.\n\n" + context
    )
    # ... rest of method unchanged
```

- [ ] **Step 2: Simplify type inference**

In `page_parser.py`, modify `_infer_type()` to always return `"Article"`:

```python
async def _infer_type(
    self, title: str, description: str, text: str, keyword: str
) -> Tuple[str, bool, List[str]]:
    """Always returns Article for article-column optimizer."""
    return "Article", False, []
```

Remove `SchemaCache` usage from `_infer_type()` and optionally remove `self._schema_cache` from `__init__` if unused elsewhere.

- [ ] **Step 3: Verify PageParser still works**

```bash
cd c:/Users/Msi/Desktop/aio/aio-main
python -c "
import sys; sys.path.insert(0, 'scripts')
from aio_engine.modules.page_parser import PageParser
from aio_engine.lib.crawler import Crawler
print('PageParser imports OK')
"
```

Expected: "PageParser imports OK"

---

## Task 5: Refactor Workflow

**Files:**
- Modify: `scripts/aio_engine/workflow.py`

- [ ] **Step 1: Update module list and dependencies**

In `workflow.py`:

```python
_MODULE_NAMES: tuple = (
    "schema", "semantic", "faq",
    "citability", "robots", "llmstxt",
    "schema_audit", "platform", "eeat", "readability",
)

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
```

- [ ] **Step 2: Remove deleted module step methods**

Delete from `workflow.py`:
- `_step_authority()` / `_do_authority()`
- `_step_monitor()` / `_do_monitor()`
- `_step_multimodal()` / `_do_multimodal()`
- `_step_brand()` / `_do_brand()`
- `_step_technical()` / `_do_technical()`

- [ ] **Step 3: Add readability step**

Add to `workflow.py`:

```python
async def _step_readability(self, ctx: WorkflowContext) -> StepResult:
    return await self._run_step("readability", ctx, self._do_readability)

async def _do_readability(self, ctx: WorkflowContext) -> dict:
    from .modules.readability_analyzer import ReadabilityAnalyzer
    analyzer = ReadabilityAnalyzer()
    return analyzer.analyze(ctx.page.text, ctx.page.headings)
```

- [ ] **Step 4: Update Phase 3 aggregation**

In `_execute_phase3()`, add readability data mapping:

```python
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
```

Remove deleted modules' data mappings from Phase 3.

- [ ] **Step 5: Update version**

```python
"version": "2.0.0",
```

- [ ] **Step 6: Update run_step map**

```python
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
```

- [ ] **Step 7: Verify workflow imports**

```bash
python -c "
import sys; sys.path.insert(0, 'scripts')
from aio_engine.workflow import Workflow
print('Workflow imports OK')
"
```

Expected: "Workflow imports OK"

---

## Task 6: Update Package Exports

**Files:**
- Modify: `scripts/aio_engine/__init__.py`
- Modify: `scripts/aio_engine/modules/__init__.py`

- [ ] **Step 1: Update __init__.py**

In `scripts/aio_engine/__init__.py`:

Remove imports for deleted modules:
- `MultimodalLabeler`
- `AuthorityChecker`
- `MonitorTracker` (and try/except block)

Remove from `__all__`:
- `"MultimodalLabeler"`
- `"AuthorityChecker"`
- `"MonitorTracker"`

Add to `__all__`:
- `"ReadabilityAnalyzer"` (after adding import)

Add import:
```python
from .modules.readability_analyzer import ReadabilityAnalyzer
```

- [ ] **Step 2: Update modules/__init__.py**

In `scripts/aio_engine/modules/__init__.py`:

Remove:
- `from .authority_checker import AuthorityChecker`
- `from .multimodal_labeler import MultimodalLabeler`
- `from .brand_checker import BrandChecker`
- `from .technical_auditor import TechnicalAuditor`

Remove standalone functions:
- `check_authority()`
- `analyze_multimodal()`
- `check_brand()`
- `audit_technical()`
- `track_monitor()`

Add:
- `from .readability_analyzer import ReadabilityAnalyzer`
- `score_readability()` standalone function

```python
async def score_readability(
    url: str,
    session: Optional[aiohttp.ClientSession] = None,
) -> dict:
    """Analyze article readability."""
    ctx = await _fetch_and_parse(url, session=session)
    page = ctx["page"]
    analyzer = ReadabilityAnalyzer()
    return analyzer.analyze(page.text, page.headings)
```

Update `__all__` accordingly.

- [ ] **Step 3: Verify imports**

```bash
python -c "
import sys; sys.path.insert(0, 'scripts')
from aio_engine import analyze, Workflow, ReadabilityAnalyzer
from aio_engine.modules import generate_schema, score_readability
print('All imports OK')
"
```

Expected: "All imports OK"

---

## Task 7: Update schemas.py

**Files:**
- Modify: `scripts/aio_engine/schemas.py`

- [ ] **Step 1: Remove old-format compatibility for deleted modules**

In `from_raw()` method, remove the old-format branches for:
- `authority`
- `monitor`
- `brand`
- `multimodal`
- `technical`

Keep branches for kept modules.

- [ ] **Step 2: Add readability to old-format compatibility**

```python
elif name == "readability":
    data = {
        "flesch_reading_ease": content.get("fleschReadingEase", 0),
        "avg_sentence_length": content.get("avgSentenceLength", 0),
    }
```

- [ ] **Step 3: Verify schemas import**

```bash
python -c "
import sys; sys.path.insert(0, 'scripts')
from aio_engine.schemas import AnalysisResult, ModuleResult
print('schemas OK')
"
```

Expected: "schemas OK"

---

## Task 8: Integration Test

**Files:**
- Create: `scripts/aio_engine/test_integration.py`

- [ ] **Step 1: Write integration test**

```python
"""Integration test: verify article optimizer runs with all 10 modules."""
import sys
sys.path.insert(0, "scripts")

import asyncio
from aio_engine import Workflow


async def test_full_workflow():
    """Test with a real article URL."""
    wf = Workflow()
    # Use a well-known article URL for testing
    url = "https://example.com"  # Replace with real article URL for actual test
    try:
        result = await wf.run(url)
        assert "meta" in result
        assert "moduleResults" in result
        assert result["meta"]["version"] == "2.0.0"

        # Verify all 10 expected modules are present
        expected_modules = {
            "schema", "semantic", "faq", "citability",
            "robots", "llmstxt", "schema_audit",
            "platform", "eeat", "readability",
        }
        actual_modules = set(result["moduleResults"].keys())
        assert expected_modules == actual_modules, f"Missing: {expected_modules - actual_modules}"

        # Verify no deleted modules leaked in
        deleted_modules = {"authority", "multimodal", "brand", "technical", "monitor"}
        assert not (deleted_modules & actual_modules), "Deleted modules still present"

        # Verify readability module works
        readability = result["moduleResults"]["readability"]
        assert readability["status"] in ("success", "skipped")
        if readability["status"] == "success":
            assert "flesch_reading_ease" in readability["data"]

        print("Integration test PASSED")
        print(f"Overall score: {result['scores']['overall']}")
        print(f"Modules: {list(actual_modules)}")
    finally:
        await wf.close()


if __name__ == "__main__":
    asyncio.run(test_full_workflow())
```

- [ ] **Step 2: Run integration test**

```bash
cd c:/Users/Msi/Desktop/aio/aio-main
python scripts/aio_engine/test_integration.py
```

Note: This test requires a valid LLM configuration to pass fully. Without LLM config, LLM-dependent modules will return `unavailable` status, which is acceptable.

---

## Self-Review Checklist

### Spec Coverage
- [ ] Delete 5 non-article modules — Task 1
- [ ] Add ReadabilityAnalyzer — Task 2
- [ ] Refactor SchemaGenerator to Article-only — Task 3
- [ ] Simplify PageParser — Task 4
- [ ] Refactor Workflow (module list, dependencies, steps, aggregation) — Task 5
- [ ] Update package exports — Task 6
- [ ] Update schemas.py — Task 7
- [ ] Integration test — Task 8

### Placeholder Scan
- [ ] No TBD/TODO
- [ ] No "implement later"
- [ ] No "add appropriate error handling" without specifics
- [ ] No "similar to Task N" references

### Type Consistency
- [ ] `ReadabilityAnalyzer.analyze()` returns ModuleResult-compatible dict
- [ ] `SchemaGenerator.generate()` new signature: `generate(self, page)`
- [ ] Workflow `_MODULE_NAMES` has 10 entries
- [ ] All module names consistent across workflow, schemas, exports
