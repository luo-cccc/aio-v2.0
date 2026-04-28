# Article SEO + GEO Optimizer — Design Spec

> **Scope**: Slim down the 14-module generic SEO AIO Engine into a focused article-column (blog post / news article / 专栏文章) SEO + GEO optimization engine.
> **Version**: 2.0.0 (breaking change from v1.1.0)
> **Date**: 2026-04-28

---

## 1. Goal

**One-sentence positioning:**

> Given a nearly-finished article URL, output an optimization checklist that makes it rank better on both Google and AI search engines (ChatGPT, Perplexity, Gemini, Bing Copilot).

**What it does:**
- Analyzes a single article page across 10 dimensions
- Scores each dimension 0-100
- Generates concrete, prioritized improvement actions
- Outputs structured JSON consumable by downstream agents/CMS/plugins

**What it does NOT do:**
- Full-site technical SEO audit
- Brand/competitor monitoring
- Keyword research (upstream concern)
- Image/video multimodal annotation (spin-off tool)

---

## 2. Architecture

### 2.1 Module Topology (10 analysis modules + 1 infra)

| Module | Action | Role |
|--------|--------|------|
| `page_parser` | Keep, simplify | Phase 1: fetch + article metadata extraction |
| `schema_generator` | **Refactor: Article-only** | Generate Article JSON-LD with article-specific properties |
| `semantic_optimizer` | Keep | Semantic coverage, cite-worthy snippets, topic analysis |
| `faq_generator` | Keep | Auto-generate FAQ structured snippets |
| `citability_scorer` | Keep | 5-dimension citation scoring (GEO core) |
| `robots_checker` | Keep, simplify | AI crawler accessibility for this URL only |
| `llmstxt_checker` | Keep | LLMs.txt compliance validation |
| `schema_auditor` | Keep, simplify | Audit only Article/NewsArticle/BlogPosting JSON-LD |
| `platform_optimizer` | Keep | 5 AI search platform visibility scoring |
| `eeat_scorer` | Keep | E-E-A-T 4-dimension scoring |
| `readability_analyzer` | **Add** | Flesch-Kincaid, sentence length, paragraph length, passive voice |

### 2.2 Removed Modules (5)

| Module | Removal Reason |
|--------|---------------|
| `authority_checker` | External review coverage — product/brand focused, not article |
| `brand_checker` | Brand mention detection — competitor analysis layer |
| `monitor` | GSC site-wide monitoring — independent ops service |
| `multimodal_labeler` | Image/video alt generation — spin-off utility |
| `technical_auditor` | Full-site technical audit — not single-article content |

### 2.3 3-Phase Pipeline

```
Phase 1: Fetch & Parse
  Crawler.fetch(url)  →  SSRF validation  →  aiohttp GET  →  raw HTML
  PageParser.parse()  →  text, headings, content_blocks, json_ld, article topics

Phase 2: Parallel Analysis (10 modules, Semaphore(3) for LLM calls)
  Group A (LLM-driven, limited concurrency):
    - schema_generator      → Article JSON-LD framework
    - semantic_optimizer    → semantic optimization + cite_worthy_snippets
    - faq_generator         → FAQ HTML snippets

  Group B (Rule-driven, unlimited parallelism):
    - citability_scorer     → content block citation scoring
    - robots_checker        → AI crawler status
    - llmstxt_checker       → LLMs.txt validation
    - schema_auditor        → Article Schema audit
    - platform_optimizer    → 5-platform visibility scoring
    - eeat_scorer           → E-E-A-T scoring
    - readability_analyzer  → readability metrics

Phase 3: Aggregate
  Workflow._execute_phase3()  →  Article optimization report JSON
```

### 2.4 Key Architectural Decisions

**Decision 1: SchemaGenerator is Article-only**
- Original: LLM infers Schema.org type from page content (Product/Article/Organization/etc.)
- Refactored: Hard-coded `"Article"` type, no type inference LLM call
- Benefit: Saves 1 LLM call per analysis, generates article-specific properties (author, datePublished, articleSection, wordCount)
- Trade-off: Cannot handle non-article pages; acceptable per scope

**Decision 2: PageParser simplified for articles**
- Original: Generic keyword extraction for FAQ + authority signals
- Refactored: "Article topic/entity extraction" for semantic_optimizer and schema_generator entity linking
- Benefit: More relevant outputs for article context

**Decision 3: ReadabilityAnalyzer is rule-based, no LLM**
- Pure regex/statistical analysis
- Zero token cost, sub-millisecond execution
- Adds unique value not covered by existing modules

---

## 3. Component Design

### 3.1 schema_generator.py — Article-Only

