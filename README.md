# SEO AIO Engine

统一异步 SEO 分析引擎。通过 3 阶段流水线（Parse -> Parallel Analysis -> Aggregate）分析任意网页 URL，输出完整的 SEO 优化数据集。

## 功能

| 模块 | 功能 |
|------|------|
| Schema.org 结构化数据 | 推断页面类型，生成 JSON-LD 代码框架，提取核心实体链接 |
| 语义内容优化 | 诊断参数堆砌文案，改写为场景体验型描述，生成可引用片段和主题覆盖分析 |
| FAQ 生成 | 围绕关键词自动生成高频问答内容 |
| 多模态标注 | 检测图片 alt 缺失/无意义，生成 VideoObject Schema |
| 权威信号检查 | 分析中文/英文平台评测覆盖，自动语言检测（知乎、B站、Amazon、YouTube 等） |
| GSC 监控 | 可选，追踪搜索点击、展示、CTR、排名趋势 |
| 可引用性评分 | 5 维度评分内容块的可被 AI 引用质量（答案块质量、自包含性、结构可读性、统计密度、独特性） |
| AI 爬虫检测 | 检测 robots.txt 对 14 个 AI 爬虫（GPTBot、ClaudeBot 等）的允许/封禁状态 |
| LLMs.txt 验证 | 检测 llms.txt / llms-full.txt 存在性、格式合规性、章节和链接完整性 |
| 品牌提及检测 | 检测品牌在 Wikipedia/Wikidata 等知识库的 presence |
| Schema 审计 | 审计页面现有 JSON-LD，检测缺失属性、类型错误、sameAs 缺失 |
| 平台优化评分 | 针对 5 个 AI 搜索平台（Google AIO、ChatGPT、Perplexity、Gemini、Bing Copilot）评分 |
| 技术 SEO 审计 | 8 维度审计（可爬性、可索引性、安全、URL、移动、CWV、SSR、速度） |
| E-E-A-T 评分 | 4 维度内容质量评分（Experience, Expertise, Authoritativeness, Trustworthiness） |

## 安装

```bash
pip install -r requirements.txt
```

可选 GSC 监控依赖：

```bash
pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib
```

## 环境配置

### 方式一：config.json（推荐，固定配置）

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

### 方式二：环境变量（CI/CD 或临时覆盖）

```bash
export ANTHROPIC_API_KEY="sk-..."
export LLM_PROVIDER="anthropic"
export LLM_MODEL=""
```

### 优先级

**config.json > 环境变量 > 代码默认值**

config.json 会覆盖环境变量中的同名配置，适合固定生产环境配置。环境变量作为兜底或开发调试使用。

## 用法

### Python API

#### 简单模式

适合大多数场景，一行代码完成分析：

```python
import sys
sys.path.insert(0, "scripts")

import asyncio
from aio_engine import analyze

result = asyncio.run(analyze("https://example.com/product"))

print(result["scores"]["overall"])           # 综合评分 0-100
print(result["actions"])                     # 优先级排序的改进行动
print(result["moduleResults"]["schema"]["data"]["schemas"])  # 生成的 JSON-LD
print(result["moduleResults"]["faq"]["data"]["faq_html"])   # FAQ HTML 片段

# 结构化访问
from aio_engine import AnalysisResult
ar = AnalysisResult.from_raw(result)
print(ar.module_results["schema"].score_details.get("reason"))
```

#### 按需单模块调用

适合只需要某个特定分析、节省 token 和时间的场景：

```python
import sys
sys.path.insert(0, "scripts")

import asyncio
from aio_engine.modules import check_robots, score_citability, generate_faq

# 只检查 robots.txt（无需 LLM，极快）
robots = asyncio.run(check_robots("https://example.com"))
print(robots["data"]["ai_crawler_status"])

# 只评分内容可引用性
score = asyncio.run(score_citability("https://example.com"))
print(score["data"]["page_metrics"])

# 只生成 FAQ（需 LLM）
faq = asyncio.run(generate_faq("https://example.com"))
print(faq["data"]["faq_html"])
```

所有 14 个模块均支持独立调用：`generate_schema`, `optimize_semantic`, `generate_faq`, `analyze_multimodal`, `check_authority`, `score_citability`, `check_robots`, `check_llmstxt`, `check_brand`, `audit_schema`, `score_platform`, `audit_technical`, `score_eeat`, `track_monitor`。

独立入口支持共享 aiohttp session（复用连接池）：

```python
import aiohttp
from aio_engine.modules import check_robots, score_citability

async with aiohttp.ClientSession() as session:
    robots = await check_robots("https://example.com", session=session)
    score = await score_citability("https://example.com", session=session)
```

新增模块示例：

```python
# 平台优化评分（5 个 AI 搜索平台）
platform = asyncio.run(score_platform("https://example.com"))
print(platform["data"]["platforms"]["google_aio"]["score"])

# 技术 SEO 审计
tech = asyncio.run(audit_technical("https://example.com"))
print(tech["data"]["categories"]["crawlability"])

# E-E-A-T 评分
eeat = asyncio.run(score_eeat("https://example.com"))
print(eeat["data"]["dimensions"]["trustworthiness"])

# Schema 审计
audit = asyncio.run(audit_schema("https://example.com"))
print(audit["data"]["issues"])
```

