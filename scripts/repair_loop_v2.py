#!/usr/bin/env python3
"""
Repair Loop v2.0 - 批处理 + 多层汇报 + Fallback Models

核心改进:
1. 批处理模式 (默认 10 个任务/批次)
2. 完整的多层汇报机制
3. 三轮修复 + Fallback Models
4. Escalation 到人工审核
"""

import os
import sys
import json
import yaml
import pandas as pd
import time
from datetime import datetime
from typing import List, Dict, Optional, Tuple

# 导入进度汇报器
from progress_reporter import ProgressReporter

# 强制 unbuffered 与 UTF-8 输出 (兼容 Windows)
for stream in [sys.stdout, sys.stderr]:
    if stream:
        if hasattr(stream, 'reconfigure'):
            try:
                stream.reconfigure(encoding='utf-8', errors='replace', line_buffering=True)
            except Exception:
                pass # Fallback if reconfigure fails on certain streams

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(line_buffering=True)

def load_repair_config(path: str = "config/repair_config.yaml") -> dict:
    """加载修复配置"""
    default_config = {
        "repair_loop": {
            "max_rounds": 3,
            "batch_size": 10,
            "rounds": {
                1: {"model": "claude-haiku-4-5-20251001", "prompt_variant": "standard", "temperature": 0.3},
                2: {"model": "claude-haiku-4-5-20251001", "prompt_variant": "detailed", "temperature": 0.5},
                3: {"model": "claude-sonnet-4-5-20250929", "prompt_variant": "expert", "temperature": 0.7}
            },
            "timeout_per_batch_s": 120
        }
    }

    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            loaded = yaml.safe_load(f) or {}
            # 合并配置
            if "repair_loop" in loaded:
                default_config["repair_loop"].update(loaded["repair_loop"])

    return default_config

class RepairTask:
    """单个修复任务"""
    def __init__(self, task_data: dict):
        self.string_id = str(task_data.get("string_id", ""))
        self.source_text = task_data.get("source_text", "")
        self.current_translation = task_data.get("current_translation", "") or task_data.get("target_text", "")
        self.issues = task_data.get("issues", [])
        self.severity = task_data.get("severity", "major")
        self.max_length = task_data.get("max_length_target", 0)
        self.content_type = task_data.get("content_type", "")

        self.repair_history = []
        self.status = "pending"
        self.final_translation = None

    def add_attempt(self, round_num: int, model: str, translation: str,
                    validation: dict, success: bool):
        self.repair_history.append({
            "round": round_num,
            "model": model,
            "timestamp": datetime.now().isoformat(),
            "attempted_fix": translation,
            "validation": validation,
            "success": success
        })

        if success:
            self.status = "repaired"
            self.final_translation = translation

    def escalate(self, reason: str):
        self.status = "escalated"
        self.repair_history.append({
            "round": "escalation",
            "timestamp": datetime.now().isoformat(),
            "reason": reason
        })

    def to_escalation_record(self) -> dict:
        return {
            "string_id": self.string_id,
            "source_text": self.source_text,
            "current_translation": self.current_translation,
            "content_type": self.content_type,
            "max_length_target": self.max_length,
            "issues": self.issues,
            "severity": self.severity,
            "repair_history": self.repair_history,
            "suggested_action": self._suggest_action()
        }

    def _suggest_action(self) -> str:
        issue_types = [i.get("type", "") for i in self.issues]
        if "placeholder_mismatch" in issue_types:
            return "检查占位符，确保源文本和译文一致"
        elif "length_overflow" in issue_types:
            return "缩短译文，使用更简洁的表达"
        elif "glossary_violation" in issue_types:
            return "参考术语表修正专有名词"
        else:
            return "人工审核并优化翻译质量"

