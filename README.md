# Article GEO Optimizer v2.0.0

文章 SEO + GEO 优化引擎。专为博客文章、新闻稿、专栏内容设计，通过 3 阶段流水线（Parse -> Parallel Analysis -> Aggregate）分析文章页面，输出完整的搜索引擎 + AI 引擎优化数据集。

> v2.0.0 是**破坏性更新**：从通用 SEO 引擎瘦身为文章专栏专用。移除了商品页、产品文档等非文章类型的支持，新增可读性分析模块，聚焦文章的内容质量、AI 引用潜力和搜索排名优化。

## 功能

| 模块 | 功能 | 依赖 LLM |
|------|------|---------|
| Schema 生成 | 生成 Article JSON-LD 代码框架 | 否 |
| 语义优化 | 诊断文案问题，生成 GEO 可引用片段和主题覆盖分析 | 是 |
| FAQ 生成 | 围绕文章关键词自动生成高频问答 | 是 |
| 可读性分析 | Flesch-Kincaid、句子/段落长度、被动语态、复杂词密度 | 否 |
| 可引用性评分 | 5 维度评分内容块的 AI 引用质量 | 否 |
| AI 爬虫检测 | 检测 robots.txt 对 14 个 AI 爬虫的允许/封禁状态 | 否 |
| LLMs.txt 验证 | 检测 llms.txt / llms-full.txt 存在性和格式合规性 | 否 |
| Schema 审计 | 审计现有 JSON-LD，检测缺失属性和类型错误 | 否 |
| 平台优化评分 | 针对 5 个 AI 搜索平台评分（Google AIO、ChatGPT、Perplexity、Gemini、Bing） | 否 |
| E-E-A-T 评分 | 4 维度内容质量评分（经验、专业、权威、可信） | 否 |

## 安装

```bash
pip install -r requirements.txt
```

## 环境配置

### 方式一：config.json（推荐）

编辑 `scripts/aio_engine/config.json`：

```json
{
  "llm": {
    "provider": "anthropic",
    "api_key": "sk-...",
    "model": "claude-sonnet-4-20250514",
    "max_tokens": 300,
    "base_url": ""
  },
  "crawler": {
    "timeout": 30
  },
  "cache": {
    "ttl_seconds": 300
  }
}
```

### 方式二：环境变量

```bash
export ANTHROPIC_API_KEY="sk-..."
export LLM_PROVIDER="anthropic"
```

### 优先级

**config.json > 环境变量 > 代码默认值**

## 用法

### Python API

#### 简单模式

```python
import sys
sys.path.insert(0, "scripts")

import asyncio
from aio_engine import analyze

result = asyncio.run(analyze("https://example.com/article"))

print(result["scores"]["overall"])           # 综合评分 0-100
print(result["actions"])                     # 优先级排序的改进行动
print(result["moduleResults"]["schema"]["data"]["schemas"])      # 生成的 JSON-LD
print(result["moduleResults"]["readability"]["data"]["flesch_reading_ease"])  # 可读性评分
```

#### 按需单模块调用

```python
import sys
sys.path.insert(0, "scripts")

import asyncio
from aio_engine.modules import (
    generate_schema, optimize_semantic, generate_faq,
    score_readability, score_citability, check_robots,
    check_llmstxt, audit_schema, score_platform, score_eeat
)

# 只检查 robots.txt（无需 LLM，极快）
robots = asyncio.run(check_robots("https://example.com"))
print(robots["data"]["ai_crawler_status"])

# 只分析可读性（无需 LLM）
readability = asyncio.run(score_readability("https://example.com"))
print(readability["data"]["flesch_reading_ease"])

# 只生成 FAQ（需 LLM）
faq = asyncio.run(generate_faq("https://example.com"))
print(faq["data"]["faq_html"])
```

所有 10 个模块均支持独立调用。独立入口支持共享 aiohttp session：

```python
import aiohttp
from aio_engine.modules import check_robots, score_readability

async with aiohttp.ClientSession() as session:
    robots = await check_robots("https://example.com", session=session)
    readability = await score_readability("https://example.com", session=session)
```

#### 工作流模式