#### 工作流模式

适合需要步骤追踪、调试、自定义钩子的场景：

```python
import sys
sys.path.insert(0, "scripts")

import asyncio
from aio_engine import Workflow, Cache

# 带缓存模式
wf = Workflow(cache=Cache(ttl_seconds=300))
result = asyncio.run(wf.run("https://example.com/product"))

# 查看各步骤执行耗时
for name, info in result["workflow"]["steps"].items():
    print(f"{name}: {info['durationMs']}ms ({info['status']})")

# 单独执行某个步骤（调试）
step = asyncio.run(wf.run_step("https://example.com/product", "multimodal"))
```

返回数据结构：

```json
{
  "meta": { "url": "...", "analyzedAt": "...", "durationMs": 409, "version": "1.1.0", "cacheHit": false },
  "pageData": { "title": "...", "type": "Product", "existingSchemas": [] },
  "moduleResults": {
    "schema": {
      "status": "success", "score": 80, "scoreDetails": {...}, "fallback": false, "errors": [],
      "data": {
        "schemas": {"Product": {...}},
        "entities": {"brand": {"name": "Apple"}, "product": {"name": "..."}}
      }
    },
    "semantic": {
      "status": "success", "score": 70, "scoreDetails": {...}, "fallback": false, "errors": [],
      "data": {
        "optimized_text": "...",
        "cite_worthy_snippets": ["AirPods Pro 2 的自适应降噪可将地铁轰鸣声减弱至接近翻书声。"],
        "semantic_topics": {"expected": [...], "covered": [...], "missing": [...]}
      }
    },
    "faq": { "status": "success", "score": 60, "scoreDetails": {...}, "fallback": false, "errors": [], "data": {...} },
    "multimodal": { "status": "success", "score": 100, "scoreDetails": {...}, "fallback": false, "errors": [], "data": {...} },
    "authority": { "status": "success", "score": 55, "scoreDetails": {...}, "fallback": false, "errors": [], "data": {...} },
    "monitor": { "status": "unavailable", "score": 0, "scoreDetails": null, "fallback": false, "errors": [], "data": {...} },
    "citability": { "status": "success", "score": 65, "scoreDetails": {...}, "fallback": false, "errors": [], "data": { "blocks": [...], "page_metrics": {...} } },
    "robots": { "status": "success", "score": 85, "scoreDetails": {...}, "fallback": false, "errors": [], "data": { "ai_crawler_status": {...}, "sitemaps": [...] } },
    "llmstxt": { "status": "success", "score": 40, "scoreDetails": {...}, "fallback": false, "errors": [], "data": { "exists": true, "format_valid": true, "issues": [], "suggestions": [...] } },
    "brand": { "status": "success", "score": 70, "scoreDetails": {...}, "fallback": false, "errors": [], "data": { "platforms": {"wikipedia": {"exists": true}, "wikidata": {"exists": false}}} },
    "schema_audit": { "status": "success", "score": 60, "scoreDetails": {...}, "fallback": false, "errors": [], "data": { "schemas_found": [...], "issues": [...], "suggestions": [...] } },
    "platform": { "status": "success", "score": 75, "scoreDetails": {...}, "fallback": false, "errors": [], "data": { "platforms": {...}, "universal_actions": [...] } },
    "technical": { "status": "success", "score": 80, "scoreDetails": {...}, "fallback": false, "errors": [], "data": { "categories": {...}, "critical_issues": [...] } },
    "eeat": { "status": "success", "score": 65, "scoreDetails": {...}, "fallback": false, "errors": [], "data": { "dimensions": {...}, "content_quality": {...} } }
  },
  "actions": [ { "action": "...", "priority": "high", "targetModule": "schema_generator", "params": {} } ],
  "moduleStatuses": { "schema": "success", "semantic": "success", ... },
  "scores": { "overall": 75 },
  "workflow": { "steps": { "schema": { "status": "success", "durationMs": 200 } } }
}
```

### CLI

```bash
# 基本分析
python -m scripts.aio_engine --url https://example.com/product

# 文本格式输出
python -m scripts.aio_engine --url https://example.com/product --format text

# 保存到文件
python -m scripts.aio_engine --url https://example.com/product --output report.json
```

## 项目结构

