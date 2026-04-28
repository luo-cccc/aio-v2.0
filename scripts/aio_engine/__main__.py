#!/usr/bin/env python3
"""
aio-engine CLI 入口
===================

用法:
    python -m scripts.aio_engine --url https://example.com/product
    python -m scripts.aio_engine --url https://example.com/product --format text
    python -m scripts.aio_engine --url https://example.com/product --output report.json
"""

import asyncio
import argparse
import json
import sys

from . import analyze, Workflow


def main():
    parser = argparse.ArgumentParser(
        description="aio-engine: 文章 SEO + GEO 优化引擎 v2.0.0",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python -m scripts.aio_engine --url https://example.com/product
  python -m scripts.aio_engine --url https://example.com/product --format text
  python -m scripts.aio_engine --url https://example.com/product --output report.json
        """,
    )
    parser.add_argument("--url", "-u", required=True, help="要分析的页面 URL")
    parser.add_argument("--format", "-f", choices=["json", "text"], default="json", help="输出格式（默认 json）")
    parser.add_argument("--output", "-o", help="输出到文件")
    parser.add_argument("--workflow", "-w", action="store_true", help="使用工作流模式（输出包含步骤追踪）")
    args = parser.parse_args()

    if args.workflow:
        wf = Workflow()
        try:
            result = asyncio.run(wf.run(args.url))
        finally:
            asyncio.run(wf.close())
    else:
        result = asyncio.run(analyze(args.url))

    if args.format == "text":
        output = _format_text(result)
    else:
        output = json.dumps(result, ensure_ascii=False, indent=2)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output)
        print(f"[信息] 报告已保存到: {args.output}")
    else:
        print(output)


def _format_text(result: dict) -> str:
    lines = []
    meta = result.get("meta", {})
    page = result.get("pageData", {})
    scores = result.get("scores", {})
    actions = result.get("actions", [])
    statuses = result.get("moduleStatuses", {})
    workflow = result.get("workflow", {})

    lines.append("=" * 60)
    lines.append("  aio-engine 分析报告")
    lines.append("=" * 60)
    lines.append("")
    lines.append(f"URL: {meta.get('url', '')}")
    lines.append(f"分析时间: {meta.get('analyzedAt', '')}")
    lines.append(f"耗时: {meta.get('durationMs', 0)}ms")
    lines.append("")

    lines.append("【页面信息】")
    lines.append(f"  标题: {page.get('title', '')}")
    lines.append(f"  类型: {page.get('type', '')}")
    lines.append(f"  已有 Schema: {', '.join(page.get('existingSchemas', [])) or '无'}")
    lines.append("")

    lines.append("【评分】")
    overall = scores.get("overall")
    lines.append(f"  综合评分: {overall if overall is not None else 'N/A'}")
    lines.append("")

    # moduleResults 中的 scoreDetails
    module_results = result.get("moduleResults", {})
    if module_results:
        lines.append("【模块评分详情】")
        for name, mod in module_results.items():
            sd = mod.get("scoreDetails") or {}
            if sd:
                reason = sd.get("reason", "")
                lines.append(f"  {name}: {reason}")
        lines.append("")

    lines.append("【模块状态】")
    for name, status in statuses.items():
        status_zh = {"success": "成功", "error": "失败", "skipped": "跳过", "unavailable": "不可用"}.get(status, status)
        lines.append(f"  {name}: {status_zh}")
    lines.append("")

    # 工作流步骤耗时（如存在）
    steps = workflow.get("steps", {})
    if steps:
        lines.append("【步骤耗时】")
        for name, info in steps.items():
            status = info.get("status", "")
            duration = info.get("durationMs", 0)
            lines.append(f"  {name}: {duration}ms ({status})")
        lines.append("")

    if actions:
        lines.append("【改进行动】")
        for a in actions:
            p = a.get("priority", "low")
            p_zh = {"high": "高", "medium": "中", "low": "低"}.get(p, p)
            target = a.get("targetModule", "")
            target_str = f" -> {target}" if target else ""
            lines.append(f"  [{p_zh}] {a.get('action', '')}{target_str}")
        lines.append("")

    return "\n".join(lines)


if __name__ == "__main__":
    main()