```python
class SchemaGenerator:
    def __init__(self, llm: LLMClient):
        self._llm = llm
        # No longer loads full Schema.org graph; uses Article-specific property list

    async def generate(self, page: ParsedPage) -> dict:
        """Generate Article JSON-LD with article-specific properties."""
        # Hard-coded type = "Article"
        # Enhanced properties: author, datePublished, dateModified, publisher,
        #   articleSection, wordCount (auto-populated from page data)
        # Falls back to LLM if local Article template is insufficient
```

**Changes from v1.1.0:**
- Remove: `_infer_type()`, `_load_full_schema()`, `_parse_schema()`, `SchemaCache` dependency
- Keep: `_build_jsonld()`, `_extract_entities()`, `_score_schema()`
- Modify: `generate()` signature — drops `type_name` parameter
- Add: Article-specific property list and auto-population logic

### 3.2 page_parser.py — Article Topic Extraction

```python
class PageParser:
    async def parse(self, url: str) -> ParsedPage:
        # Fetch via Crawler
        # Extract text, headings, content_blocks, json_ld
        # Extract article topics/entities (replaces generic keyword extraction)
```

**Changes:**
- `_extract_keyword()` prompt changed from "extract 1-3 keywords" to "extract article core topics and 3-5 key entities"
- `_infer_type()` still exists for compatibility but always returns `"Article"` without LLM call

### 3.3 readability_analyzer.py — New Module

```python
class ReadabilityAnalyzer:
    def analyze(self, text: str, headings: List[dict]) -> dict:
        """
        Returns ModuleResult dict with:
        - data.flesch_kincaid_score: float
        - data.flesch_reading_ease: float
        - data.avg_sentence_length: float
        - data.avg_paragraph_length: float
        - data.passive_voice_ratio: float
        - data.long_sentences_count: int (>25 words)
        - data.complex_words_ratio: float
        """
```

**Scoring (100-point scale):**
| Dimension | Weight | Target |
|-----------|--------|--------|
| Flesch Reading Ease | 30 | 60-70 (standard/easy) |
| Sentence length | 25 | avg 15-20 words |
| Paragraph length | 20 | avg 3-5 sentences |
| Passive voice ratio | 15 | <10% |
| Complex word density | 10 | <15% |

### 3.4 robots_checker.py — Simplified