```
seo-aio-engine/
  SKILL.md              # Qoder Skill 定义
  README.md             # 本文件
  requirements.txt      # Python 依赖
  assets/               # 静态资源
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
      config.json       # 固定配置文件（LLM / Crawler / Cache）
      lib/              # 基础能力库
        __init__.py
        config.py       # 配置加载器（优先级：config.json > 环境变量 > 默认值）
        llm_client.py   # 统一 LLM 客户端（9 提供商）+ Prompt 注入防护
        crawler.py      # 异步页面抓取器 + SSRF 防护 + 内容块提取
        schema_cache.py # Schema.org 类型缓存
        cache.py        # 可选内存缓存层（TTL）
        html_utils.py   # HTML 特征提取（作者/日期/表格/列表等）
        json_utils.py   # JSON 容错解析（LLM 响应提取）
        session_utils.py # 共享 aiohttp Session 工具
      modules/          # 功能模块集
        __init__.py
        page_parser.py      # 页面解析 + 关键词/类型推断
        schema_generator.py # JSON-LD 生成
        semantic_optimizer.py
        faq_generator.py
        multimodal_labeler.py
        authority_checker.py
        monitor.py          # 可选 GSC 集成
        citability_scorer.py    # 可引用性评分
        robots_checker.py       # AI 爬虫检测
        llmstxt_checker.py      # LLMs.txt 验证
        brand_checker.py        # 品牌提及检测
        schema_auditor.py       # Schema 审计
        platform_optimizer.py   # 平台优化评分
        technical_auditor.py    # 技术 SEO 审计
        eeat_scorer.py          # E-E-A-T 评分
```

## 架构

```
阶段1: 抓取 & 解析
  Crawler.fetch(url) -> 原始 HTML
  PageParser.parse() -> 关键词、Schema 类型、页面元数据

阶段2: 并行深度分析（14 模块）
  SchemaGenerator.generate()      -> JSON-LD 框架
  SemanticOptimizer.optimize()    -> 语义优化文案
  FAQGenerator.generate()         -> FAQ HTML
  MultimodalLabeler.analyze()     -> 图片 alt / 视频 Schema
  AuthorityChecker.check()        -> 权威信号报告
  MonitorTracker.track()          -> GSC 数据（可选）
  CitabilityScorer.analyze()      -> 内容块可引用性评分
  RobotsChecker.check()           -> AI 爬虫封禁状态
  LLMsTxtChecker.check()          -> LLMs.txt 格式验证
  BrandChecker.check()            -> 品牌提及检测
  SchemaAuditor.audit()           -> Schema 审计
  PlatformOptimizer.analyze()     -> 平台优化评分
  TechnicalAuditor.audit()        -> 技术 SEO 审计
  EEATScorer.analyze()            -> E-E-A-T 评分

阶段3: 聚合 & 输出
  Workflow._execute_phase3() -> 标准化数据集
```

## 底座化特性

- **scoreDetails**: 每个模块返回评分明细（如 `base_score`、`coverage_rate`、`reason`）
- **fallback 标记**: 当模块使用降级策略（如 LLM 失败转本地）时显式标注
- **errors[]**: 错误信息数组，便于下游消费
- **targetModule + params**: 每个 action 包含目标模块和参数，支持自动化执行
- **cacheHit**: 缓存命中标记，meta 中显式标注
- **模块依赖声明**: Phase 2 执行前自动检查输入依赖，缺失时标记 `skipped`
- **SSRF 防护**: URL 验证阻断内网/非 HTTP(S) 请求
- **Prompt 注入防护**: 用户内容 sanitization，中和系统消息分隔符等注入模式
- **共享 aiohttp Session**: Workflow 内统一创建和注入，连接池复用
- **LLM 响应结构校验**: 提取文本前校验 `content`/`choices` 数组非空
- **图片大小限制**: 多模态下载限制 10MB，防止内存耗尽
- **边界安全**: 空列表/None/空字符串统一处理，除零保护，越界保护
- **独立入口共享 session**: `modules/__init__.py` 各函数支持 `session` 参数，复用 aiohttp 连接池

## GEO 增强（生成式引擎优化）

引擎在现有 SEO 分析基础上，增加了面向生成式 AI 的引用优化能力：

- **实体链接** (`schema.data.entities`): 从 JSON-LD 提取 brand/product/author 等核心实体，提示补充 sameAs/Wikidata 链接
- **可引用片段** (`semantic.data.cite_worthy_snippets`): LLM 生成 3-5 句信息密度高的单句，方便 AI 引擎直接摘取
- **语义主题覆盖** (`semantic.data.semantic_topics`): 分析 expected/covered/missing 主题，自动为缺失主题生成补全 action
- **内容块可引用性** (`citability.data.blocks`): 按 heading 分段评分，5 维度量化每段内容被 AI 引用的潜力
- **AI 爬虫可达性** (`robots.data.ai_crawler_status`): 检测 14 个主流 AI 爬虫的 robots.txt 状态，量化站点对 AI 引擎的开放度
- **LLMs.txt 合规性** (`llmstxt.data`): 验证 llms.txt 格式、章节、链接完整性，确保 AI 引擎能正确理解站点内容策略
- **自动派生 GEO actions**: Phase 3 聚合时扫描 entities、semantic_topics、citability、robots、llmstxt，自动追加 sameAs 补充、主题段落补充、内容块优化、爬虫封禁修复等 actions

## 限流

LLM 调用通过 `asyncio.Semaphore(3)` 限制为 3 并发，防止 API 限流。

## 许可证

MIT