class BatchRepairLoop:
    """批处理修复引擎"""

    def __init__(self, config: dict, qa_type: str = "soft", output_dir: str = "."):
        self.config = config.get("repair_loop", {})
        self.max_rounds = self.config.get("max_rounds", 3)
        self.batch_size = self.config.get("batch_size", 10)
        self.rounds_config = self.config.get("rounds", {})
        self.qa_type = qa_type
        self.output_dir = output_dir

        self.stats = {
            "total_tasks": 0,
            "repaired": 0,
            "escalated": 0,
            "by_round": {1: 0, 2: 0, 3: 0}
        }

    def run(self, tasks: List[RepairTask], data_df: pd.DataFrame) -> Tuple[pd.DataFrame, List[dict]]:
        """执行批处理修复"""
        from runtime_adapter import LLMClient

        self.stats["total_tasks"] = len(tasks)
        escalations = []

        # 初始化进度汇报器
        reporter = ProgressReporter(
            step=f"repair_{self.qa_type}",
            output_dir=self.output_dir,
            total_items=len(tasks),
            max_rounds=self.max_rounds
        )
        reporter.start({
            "max_rounds": self.max_rounds,
            "batch_size": self.batch_size
        })

        # 从 DataFrame 补全任务缺失的元数据 (如 max_length)
        self._enrich_tasks_from_df(tasks, data_df)

        for round_num in range(1, self.max_rounds + 1):
            pending_tasks = [t for t in tasks if t.status == "pending"]

            if not pending_tasks:
                break

            round_config = self.rounds_config.get(round_num, self.rounds_config.get(1, {}))
            model = round_config.get("model", "claude-haiku-4-5-20251001")
            prompt_variant = round_config.get("prompt_variant", "standard")
            temperature = round_config.get("temperature", 0.5)

            self._print_round_header(round_num, model, len(pending_tasks))

            # 分批处理
            total_batches = (len(pending_tasks) + self.batch_size - 1) // self.batch_size
            client = LLMClient()

            for batch_idx in range(total_batches):
                start_idx = batch_idx * self.batch_size
                end_idx = min(start_idx + self.batch_size, len(pending_tasks))
                batch_tasks = pending_tasks[start_idx:end_idx]
                batch_num = batch_idx + 1

                reporter.batch_start(batch_num, total_batches, len(batch_tasks))

                t0 = time.time()

                try:
                    # 构建批量修复 prompt
                    prompt = self._build_batch_prompt(batch_tasks, prompt_variant)

                    result = client.chat(
                        system=prompt["system"],
                        user=prompt["user"],
                        temperature=temperature,
                        metadata={
                            "step": f"repair_{self.qa_type}",
                            "round": round_num,
                            "batch_num": batch_num
                        },
                        timeout=self.config.get("timeout_per_batch_s", 120)
                    )

                    # 解析批量结果
                    repairs = self._parse_batch_result(result.text, batch_tasks)

                    # 验证并应用修复
                    success_count = 0
                    for task, repair in zip(batch_tasks, repairs):
                        validation = self._validate_repair(repair, task)
                        success = validation.get("passed", False)

                        task.add_attempt(round_num, model, repair, validation, success)

                        if success:
                            success_count += 1
                            self.stats["repaired"] += 1
                            self.stats["by_round"][round_num] += 1
                            data_df = self._apply_repair(data_df, task)

                    latency_ms = int((time.time() - t0) * 1000)
                    reporter.batch_complete(
                        batch_num, total_batches,
                        success_count=success_count,
                        failed_count=len(batch_tasks) - success_count,
                        latency_ms=latency_ms,
                        metadata={"model": model, "round": round_num}
                    )
                    sys.stdout.flush()

                    # Checkpointing every 5 batches
                    if batch_num % 5 == 0:
                         ckpt_path = os.path.join(self.output_dir, f"{self.qa_type}_repair_checkpoint.csv")
                         data_df.to_csv(ckpt_path, index=False, encoding='utf-8')
                         print(f"💾 Checkpoint saved: {ckpt_path}")
                         sys.stdout.flush()

                except Exception as e:
                    latency_ms = int((time.time() - t0) * 1000)
                    reporter.batch_complete(
                        batch_num, total_batches,
                        success_count=0,
                        failed_count=len(batch_tasks),
                        latency_ms=latency_ms,
                        metadata={"error": str(e)}
                    )
                    print(f"❌ Batch {batch_num} error: {e}")
                    sys.stdout.flush()

            # 轮次结束汇报
            pending_after = [t for t in tasks if t.status == "pending"]
            reporter.round_complete(round_num, len(pending_after))

        # 处理仍未修复的任务 -> Escalate
        for task in tasks:
            if task.status == "pending":
                task.escalate(f"Failed after {self.max_rounds} repair rounds")
                escalations.append(task.to_escalation_record())
                self.stats["escalated"] += 1

        reporter.complete(
            self.stats["repaired"],
            self.stats["escalated"],
            metadata={"by_round": self.stats["by_round"]}
        )

        # 保存统计
        stats_path = os.path.join(self.output_dir, f"repair_{self.qa_type}_stats.json")
        with open(stats_path, 'w', encoding='utf-8') as f:
            json.dump(self.stats, f, indent=2)

        return data_df, escalations

    def _build_batch_prompt(self, tasks: List[RepairTask], variant: str) -> dict:
        """构建批量修复 prompt"""

        items_desc = ""
        for i, task in enumerate(tasks):
            issue_desc = "; ".join([f"{iss.get('type', 'unknown')}" for iss in task.issues])
            max_len_str = str(task.max_length) if task.max_length > 0 else "Unlimited"
            items_desc += f"""
[{i+1}] string_id: {task.string_id}
Source: {task.source_text[:200]}
Current: {task.current_translation[:200]}
Issues: {issue_desc}
Max length: {max_len_str}
"""

        if variant == "standard":
            system = f"""You are a translation repair specialist. Fix the following translation issues.

## Instructions
- Fix each translation to resolve the identified issues
- Preserve ALL placeholders exactly as they appear
- Respect max length constraints
- Maintain original meaning and tone

## Output Format
Return a JSON array with fixed translations:
[
  {{"string_id": "xxx", "fixed_translation": "..."}},
  ...
]
"""
        elif variant == "detailed":
            system = f"""You are an expert translation repair specialist. Previous repair attempts failed.

## Instructions
- Analyze why the issues persist
- Apply more aggressive fixes
- Consider alternative phrasings
- Strictly enforce length limits

## Output Format
Return JSON array:
[{{"string_id": "xxx", "fixed_translation": "..."}}]
"""
        else:  # expert
            system = f"""You are a senior localization expert handling difficult cases.

## Instructions
- These cases failed multiple repair attempts
- Use creative solutions within constraints
- If truly impossible, return "[NEEDS_HUMAN]" as the translation

## Output Format
Return JSON array:
[{{"string_id": "xxx", "fixed_translation": "..."}}]
"""

        user = f"""Fix these {len(tasks)} translations:

{items_desc}

Return ONLY the JSON array with fixed translations:"""

        return {"system": system, "user": user}

    def _parse_batch_result(self, response: str, tasks: List[RepairTask]) -> List[str]:
        """解析批量结果"""
        import re

        # 尝试提取 JSON
        text = response.strip()
        if text.startswith("```"):
            parts = text.split("```")
            if len(parts) >= 2:
                inner = parts[1].strip()
                if inner.startswith("json"):
                    text = inner[4:].strip()
                else:
                    text = inner

        repairs = []
        try:
            data = json.loads(text)
            if isinstance(data, list):
                # 创建 string_id -> translation 映射
                id_to_fix = {str(item.get("string_id", "")): item.get("fixed_translation", "")
                            for item in data}

                # 按任务顺序返回
                for task in tasks:
                    repairs.append(id_to_fix.get(task.string_id, task.current_translation))
        except json.JSONDecodeError:
            # 解析失败，返回原始翻译
            repairs = [task.current_translation for task in tasks]

        # 确保长度匹配
        while len(repairs) < len(tasks):
            repairs.append(tasks[len(repairs)].current_translation)

        return repairs[:len(tasks)]

    def _validate_repair(self, translation: str, task: RepairTask) -> dict:
        """验证修复结果"""
        import re

        if translation.startswith("[NEEDS_HUMAN]"):
            return {"passed": False, "reason": "Marked for human review"}

        validation = {"passed": True, "checks": []}

        # 长度检查
        if task.max_length > 0 and len(translation) > task.max_length:
            validation["passed"] = False
            validation["checks"].append({
                "type": "length",
                "passed": False,
                "detail": f"{len(translation)} > {task.max_length}"
            })

        # 占位符检查
        source_phs = set(re.findall(r'⟦PH_\d+⟧|\{[^}]+\}|%[sd]', task.source_text))
        target_phs = set(re.findall(r'⟦PH_\d+⟧|\{[^}]+\}|%[sd]', translation))
        if source_phs and source_phs != target_phs:
            validation["passed"] = False
            validation["checks"].append({
                "type": "placeholder",
                "passed": False
            })

        # 空检查
        if not translation.strip():
            validation["passed"] = False
            validation["checks"].append({"type": "empty", "passed": False})

        return validation

    def _apply_repair(self, df: pd.DataFrame, task: RepairTask) -> pd.DataFrame:
        """应用修复"""
        idx = df[df["string_id"].astype(str) == task.string_id].index
        if len(idx) > 0:
            target_cols = [c for c in df.columns if 'ru' in c.lower() or 'target' in c.lower()]
            if target_cols:
                df.loc[idx[0], target_cols[0]] = task.final_translation
        return df

    def _print_round_header(self, round_num: int, model: str, pending: int):
        """打印轮次头部 (内部使用)"""
        print("\n" + "=" * 50)
        print(f"Round {round_num}/{self.max_rounds} - Model: {model}")
        print(f"Pending: {pending} tasks, Batch size: {self.batch_size}")
        print("=" * 50)
        sys.stdout.flush()

    def _enrich_tasks_from_df(self, tasks: List[RepairTask], df: pd.DataFrame):
        """从 DataFrame 中补全元数据"""
        # 创建 ID 到行的映射
        id_map = {str(row['string_id']): row for _, row in df.iterrows()}
        
        for task in tasks:
            if task.string_id in id_map:
                row = id_map[task.string_id]
                # 补全 max_length
                if not task.max_length or task.max_length == 0:
                    ml = row.get("max_len_target") or row.get("max_length_target")
                    if ml:
                        try:
                            task.max_length = int(float(ml))
                        except (ValueError, TypeError):
                            pass
                # 补全 source_text (如果任务中缺失)
                if not task.source_text:
                    task.source_text = row.get("tokenized_zh") or row.get("source_zh") or ""