```python
import sys
sys.path.insert(0, "scripts")

import asyncio
from aio_engine import Workflow, Cache

# 带缓存模式
wf = Workflow(cache=Cache(ttl_seconds=300))
result = asyncio.run(wf.run("https://example.com/article"))

# 查看各步骤执行耗时
for name, info in result["workflow"]["steps"].items():
    print(f"{name}: {info['durationMs']}ms ({info['status']})")

# 单独执行某个步骤（调试）
step = asyncio.run(wf.run_step("https://example.com/article", "readability"))
```

### CLI

```bash
# 基本分析
python -m scripts.aio_engine --url https://example.com/article

# 文本格式输出
python -m scripts.aio_engine --url https://example.com/article --format text

# 保存到文件
python -m scripts.aio_engine --url https://example.com/article --output report.json

# 工作流模式（含步骤追踪）
python -m scripts.aio_engine --url https://example.com/article --workflow
```

## 返回数据结构

```json
{
  "meta": {
    "url": "https://example.com/article",
    "analyzedAt": "2024-01-01T00:00:00Z",
    "durationMs": 409,
    "version": "2.0.0",
    "cacheHit": false
  },
  "pageData": {
    "title": "如何优化文章 SEO",
    "description": "...",
    "type": "Article",
    "existingSchemas": ["Article"]
  },
  "moduleResults": {
    "schema": {
      "status": "success",
      "score": 80,
      "data": {
        "schemas": {"Article": {"@context": "https://schema.org", "@type": "Article", ...}},
        "entities": {"article": {"name": "如何优化文章 SEO"}}
      }
    },
    "semantic": {
      "status": "success",
      "score": 70,
      "data": {
        "optimized_text": "...",
        "cite_worthy_snippets": ["AI 引用片段示例..."],
        "semantic_topics": {"expected": [...], "covered": [...], "missing": [...]}
      }
    },
    "faq": {
      "status": "success",
      "score": 60,
      "data": {"faq_html": "<dl>...</dl>"}
    },
    "readability": {
      "status": "success",
      "score": 75,
      "data": {
        "flesch_reading_ease": 65.0,
        "flesch_kincaid_grade": 8.5,
        "avg_sentence_length": 18.2,
        "avg_paragraph_length": 4.5,
        "passive_voice_ratio": 0.08,
        "long_sentences_count": 3,
        "complex_words_ratio": 0.12,
        "sentence_count": 45,
        "word_count": 820
      }
    },
    "citability": {
      "status": "success",
      "score": 65,
      "data": {"blocks": [...], "page_metrics": {...}}
    },
    "robots": {
      "status": "success",
      "score": 85,
      "data": {"ai_crawler_status": {...}, "sitemaps": [...]}
    },
    "llmstxt": {
      "status": "success",
      "score": 40,
      "data": {"exists": true, "format_valid": true, "issues": [], "suggestions": [...]}
    },
    "schema_audit": {
      "status": "success",
      "score": 60,
      "data": {"schemas_found": [...], "issues": [...], "suggestions": [...]}
    },
    "platform": {
      "status": "success",
      "score": 75,
      "data": {"platforms": {...}, "universal_actions": [...]}
    },
    "eeat": {
      "status": "success",
      "score": 65,
      "data": {"dimensions": {...}, "content_quality": {...}}
    }
  },
  "actions": [
    {"action": "...", "priority": "high", "targetModule": "schema_generator", "params": {}}
  ],
  "moduleStatuses": {
    "schema": "success",
    "semantic": "success",
    "faq": "success",
    "readability": "success",
    "citability": "success",
    "robots": "success",
    "llmstxt": "success",
    "schema_audit": "success",
    "platform": "success",
    "eeat": "success"
  },
  "scores": {"overall": 75},
  "workflow": {
    "steps": {
      "fetch": {"status": "success", "durationMs": 200},
      "schema": {"status": "success", "durationMs": 150}
    }
  }
}
```

## 项目结构

