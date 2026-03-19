#!/usr/bin/env python3
"""
Metrics Aggregator (v2.0) - 汇总 LLM 调用统计
从 reports/*_progress.jsonl 和 data/llm_trace.jsonl 读取数据
生成包含 Token 消耗和费用估算的统计报告

Features:
- Token 统计 (prompt_tokens, completion_tokens)
- 费用计算 (结合 config/pricing.yaml)
- API 余额查询 (可选)
- Markdown + JSON 双格式输出
"""

import os
import sys
import json
import glob
import math
import yaml
import requests
from datetime import datetime
from collections import defaultdict
from typing import Optional, Dict, Any

# 确保输出不缓冲
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(line_buffering=True)

def load_pricing_config(pricing_path: str = "config/pricing.yaml") -> Dict[str, Any]:
    """加载定价配置"""
    if not os.path.exists(pricing_path):
        # 尝试相对路径
        script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        pricing_path = os.path.join(script_dir, "config", "pricing.yaml")

    if os.path.exists(pricing_path):
        with open(pricing_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f) or {}

    # 默认定价 (per 1M tokens, USD)
    return {
        "models": {
            "claude-haiku-4-5-20251001": {"input_per_1M": 0.25, "output_per_1M": 1.25},
            "claude-sonnet-4-5-20250929": {"input_per_1M": 3.0, "output_per_1M": 15.0},
            "gpt-4.1-mini": {"input_per_1M": 0.15, "output_per_1M": 0.60},
            "gpt-4.1": {"input_per_1M": 2.0, "output_per_1M": 8.0},
            "text-embedding-3-small": {"input_per_1M": 0.02, "output_per_1M": 0.0},
            "_default": {"input_per_1M": 0.50, "output_per_1M": 2.0}
        }
    }

def query_api_balance() -> Optional[Dict[str, Any]]:
    """
    查询 API 余额 (如果支持)

    Returns:
        dict: {"balance": float, "currency": str, "updated_at": str} 或 None
    """
    base_url = os.getenv("LLM_BASE_URL", "").strip().rstrip("/")
    api_key = os.getenv("LLM_API_KEY", "").strip()

    if not base_url or not api_key:
        return None

    # 尝试常见的余额查询端点
    balance_endpoints = [
        "/dashboard/billing/credit_grants",  # OpenAI 风格
        "/v1/dashboard/billing/credit_grants",
        "/user/balance",  # 某些代理网关
        "/v1/user/balance",
    ]

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    for endpoint in balance_endpoints:
        try:
            resp = requests.get(
                f"{base_url}{endpoint}",
                headers=headers,
                timeout=10
            )
            if resp.status_code == 200:
                data = resp.json()
                # 解析不同格式的响应
                if "total_available" in data:
                    return {
                        "balance": float(data["total_available"]),
                        "currency": "USD",
                        "updated_at": datetime.now().isoformat(),
                        "source": endpoint
                    }
                elif "balance" in data:
                    return {
                        "balance": float(data["balance"]),
                        "currency": data.get("currency", "USD"),
                        "updated_at": datetime.now().isoformat(),
                        "source": endpoint
                    }
                elif "data" in data and isinstance(data["data"], dict):
                    # 嵌套格式
                    inner = data["data"]
                    if "balance" in inner:
                        return {
                            "balance": float(inner["balance"]),
                            "currency": inner.get("currency", "USD"),
                            "updated_at": datetime.now().isoformat(),
                            "source": endpoint
                        }
        except Exception:
            continue

    return None

