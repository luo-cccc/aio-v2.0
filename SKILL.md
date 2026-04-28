---
name: seo-aio-engine
description: |
  SEO AIO Engine — 统一异步 SEO 分析引擎。面向 AI Agent 提供 14 个独立分析工具，
  支持全量分析（analyze）和按需单模块调用。所有工具返回统一 ModuleResult 格式，
  可直接被下游 Agent 消费。
triggers:
  - 分析网页 SEO
  - 生成 Schema.org JSON-LD
  - 优化商品描述文案
  - 生成 FAQ 内容
  - 检测图片 alt 缺失
  - 检查外部评测覆盖
  - 评分内容可引用性
  - 检测 AI 爬虫封禁
  - 验证 llms.txt
  - 技术 SEO 审计
  - E-E-A-T 评分
  - 品牌提及检测
license: MIT
compatibility: Python 3.10+, aiohttp
metadata:
  author: schema-tool-project
  version: "1.1.0"
  language: python
---

# SEO AIO Engine — AI Agent 接口规范

## 快速决策

| 用户意图 | 调用方式 |
|----------|----------|
| "分析这个网页" | `analyze(url)` — 全量 14 模块 |
| "生成 Schema" | `generate_schema(url)` — 仅 schema 模块 |
| "优化文案" | `optimize_semantic(url)` — 仅语义优化 |
| "生成 FAQ" | `generate_faq(url)` — 仅 FAQ |
| "检查图片" | `analyze_multimodal(url)` — 仅多模态 |
| "检查权威信号" | `check_authority(url, lang="zh"|"en")` — 仅权威信号，自动检测语言 |
| "评分可引用性" | `score_citability(url)` — 仅 citability |
| "检查 robots.txt" | `check_robots(url)` — 仅 robots |
| "检查 llms.txt" | `check_llmstxt(url)` — 仅 llmstxt |
| "检查品牌" | `check_brand(url)` — 仅品牌 |
| "审计 Schema" | `audit_schema(url)` — 仅 schema 审计 |
| "平台优化评分" | `score_platform(url)` — 仅平台 |
| "技术审计" | `audit_technical(url)` — 仅技术 |
| "E-E-A-T 评分" | `score_eeat(url)` — 仅 E-E-A-T |
| "GSC 监控" | `track_monitor(url)` — 仅监控（需配置） |

## 函数签名表

```python
# 全量分析（向后兼容）
async def analyze(url: str) -> dict

# 独立模块调用（按需、低成本）
async def generate_schema(url: str, llm: LLMClient | None = None, session: aiohttp.ClientSession | None = None) -> dict
async def optimize_semantic(url: str, llm: LLMClient | None = None, session: aiohttp.ClientSession | None = None) -> dict
async def generate_faq(url: str, llm: LLMClient | None = None, session: aiohttp.ClientSession | None = None) -> dict
async def analyze_multimodal(url: str, llm: LLMClient | None = None, session: aiohttp.ClientSession | None = None) -> dict
async def check_authority(url: str, llm: LLMClient | None = None, session: aiohttp.ClientSession | None = None, lang: str | None = None) -> dict
async def score_citability(url: str, session: aiohttp.ClientSession | None = None) -> dict
async def check_robots(url: str, session: aiohttp.ClientSession | None = None) -> dict
async def check_llmstxt(url: str, session: aiohttp.ClientSession | None = None) -> dict
async def check_brand(url: str, session: aiohttp.ClientSession | None = None) -> dict
async def audit_schema(url: str, session: aiohttp.ClientSession | None = None) -> dict
async def score_platform(url: str, session: aiohttp.ClientSession | None = None) -> dict
async def audit_technical(url: str, session: aiohttp.ClientSession | None = None) -> dict
async def score_eeat(url: str, session: aiohttp.ClientSession | None = None) -> dict
async def track_monitor(url: str) -> dict
```

## Tools 数组（JSON Schema 格式）