- Keep: 14 AI crawler status detection
- Remove: Sitemap-related actions weight reduction (article optimization doesn't care about site-wide sitemap)

### 3.5 schema_auditor.py — Article-Scoped

- Only audits JSON-LD where `@type` is `Article`, `NewsArticle`, or `BlogPosting`
- Ignores other schema types (Product, Organization, etc.)

### 3.6 Modules Requiring No Changes

- `semantic_optimizer.py` — already article-friendly
- `faq_generator.py` — already article-friendly
- `citability_scorer.py` — already article-friendly
- `llmstxt_checker.py` — URL-level, no changes needed
- `platform_optimizer.py` — already article-friendly
- `eeat_scorer.py` — already article-friendly

---

## 4. Infrastructure Changes

### 4.1 workflow.py

```python
_MODULE_NAMES: tuple = (
    "schema", "semantic", "faq",
    "citability", "robots", "llmstxt",
    "schema_audit", "platform", "eeat", "readability",
)

_MODULE_DEPENDENCIES: Dict[str, List[str]] = {
    "schema": ["title", "description", "url"],  # derived_type no longer needed (always Article)
    "semantic": ["text"],
    "faq": ["keyword"],
    "citability": ["content_blocks"],
    "robots": ["url"],
    "llmstxt": ["url"],
    "schema_audit": ["json_ld_scripts"],  # derived_type removed
    "platform": ["content_blocks", "headings", "_raw_html", "text", "images", "videos"],
    "eeat": ["text", "content_blocks", "headings", "_raw_html"],
    "readability": ["text", "headings"],
}
```

### 4.2 schemas.py

- `AnalysisResult` / `ModuleResult` structure **unchanged** (backward compatible)
- Remove: old-format compatibility branches for removed modules

### 4.3 __init__.py (package entry)

- `__all__` reduced to kept modules
- Remove imports for deleted modules

### 4.4 modules/__init__.py (standalone entry)

- Remove: `check_authority`, `analyze_multimodal`, `check_brand`, `audit_technical`, `track_monitor`
- Keep: all other standalone functions with same signatures

### 4.5 Version Bump

```python
version = "2.0.0"  # Breaking change: module reduction + Article specialization
```

---

## 5. Data Flow

### 5.1 Module Dependency Graph

```
page_parser (Phase 1)
  │
  ├─► schema_generator ──► requires: title, description, url
  ├─► semantic_optimizer ──► requires: text
  ├─► faq_generator ──► requires: keyword
  ├─► citability_scorer ──► requires: content_blocks
  ├─► robots_checker ──► requires: url
  ├─► llmstxt_checker ──► requires: url
  ├─► schema_auditor ──► requires: json_ld_scripts
  ├─► platform_optimizer ──► requires: content_blocks, headings, _raw_html, text, images, videos
  ├─► eeat_scorer ──► requires: text, content_blocks, headings, _raw_html
  └─► readability_analyzer ──► requires: text, headings
```

### 5.2 Concurrency Groups

| Group | Modules | Limiting |
|-------|---------|----------|
| LLM-driven | schema, semantic, faq | Semaphore(3) |
| Rule-driven | citability, robots, llmstxt, schema_audit, platform, eeat, readability | No limit |

### 5.3 Output Structure

```json
{
  "meta": {
    "url": "...",
    "analyzedAt": "...",
    "durationMs": 409,
    "version": "2.0.0",
    "cacheHit": false
  },
  "pageData": {
    "title": "...",
    "description": "...",
    "type": "Article",
    "existingSchemas": ["BlogPosting"]
  },
  "moduleResults": {
    "schema": { "status": "success", "score": 80, "data": {"schemas": {"Article": {...}}, "entities": {...}} },
    "semantic": { "status": "success", "score": 70, "data": {"optimized_text": "...", "cite_worthy_snippets": [...], "semantic_topics": {...}} },
    "faq": { "status": "success", "score": 60, "data": {"faq_html": "..."} },
    "citability": { "status": "success", "score": 65, "data": {"blocks": [...], "page_metrics": {...}} },
    "robots": { "status": "success", "score": 85, "data": {"ai_crawler_status": {...}} },
    "llmstxt": { "status": "success", "score": 40, "data": {...} },
    "schema_audit": { "status": "success", "score": 60, "data": {"schemas_found": [...], "issues": [...]} },
    "platform": { "status": "success", "score": 75, "data": {"platforms": {...}, "universal_actions": [...]} },
    "eeat": { "status": "success", "score": 65, "data": {"dimensions": {...}} },
    "readability": { "status": "success", "score": 72, "data": {"flesch_reading_ease": 65, "avg_sentence_length": 18.5, ...} }
  },
  "geo": {
    "citeWorthySnippets": [...],
    "semanticTopics": {...},
    "entities": {...}
  },
  "actions": [
    {"action": "...", "priority": "high", "targetModule": "...", "params": {}}
  ],
  "moduleStatuses": {...},
  "scores": {"overall": 68},
  "workflow": {"steps": {...}}
}
```

---

## 6. Error Handling

| Scenario | Handling |
|----------|----------|
| Phase 1 fetch fails | All modules marked `skipped`, return error report |
| LLM module timeout/failure | Marked `error`, doesn't block other modules, overall_score calculated from available modules |
| LLM not configured | LLM modules marked `unavailable`, local modules run normally |
| Article text < 100 words | readability marked `skipped`, semantic runs with degraded confidence |
| robots.txt unreachable | robots module marked `error` with network message |
| No JSON-LD found | schema_audit marked `success` with score 0 and "no schema found" action |

---

## 7. Testing Strategy

### 7.1 Unit Tests
- Each module tested independently with mocked Crawler/LLM
- ReadabilityAnalyzer: verify against known Flesch scores

### 7.2 Integration Tests
- 3-5 real article URLs run through full Workflow
- Validate output structure matches spec
- Verify all 10 modules produce non-error results

### 7.3 Regression Tests
- Confirm `analyze()` and `Workflow()` interfaces unchanged
- Confirm standalone module functions in `modules/__init__.py` work
- Verify removed modules no longer appear in exports

### 7.4 Performance Baseline
- Full analysis should complete < 10s for a typical article ( dominated by 3 LLM calls )
- Local-only analysis (without LLM) should complete < 2s

---

## 8. Migration Guide (v1.1.0 → v2.0.0)

### Breaking Changes
1. Removed modules no longer available: `check_authority`, `analyze_multimodal`, `check_brand`, `audit_technical`, `track_monitor`
2. `SchemaGenerator` no longer accepts `type_name` parameter
3. `page.derived_type` is always `"Article"`
4. `version` field changes from `"1.1.0"` to `"2.0.0"`

### Non-Breaking Changes
- `analyze(url)` interface unchanged
- `Workflow` class interface unchanged
- `ModuleResult` structure unchanged
- Standalone module functions in `modules/__init__.py` retain same signatures

### Action Required for Consumers
- Remove calls to deleted standalone functions
- Update any code depending on `derived_type` being dynamic
- No changes needed if only using `analyze()` or kept standalone functions