def load_progress_logs(reports_dir: str = "reports") -> list:
    """加载所有 JSONL 进度日志"""
    all_events = []

    pattern = os.path.join(reports_dir, "*_progress.jsonl")
    for filepath in glob.glob(pattern):
        with open(filepath, 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    try:
                        event = json.loads(line)
                        event['_source_file'] = os.path.basename(filepath)
                        all_events.append(event)
                    except json.JSONDecodeError:
                        continue

    return all_events

def load_trace_logs(trace_path: str = "data/llm_trace.jsonl") -> list:
    """加载 LLM trace 日志 (包含详细 token 信息)"""
    events = []

    if not os.path.exists(trace_path):
        return events

    with open(trace_path, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip():
                try:
                    event = json.loads(line)
                    events.append(event)
                except json.JSONDecodeError:
                    continue

    return events


def _estimate_tokens_from_chars(char_count: Any) -> int:
    if char_count in (None, "", 0):
        return 0
    try:
        value = int(char_count)
    except (TypeError, ValueError):
        return 0
    if value <= 0:
        return 0
    return max(1, math.ceil(value / 4))


def _normalize_usage_record(record: Dict[str, Any]) -> Dict[str, int]:
    usage = record.get("usage")
    if isinstance(usage, dict):
        prompt_tokens = int(usage.get("prompt_tokens") or 0)
        completion_tokens = int(usage.get("completion_tokens") or 0)
        total_tokens = int(usage.get("total_tokens") or (prompt_tokens + completion_tokens))
        return {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
            "estimated": False,
        }

    prompt_tokens = record.get("prompt_tokens")
    completion_tokens = record.get("completion_tokens")
    total_tokens = record.get("total_tokens")
    if prompt_tokens is not None or completion_tokens is not None or total_tokens is not None:
        pt = int(prompt_tokens or 0)
        ct = int(completion_tokens or 0)
        return {
            "prompt_tokens": pt,
            "completion_tokens": ct,
            "total_tokens": int(total_tokens or (pt + ct)),
            "estimated": False,
        }

    estimated_prompt = _estimate_tokens_from_chars(record.get("req_chars"))
    estimated_completion = _estimate_tokens_from_chars(record.get("resp_chars"))
    if estimated_prompt or estimated_completion:
        return {
            "prompt_tokens": estimated_prompt,
            "completion_tokens": estimated_completion,
            "total_tokens": estimated_prompt + estimated_completion,
            "estimated": True,
        }

    return {
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
        "estimated": False,
    }

def aggregate_metrics(events: list, trace_events: list = None, pricing: dict = None) -> dict:
    """汇总指标，包含 Token 和费用计算"""

    if pricing is None:
        pricing = load_pricing_config()

    metrics = {
        'summary': {
            'total_steps': 0,
            'total_batches': 0,
            'total_rows': 0,
            'total_success': 0,
            'total_failed': 0,
            'total_latency_ms': 0,
            'total_prompt_tokens': 0,
            'total_completion_tokens': 0,
            'total_tokens': 0,
            'estimated_cost_usd': 0.0,
            'estimated_usage_batches': 0,
        },
        'by_step': defaultdict(lambda: {
            'batches': 0,
            'rows': 0,
            'success': 0,
            'failed': 0,
            'latency_ms': 0,
            'prompt_tokens': 0,
            'completion_tokens': 0,
            'estimated_cost_usd': 0.0,
            'models': set()
        }),
        'by_model': defaultdict(lambda: {
            'batches': 0,
            'rows': 0,
            'latency_ms': 0,
            'prompt_tokens': 0,
            'completion_tokens': 0,
            'estimated_cost_usd': 0.0
        }),
        'api_balance': None
    }

    steps_seen = set()
    model_pricing = pricing.get("models", {})
    default_pricing = model_pricing.get("_default", {"input_per_1M": 0.5, "output_per_1M": 2.0})

    # 从 trace 日志构建 token 查找表 (按 request_id)
    token_lookup = {}
    if trace_events:
        for event in trace_events:
            req_id = event.get("request_id")
            if not req_id:
                continue
            token_lookup[req_id] = _normalize_usage_record(event)

    for event in events:
        step = event.get('step', 'unknown')
        event_type = event.get('event', '')

        # 跳过 unknown 步骤 (历史残留)
        if step == 'unknown':
            continue

        if event_type == 'step_start':
            steps_seen.add(step)
            model = event.get('model') or event.get('model_name') or 'unspecified'
            if model and model not in ('unknown', 'unspecified'):
                metrics['by_step'][step]['models'].add(model)

        elif event_type == 'batch_complete':
            rows = event.get('rows_in_batch') or event.get('batch_size') or 0
            latency = event.get('latency_ms', 0)
            status = event.get('status', 'SUCCESS')
            model = event.get('model') or event.get('model_name') or 'unspecified'

            # 获取 token 使用量
            usage = event.get('usage', {})
            if not usage:
                # 尝试从 trace 查找
                req_id = event.get('request_id')
                if req_id and req_id in token_lookup:
                    usage = token_lookup[req_id]
                else:
                    usage = _normalize_usage_record(event)

            prompt_tokens = usage.get('prompt_tokens', 0)
            completion_tokens = usage.get('completion_tokens', 0)
            if usage.get('estimated'):
                metrics['summary']['estimated_usage_batches'] += 1

            # 计算费用
            mp = model_pricing.get(model, default_pricing)
            batch_cost = (
                prompt_tokens * mp.get('input_per_1M', 0.5) / 1_000_000 +
                completion_tokens * mp.get('output_per_1M', 2.0) / 1_000_000
            )

            # 更新 summary
            metrics['summary']['total_batches'] += 1
            metrics['summary']['total_rows'] += rows
            metrics['summary']['total_latency_ms'] += latency
            metrics['summary']['total_prompt_tokens'] += prompt_tokens
            metrics['summary']['total_completion_tokens'] += completion_tokens
            metrics['summary']['estimated_cost_usd'] += batch_cost

            if status in ('SUCCESS', 'ok', 'success'):
                metrics['summary']['total_success'] += rows
            else:
                metrics['summary']['total_failed'] += rows

            # 更新 by_step
            metrics['by_step'][step]['batches'] += 1
            metrics['by_step'][step]['rows'] += rows
            metrics['by_step'][step]['latency_ms'] += latency
            metrics['by_step'][step]['prompt_tokens'] += prompt_tokens
            metrics['by_step'][step]['completion_tokens'] += completion_tokens
            metrics['by_step'][step]['estimated_cost_usd'] += batch_cost

            if status in ('SUCCESS', 'ok', 'success'):
                metrics['by_step'][step]['success'] += rows
            else:
                metrics['by_step'][step]['failed'] += rows

            # 更新 by_model
            if model and model not in ('unknown', 'unspecified'):
                metrics['by_model'][model]['batches'] += 1
                metrics['by_model'][model]['rows'] += rows
                metrics['by_model'][model]['latency_ms'] += latency
                metrics['by_model'][model]['prompt_tokens'] += prompt_tokens
                metrics['by_model'][model]['completion_tokens'] += completion_tokens
                metrics['by_model'][model]['estimated_cost_usd'] += batch_cost

    # 计算总 token
    metrics['summary']['total_tokens'] = (
        metrics['summary']['total_prompt_tokens'] +
        metrics['summary']['total_completion_tokens']
    )

    # 四舍五入费用
    metrics['summary']['estimated_cost_usd'] = round(
        metrics['summary']['estimated_cost_usd'], 6
    )

    for step_data in metrics['by_step'].values():
        step_data['estimated_cost_usd'] = round(step_data['estimated_cost_usd'], 6)
        step_data['models'] = list(step_data['models'])

    for model_data in metrics['by_model'].values():
        model_data['estimated_cost_usd'] = round(model_data['estimated_cost_usd'], 6)

    metrics['summary']['total_steps'] = len(steps_seen)

    return metrics

def generate_report(metrics: dict, output_path: str = "reports/metrics_report.md"):
    """生成增强版 Markdown 报告"""

    lines = [
        "# LLM 调用统计报告 (v2.0)",
        f"\n生成时间: {datetime.now().isoformat()}",
    ]

    # API 余额 (如果有)
    if metrics.get('api_balance'):
        balance = metrics['api_balance']
        lines.extend([
            "\n## API 余额",
            f"\n| 项目 | 值 |",
            f"|------|-----|",
            f"| 当前余额 | {balance['balance']:.4f} {balance['currency']} |",
            f"| 查询时间 | {balance['updated_at']} |",
        ])

    # 总体统计
    s = metrics['summary']
    lines.extend([
        "\n## 总体统计\n",
        f"| 指标 | 值 |",
        f"|------|-----|",
        f"| 步骤数 | {s['total_steps']} |",
        f"| 批次数 | {s['total_batches']} |",
        f"| 总行数 | {s['total_rows']} |",
        f"| 成功 | {s['total_success']} |",
        f"| 失败 | {s['total_failed']} |",
        f"| 总延迟 | {s['total_latency_ms']:,}ms ({s['total_latency_ms']/1000:.1f}s) |",
        f"| Prompt Tokens | {s['total_prompt_tokens']:,} |",
        f"| Completion Tokens | {s['total_completion_tokens']:,} |",
        f"| **总 Tokens** | **{s['total_tokens']:,}** |",
        f"| **估算费用** | **${s['estimated_cost_usd']:.4f} USD** |",
        f"| 估算 Token 批次数 | {s.get('estimated_usage_batches', 0)} |",
    ])

    # 按步骤统计
    lines.extend([
        "\n## 按步骤统计\n",
        "| 步骤 | 批次 | 行数 | Tokens | 费用(USD) | 延迟(s) | 模型 |",
        "|------|------|------|--------|-----------|---------|------|"
    ])

    for step, data in sorted(metrics['by_step'].items()):
        total_tokens = data['prompt_tokens'] + data['completion_tokens']
        models = ', '.join(data['models'][:2]) if data['models'] else 'N/A'
        if len(data['models']) > 2:
            models += f" (+{len(data['models'])-2})"

        lines.append(
            f"| {step} | {data['batches']} | {data['rows']} | "
            f"{total_tokens:,} | ${data['estimated_cost_usd']:.4f} | "
            f"{data['latency_ms']/1000:.1f} | {models} |"
        )

    # 按模型统计
    if metrics['by_model']:
        lines.extend([
            "\n## 按模型统计\n",
            "| 模型 | 批次 | 行数 | Prompt | Completion | 费用(USD) |",
            "|------|------|------|--------|------------|-----------|"
        ])

        for model, data in sorted(metrics['by_model'].items()):
            lines.append(
                f"| {model} | {data['batches']} | {data['rows']} | "
                f"{data['prompt_tokens']:,} | {data['completion_tokens']:,} | "
                f"${data['estimated_cost_usd']:.4f} |"
            )

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))

    print(f"✅ Metrics 报告已生成: {output_path}")
    return output_path