```json
[
  {
    "name": "analyze",
    "description": "全量 SEO 分析：14 个模块并行执行，返回完整数据集。适合首次分析或需要综合评分的场景。",
    "parameters": {
      "type": "object",
      "properties": {
        "url": {"type": "string", "format": "uri", "description": "要分析的网页 URL"}
      },
      "required": ["url"]
    }
  },
  {
    "name": "generate_schema",
    "description": "推断页面 Schema.org 类型并生成 JSON-LD 框架，提取核心实体链接。",
    "parameters": {
      "type": "object",
      "properties": {
        "url": {"type": "string", "format": "uri"}
      },
      "required": ["url"]
    }
  },
  {
    "name": "optimize_semantic",
    "description": "诊断参数堆砌文案，改写为场景体验型描述，生成可引用片段和主题覆盖分析。",
    "parameters": {
      "type": "object",
      "properties": {
        "url": {"type": "string", "format": "uri"}
      },
      "required": ["url"]
    }
  },
  {
    "name": "generate_faq",
    "description": "围绕页面关键词自动生成高频问答内容（HTML 片段）。",
    "parameters": {
      "type": "object",
      "properties": {
        "url": {"type": "string", "format": "uri"}
      },
      "required": ["url"]
    }
  },
  {
    "name": "analyze_multimodal",
    "description": "检测图片 alt 缺失/无意义，生成 VideoObject Schema。",
    "parameters": {
      "type": "object",
      "properties": {
        "url": {"type": "string", "format": "uri"}
      },
      "required": ["url"]
    }
  },
  {
    "name": "check_authority",
    "description": "分析外部权威信号覆盖情况（中英文平台，自动语言检测：知乎、B站、Amazon、YouTube 等）。",
    "parameters": {
      "type": "object",
      "properties": {
        "url": {"type": "string", "format": "uri"}
      },
      "required": ["url"]
    }
  },
  {
    "name": "score_citability",
    "description": "5 维度评分内容块的可被 AI 引用质量（答案块质量、自包含性、结构可读性、统计密度、独特性）。",
    "parameters": {
      "type": "object",
      "properties": {
        "url": {"type": "string", "format": "uri"}
      },
      "required": ["url"]
    }
  },
  {
    "name": "check_robots",
    "description": "检测 robots.txt 对 14 个 AI 爬虫（GPTBot、ClaudeBot 等）的允许/封禁状态。",
    "parameters": {
      "type": "object",
      "properties": {
        "url": {"type": "string", "format": "uri"}
      },
      "required": ["url"]
    }
  },
  {
    "name": "check_llmstxt",
    "description": "检测 llms.txt / llms-full.txt 存在性和格式合规性。",
    "parameters": {
      "type": "object",
      "properties": {
        "url": {"type": "string", "format": "uri"}
      },
      "required": ["url"]
    }
  },
  {
    "name": "check_brand",
    "description": "检测品牌在 Wikipedia/Wikidata 等平台的 presence。",
    "parameters": {
      "type": "object",
      "properties": {
        "url": {"type": "string", "format": "uri"}
      },
      "required": ["url"]
    }
  },
  {
    "name": "audit_schema",
    "description": "审计页面现有 JSON-LD structured data，检测缺失和错误。",
    "parameters": {
      "type": "object",
      "properties": {
        "url": {"type": "string", "format": "uri"}
      },
      "required": ["url"]
    }
  },
  {
    "name": "score_platform",
    "description": "针对 5 个 AI 搜索平台（Google AIO、ChatGPT、Perplexity、Gemini、Bing Copilot）评分。",
    "parameters": {
      "type": "object",
      "properties": {
        "url": {"type": "string", "format": "uri"}
      },
      "required": ["url"]
    }
  },
  {
    "name": "audit_technical",
    "description": "8 维度技术 SEO 审计（可爬性、可索引性、安全、URL、移动、CWV、SSR、速度）。",
    "parameters": {
      "type": "object",
      "properties": {
        "url": {"type": "string", "format": "uri"}
      },
      "required": ["url"]
    }
  },
  {
    "name": "score_eeat",
    "description": "4 维度内容质量评分（Experience, Expertise, Authoritativeness, Trustworthiness）。",
    "parameters": {
      "type": "object",
      "properties": {
        "url": {"type": "string", "format": "uri"}
      },
      "required": ["url"]
    }
  },
  {
    "name": "track_monitor",
    "description": "追踪 GSC 搜索数据（点击、展示、CTR、排名趋势）。需额外安装 google-api-python-client。",
    "parameters": {
      "type": "object",
      "properties": {
        "url": {"type": "string", "format": "uri"}
      },
      "required": ["url"]
    }
  }
]
```