def generate_escalation_report(escalations: List[dict], output_path: str):
    """生成人工审核文档"""
    if not escalations:
        print("✅ No escalations needed")
        return

    df = pd.DataFrame(escalations)

    # 展开字段
    df["issues_summary"] = df["issues"].apply(
        lambda x: "; ".join([f"{i.get('type')}" for i in x]) if x else ""
    )
    df["repair_attempts"] = df["repair_history"].apply(
        lambda x: len([h for h in x if h.get("round") != "escalation"]) if x else 0
    )

    output_cols = [
        "string_id", "source_text", "current_translation",
        "content_type", "max_length_target", "severity",
        "issues_summary", "repair_attempts", "suggested_action"
    ]
    output_cols = [c for c in output_cols if c in df.columns]

    df[output_cols].to_csv(output_path, index=False, encoding='utf-8-sig')
    print(f"📋 Escalation report: {output_path} ({len(escalations)} items)")

def main():
    import argparse

    parser = argparse.ArgumentParser(description="Repair Loop v2.0")
    parser.add_argument("--input", required=True, help="Input CSV")
    parser.add_argument("--tasks", required=True, help="Repair tasks JSONL")
    parser.add_argument("--output", required=True, help="Output CSV")
    parser.add_argument("--output-dir", required=True, help="Output directory")
    parser.add_argument("--qa-type", choices=["hard", "soft"], default="soft")
    parser.add_argument("--config", default="config/repair_config.yaml")

    args = parser.parse_args()

    print(f"\n{'='*60}")
    print(f"Repair Loop v2.0 - {args.qa_type.upper()} QA")
    print(f"{'='*60}")
    sys.stdout.flush()

    config = load_repair_config(args.config)

    df = pd.read_csv(args.input, encoding='utf-8')
    print(f"✅ Loaded {len(df)} rows")

    tasks = []
    try:
        with open(args.tasks, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            
        if not lines:
            print("⚠️ Task file is empty")
        else:
            # Try to parse first line as a standalone JSON object
            try:
                # If there's only one line, it's likely a single JSON object
                if len(lines) == 1:
                    data = json.loads(lines[0])
                    if isinstance(data, dict) and "errors" in data:
                         for err in data["errors"]:
                             tasks.append(RepairTask(err))
                    else:
                        tasks.append(RepairTask(data))
                else:
                    # Try to parse as JSONL first (most common for v2)
                    success = True
                    temp_tasks = []
                    for line in lines:
                        if line.strip():
                            try:
                                temp_tasks.append(RepairTask(json.loads(line)))
                            except json.JSONDecodeError:
                                success = False
                                break
                    
                    if success:
                        tasks = temp_tasks
                    else:
                        # Fallback: try parsing whole file as one JSON
                        data = json.loads("".join(lines))
                        if isinstance(data, dict) and "errors" in data:
                            for err in data["errors"]:
                                tasks.append(RepairTask(err))
                        else:
                            tasks.append(RepairTask(data))
            except Exception as e:
                print(f"❌ Failed to parse tasks file: {e}")
                return
    except Exception as e:
        print(f"❌ Failed to read tasks: {e}")
        return

    print(f"✅ Loaded {len(tasks)} repair tasks")
    sys.stdout.flush()

    if not tasks:
        print("⚠️ No repair tasks")
        df.to_csv(args.output, index=False, encoding='utf-8')
        return

    repair_loop = BatchRepairLoop(config, args.qa_type, args.output_dir)
    repaired_df, escalations = repair_loop.run(tasks, df)

    repaired_df.to_csv(args.output, index=False, encoding='utf-8')
    print(f"✅ Saved: {args.output}")

    if escalations:
        esc_path = os.path.join(args.output_dir, f"escalated_{args.qa_type}_qa.csv")
        generate_escalation_report(escalations, esc_path)

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        import traceback
        with open("crash_repair.log", "w", encoding="utf-8") as f:
            f.write(traceback.format_exc())
        print(f"CRITICAL ERROR: {e}")
        sys.exit(1)