def main():
    import argparse
    parser = argparse.ArgumentParser(description="汇总 LLM 调用统计 (v2.0)")
    parser.add_argument("--reports-dir", default="reports", help="JSONL 日志目录")
    parser.add_argument("--trace-path", default="data/llm_trace.jsonl", help="LLM trace 日志路径")
    parser.add_argument("--output", default="reports/metrics_report", help="输出报告路径 (不含扩展名)")
    parser.add_argument("--query-balance", action="store_true", help="查询 API 余额")
    parser.add_argument("--json", action="store_true", help="同时输出 JSON 格式")

    args = parser.parse_args()

    # 加载 pricing
    pricing = load_pricing_config()
    print(f"已加载定价配置: {len(pricing.get('models', {}))} 个模型")

    # 加载 progress 日志
    events = load_progress_logs(args.reports_dir)
    print(f"加载了 {len(events)} 条 progress 事件")

    # 加载 trace 日志
    trace_events = load_trace_logs(args.trace_path)
    print(f"加载了 {len(trace_events)} 条 trace 事件")

    if not events:
        print("⚠️ 没有找到任何 progress 事件")
        return

    # 汇总指标
    metrics = aggregate_metrics(events, trace_events, pricing)

    # 查询 API 余额 (可选)
    if args.query_balance:
        print("正在查询 API 余额...")
        balance = query_api_balance()
        if balance:
            metrics['api_balance'] = balance
            print(f"✅ 余额: {balance['balance']:.4f} {balance['currency']}")
        else:
            print("⚠️ 无法查询余额 (端点不支持或认证失败)")

    # 生成报告
    md_path = args.output if args.output.endswith('.md') else f"{args.output}.md"
    generate_report(metrics, md_path)

    # JSON 输出
    if args.json:
        json_path = args.output.replace('.md', '') + '.json'
        # 转换 defaultdict 为普通 dict
        output_metrics = json.loads(json.dumps(metrics, default=list))
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(output_metrics, f, indent=2, ensure_ascii=False)
        print(f"✅ JSON 报告: {json_path}")

    # 打印摘要
    s = metrics['summary']
    print(f"\n📊 统计摘要:")
    print(f"   总 Tokens: {s['total_tokens']:,}")
    print(f"   估算费用: ${s['estimated_cost_usd']:.4f} USD")

if __name__ == "__main__":
    main()