## 统一返回格式（ModuleResult）

所有函数返回以下结构的 dict：

```json
{
  "status": "success | error | skipped | unavailable",
  "score": 0,
  "score_details": {"reason": "...", "base_score": 0},
  "data": {},
  "fallback": false,
  "errors": [],
  "recommended_actions": [
    {"action": "...", "priority": "high|medium|low", "target_module": "...", "params": {}}
  ]
}
```

## 环境配置

### 方式一：config.json（推荐）

编辑 `scripts/aio_engine/config.json`：

```json
{
  "llm": {
    "provider": "anthropic",
    "api_key": "sk-...",
    "model": "",
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

### 方式二：环境变量（兜底配置）

```bash
export ANTHROPIC_API_KEY="sk-..."
export LLM_PROVIDER="anthropic"
export LLM_MODEL=""
```

**优先级：config.json > 环境变量 > 默认值**

config.json 覆盖环境变量，适合固定生产环境配置。

## 使用示例

```python
import sys, asyncio
sys.path.insert(0, "scripts")

# 全量分析
from aio_engine import analyze
result = asyncio.run(analyze("https://example.com"))

# 按需单模块（更快、更省 token）
from aio_engine.modules import check_robots, score_citability
robots = asyncio.run(check_robots("https://example.com"))
citability = asyncio.run(score_citability("https://example.com"))

# 共享 session（复用连接池）
import aiohttp
from aio_engine.modules import check_robots, score_citability

async def main():
    async with aiohttp.ClientSession() as session:
        robots = await check_robots("https://example.com", session=session)
        citability = await score_citability("https://example.com", session=session)

asyncio.run(main())
```

## 架构

```
seo-aio-engine/
  scripts/aio_engine/
    __init__.py          # analyze() + Workflow（全量入口）
    __main__.py          # CLI 入口
    workflow.py          # 工作流编排器（3 阶段 + 缓存 + 依赖检查）
    schemas.py           # 输出模型定义（AnalysisResult / ModuleResult 等）
    config.json          # 固定配置文件（LLM / Crawler / Cache）
    lib/
      __init__.py
      config.py          # 配置加载器（config.json > 环境变量 > 默认值）
      llm_client.py      # 9 提供商 LLM 客户端 + Prompt 注入防护
      crawler.py         # 异步抓取 + SSRF 防护 + 共享 session
      schema_cache.py    # Schema.org 类型缓存
      cache.py           # 可选内存缓存层（TTL）
      html_utils.py      # HTML 特征提取（表格/列表/作者/日期等）
      json_utils.py      # JSON 回退解析（LLM 响应容错）
      session_utils.py   # NullContextManager 共享工具
    modules/
      __init__.py        # 14 个独立异步函数（按需入口）
      page_parser.py     # 页面解析
      schema_generator.py
      semantic_optimizer.py
      faq_generator.py
      multimodal_labeler.py
      authority_checker.py
      citability_scorer.py
      robots_checker.py
      llmstxt_checker.py
      brand_checker.py
      schema_auditor.py
      platform_optimizer.py
      technical_auditor.py
      eeat_scorer.py
      monitor.py         # 可选
```

## 底座化特性

- **scoreDetails**: 每个模块返回评分明细（base_score、reason 等）
- **fallback 标记**: 降级策略时显式标注
- **errors[]**: 错误信息数组
- **targetModule + params**: 每个 action 包含目标模块和参数
- **模块依赖声明**: 缺失输入时自动标记 skipped
- **SSRF 防护**: URL 验证阻断内网/非 HTTP(S) 请求
- **Prompt 注入防护**: 用户内容 sanitization，中和系统消息分隔符等注入模式
- **共享 aiohttp Session**: Workflow 内统一创建和注入，连接池复用
- **LLM 响应结构校验**: 提取文本前校验 `content`/`choices` 数组非空
- **图片大小限制**: 多模态下载限制 10MB，防止内存耗尽
- **边界安全**: 空列表/None/空字符串统一处理，除零保护，越界保护
- **独立入口共享 session**: `modules/__init__.py` 各函数支持 `session` 参数，复用 aiohttp 连接池