```
aio-v2.0/
  README.md             # 本文件
  requirements.txt      # Python 依赖
  .gitignore            # Git 忽略规则
  docs/
    superpowers/
      plans/            # 实现计划
      specs/            # 设计文档
  references/
    ENVIRONMENT.md      # 环境变量参考
    PROVIDERS.md        # LLM 提供商能力参考
    output_schema.json  # 标准输出 JSON Schema
  scripts/
    aio_engine/         # 主引擎包
      __init__.py       # 统一入口：analyze() + Workflow + schemas
      __main__.py       # CLI 入口
      workflow.py       # 工作流编排器（3 阶段 + 缓存 + 依赖检查）
      schemas.py        # 输出模型定义（AnalysisResult 等）
      config.json       # 固定配置文件
      test_integration.py   # 集成测试
      lib/              # 基础能力库
        config.py       # 配置加载器
        llm_client.py   # 统一 LLM 客户端
        crawler.py      # 异步页面抓取器
        cache.py        # 内存缓存层
        html_utils.py   # HTML 特征提取
        json_utils.py   # JSON 容错解析
        session_utils.py # 共享 aiohttp Session
      modules/          # 功能模块集（10 个）
        __init__.py         # 独立异步入口
        page_parser.py      # 页面解析（Article-only）
        schema_generator.py # Article JSON-LD 生成
        semantic_optimizer.py
        faq_generator.py
        readability_analyzer.py  # 可读性评分（NEW v2.0.0）
        citability_scorer.py
        robots_checker.py
        llmstxt_checker.py
        schema_auditor.py
        platform_optimizer.py
        eeat_scorer.py
        test_readability.py    # 单元测试
```

## 架构

```
阶段1: 抓取 & 解析
  Crawler.fetch(url) -> 原始 HTML
  PageParser.parse() -> 关键词（Article-only）、页面元数据

阶段2: 并行深度分析（10 模块）
  SchemaGenerator.generate()      -> Article JSON-LD 框架
  SemanticOptimizer.optimize()    -> 语义优化文案
  FAQGenerator.generate()         -> FAQ HTML
  ReadabilityAnalyzer.analyze()   -> 可读性指标（NEW）
  CitabilityScorer.analyze()      -> 内容块可引用性评分
  RobotsChecker.check()           -> AI 爬虫封禁状态
  LLMsTxtChecker.check()          -> LLMs.txt 格式验证
  SchemaAuditor.audit()           -> Schema 审计
  PlatformOptimizer.analyze()     -> 平台优化评分
  EEATScorer.analyze()            -> E-E-A-T 评分

阶段3: 聚合 & 输出
  Workflow._execute_phase3() -> 标准化数据集
```

## 底座化特性

- **scoreDetails**: 每个模块返回评分明细（如 `base_score`、`reason`）
- **fallback 标记**: 降级策略时显式标注
- **errors[]**: 错误信息数组
- **targetModule + params**: 每个 action 包含目标模块和参数
- **模块依赖声明**: Phase 2 执行前自动检查输入依赖
- **SSRF 防护**: URL 验证阻断内网/非 HTTP(S) 请求
- **Prompt 注入防护**: 用户内容 sanitization
- **共享 aiohttp Session**: Workflow 内统一创建和注入

## GEO 增强（生成式引擎优化）

- **实体链接** (`schema.data.entities`): 提取文章核心实体
- **可引用片段** (`semantic.data.cite_worthy_snippets`): 高信息密度句子
- **语义主题覆盖** (`semantic.data.semantic_topics`): expected/covered/missing 分析
- **内容块可引用性** (`citability.data.blocks`): 按 heading 分段评分
- **AI 爬虫可达性** (`robots.data.ai_crawler_status`): 14 个 AI 爬虫检测
- **LLMs.txt 合规性** (`llmstxt.data`): 格式、章节、链接完整性

## v2.0.0 变更日志

### 新增
- **ReadabilityAnalyzer**: 纯规则驱动的可读性分析，Flesch-Kincaid、句子/段落长度、被动语态、复杂词密度

### 移除（非文章类型模块）
- ~~MultimodalLabeler~~（图片 alt/视频 Schema）
- ~~AuthorityChecker~~（平台权威信号）
- ~~BrandChecker~~（品牌提及检测）
- ~~TechnicalAuditor~~（技术 SEO 审计）
- ~~MonitorTracker~~（GSC 监控）

### 变更
- SchemaGenerator: 移除类型推断，固定生成 Article Schema
- PageParser: 固定推断类型为 Article
- Workflow: 模块从 14 个精简为 10 个
- 版本号: 1.1.0 -> 2.0.0

## 测试

```bash
# 运行全部测试
python -m pytest scripts/aio_engine/test_integration.py scripts/aio_engine/modules/test_readability.py -v
```

## 限流

LLM 调用通过 `asyncio.Semaphore(3)` 限制为 3 并发。

## 许可证

MIT
