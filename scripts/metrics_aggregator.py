#!/usr/bin/env python3
"""
Metrics Aggregator - 汇总 LLM 调用统计
从 reports/*_progress.jsonl 读取数据，生成统计报告
"""

import os
import json
import glob
from datetime import datetime
from collections import defaultdict

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

def aggregate_metrics(events: list) -> dict:
    """汇总指标"""
    metrics = {
        'summary': {
            'total_steps': 0,
            'total_batches': 0,
            'total_rows': 0,
            'total_success': 0,
            'total_failed': 0,
            'total_latency_ms': 0
        },
        'by_step': defaultdict(lambda: {
            'batches': 0,
            'rows': 0,
            'success': 0,
            'failed': 0,
            'latency_ms': 0,
            'models': set()
        }),
        'by_model': defaultdict(lambda: {
            'batches': 0,
            'rows': 0,
            'latency_ms': 0
        })
    }

    steps_seen = set()

    for event in events:
        step = event.get('step', 'unknown')
        event_type = event.get('event', '')

        # 跳过 unknown 步骤 (历史残留)
        if step == 'unknown':
            continue

        if event_type == 'step_start':
            steps_seen.add(step)
            # 兼容多种 model 字段名
            model = event.get('model') or event.get('model_name') or 'unspecified'
            if model and model != 'unknown' and model != 'unspecified':
                metrics['by_step'][step]['models'].add(model)

        elif event_type == 'batch_complete':
            # 兼容多种行数字段名
            rows = event.get('rows_in_batch') or event.get('batch_size') or 0
            latency = event.get('latency_ms', 0)
            status = event.get('status', 'SUCCESS')

            metrics['summary']['total_batches'] += 1
            metrics['summary']['total_rows'] += rows
            metrics['summary']['total_latency_ms'] += latency

            if status in ('SUCCESS', 'ok', 'success'):
                metrics['summary']['total_success'] += rows
            else:
                metrics['summary']['total_failed'] += rows

            metrics['by_step'][step]['batches'] += 1
            metrics['by_step'][step]['rows'] += rows
            metrics['by_step'][step]['latency_ms'] += latency

            if status in ('SUCCESS', 'ok', 'success'):
                metrics['by_step'][step]['success'] += rows
            else:
                metrics['by_step'][step]['failed'] += rows

            # 记录 by_model 统计
            model = event.get('model') or event.get('model_name') or 'unspecified'
            if model and model != 'unknown':
                metrics['by_model'][model]['batches'] += 1
                metrics['by_model'][model]['rows'] += rows
                metrics['by_model'][model]['latency_ms'] += latency

    metrics['summary']['total_steps'] = len(steps_seen)

    # 转换 set 为 list (JSON 序列化)
    for step_data in metrics['by_step'].values():
        step_data['models'] = list(step_data['models'])

    return metrics

def generate_report(metrics: dict, output_path: str = "reports/metrics_report.md"):
    """生成 Markdown 报告"""
    lines = [
        "# LLM 调用统计报告",
        f"\n生成时间: {datetime.now().isoformat()}",
        "\n## 总体统计\n",
        f"| 指标 | 值 |",
        f"|------|-----|",
        f"| 步骤数 | {metrics['summary']['total_steps']} |",
        f"| 批次数 | {metrics['summary']['total_batches']} |",
        f"| 总行数 | {metrics['summary']['total_rows']} |",
        f"| 成功 | {metrics['summary']['total_success']} |",
        f"| 失败 | {metrics['summary']['total_failed']} |",
        f"| 总延迟 | {metrics['summary']['total_latency_ms']}ms |",
        "\n## 按步骤统计\n",
        "| 步骤 | 批次 | 行数 | 成功 | 失败 | 延迟(ms) | 模型 |",
        "|------|------|------|------|------|----------|------|"
    ]

    for step, data in metrics['by_step'].items():
        models = ', '.join(data['models']) if data['models'] else 'N/A'
        lines.append(
            f"| {step} | {data['batches']} | {data['rows']} | "
            f"{data['success']} | {data['failed']} | {data['latency_ms']} | {models} |"
        )

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))

    print(f"✅ Metrics 报告已生成: {output_path}")
    return output_path

def main():
    import argparse
    parser = argparse.ArgumentParser(description="汇总 LLM 调用统计")
    parser.add_argument("--reports-dir", default="reports", help="JSONL 日志目录")
    parser.add_argument("--output", default="reports/metrics_report.md", help="输出报告路径")
    parser.add_argument("--json", action="store_true", help="同时输出 JSON 格式")

    args = parser.parse_args()

    # Load events
    if not os.path.exists(args.reports_dir):
        print(f"❌ 目录不存在: {args.reports_dir}")
        return

    events = load_progress_logs(args.reports_dir)
    print(f"加载了 {len(events)} 条事件")

    if not events:
        print("⚠️ 没有找到任何事件")
        return

    metrics = aggregate_metrics(events)

    generate_report(metrics, args.output)

    if args.json:
        json_path = args.output.replace('.md', '.json')
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(metrics, f, indent=2, ensure_ascii=False)
        print(f"✅ JSON 报告: {json_path}")

if __name__ == "__main__":
    main()
