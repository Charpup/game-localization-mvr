#!/usr/bin/env python3
"""
Repair Loop (v2.0) - 多轮修复 + Fallback Models + Escalation

Features:
- 最多 3 轮修复尝试
- 每轮使用不同模型/策略
- 修复失败后自动 escalate 到人工审核
- 生成详细的修复历史记录
"""

import os
import sys
import json
import re
import yaml
import pandas as pd
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Tuple

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Ensure UTF-8 output on Windows consoles before any status glyphs are printed.
if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
if sys.platform == "win32" and hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)

# 确保 unbuffered 输出
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True)


QA_TYPE_TO_STEP = {
    "hard": "repair_hard",
    "soft": "repair_soft_major",
}

CJK_RE = re.compile(r"[\u4e00-\u9fff]")
META_RESPONSE_RE = re.compile(
    r"(?:i'm ready to help|please provide|once you (?:share|provide)|source text and current translation are empty)",
    re.IGNORECASE,
)
FROZEN_TOKEN_RE = re.compile(r"⟦[A-Z]+_\d+⟧")


def _task_key(value: object) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except Exception:
        pass
    return str(value).strip()


def _first_present(row: Dict[str, object], candidates: List[str]) -> str:
    for key in candidates:
        value = row.get(key)
        if value is None:
            continue
        try:
            if pd.isna(value):
                continue
        except Exception:
            pass
        text = str(value).strip()
        if text:
            return text
    return ""


def _target_value_columns(columns: List[str]) -> List[str]:
    result: List[str] = []
    excluded_exact = {
        "target_locale",
        "target_lang",
        "target_language",
        "target_key",
        "target_column",
    }
    for column in columns:
        lower = column.lower()
        if lower in {"target", "target_text", "translated_text"} or lower.startswith("target_"):
            if "length" in lower or lower.startswith("max_"):
                continue
            if lower in excluded_exact or lower.endswith("_locale") or lower.endswith("_language"):
                continue
            result.append(column)
    return result


def hydrate_task_from_frame(task: "RepairTask", data_df: pd.DataFrame) -> None:
    if "string_id" not in data_df.columns:
        return

    key = _task_key(task.string_id)
    if not key:
        return

    matches = data_df[data_df["string_id"].astype(str).str.strip() == key]
    if matches.empty:
        return

    row = matches.iloc[0].to_dict()
    target_columns = _target_value_columns(list(data_df.columns))

    if not task.source_text:
        task.source_text = _first_present(row, ["tokenized_zh", "source_zh", "source_text", "source"])
    if not task.current_translation:
        task.current_translation = _first_present(row, [*target_columns, "current_translation", "target"])
    if not task.max_length:
        task.max_length = row.get("max_length_target") or row.get("max_len_target") or 0
    if not task.content_type:
        task.content_type = _first_present(row, ["content_type", "content_class"])


def _extract_frozen_tokens(text: str) -> List[str]:
    return FROZEN_TOKEN_RE.findall(text or "")


def repair_step_for_qa_type(qa_type: str) -> str:
    """Map CLI qa_type values to runtime routing steps."""
    return QA_TYPE_TO_STEP.get(qa_type, f"repair_{qa_type}")

def load_repair_config(path: str = "config/repair_config.yaml") -> dict:
    """加载修复配置"""
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f) or {}
    return {
        "repair_loop": {
            "max_rounds": 3,
            "rounds": {
                1: {"model": "claude-haiku-4-5-20251001", "prompt_variant": "standard"},
                2: {"model": "claude-haiku-4-5-20251001", "prompt_variant": "detailed"},
                3: {"model": "claude-sonnet-4-5-20250929", "prompt_variant": "expert"}
            }
        }
    }

class RepairTask:
    """单个修复任务"""
    def __init__(self, task_data: dict):
        self.string_id = task_data.get("string_id")
        self.source_text = task_data.get("source_text", "")
        self.current_translation = task_data.get("current_translation", "")
        self.issues = task_data.get("issues", [])
        self.severity = task_data.get("severity", "major")
        self.max_length = task_data.get("max_length_target", 0)
        self.content_type = task_data.get("content_type", "")

        self.repair_history = []
        self.status = "pending"  # pending, repaired, escalated
        self.final_translation = None

    def add_repair_attempt(self, round_num: int, model: str, result: dict):
        """记录修复尝试"""
        self.repair_history.append({
            "round": round_num,
            "model": model,
            "timestamp": datetime.now().isoformat(),
            "attempted_fix": result.get("translation", ""),
            "validation_result": result.get("validation", {}),
            "success": result.get("success", False)
        })

        if result.get("success"):
            self.status = "repaired"
            self.final_translation = result.get("translation")

    def escalate(self, reason: str):
        """标记为需要人工处理"""
        self.status = "escalated"
        self.repair_history.append({
            "round": "escalation",
            "timestamp": datetime.now().isoformat(),
            "reason": reason
        })

    def to_escalation_record(self) -> dict:
        """生成 escalation 记录"""
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
        """生成人工处理建议"""
        issue_types = [i.get("type", "") for i in self.issues]

        if "placeholder_mismatch" in issue_types:
            return "检查并修复占位符，确保源文本和译文占位符数量及顺序一致"
        elif "length_overflow" in issue_types:
            return "缩短译文，建议使用更简洁的表达或省略非关键词汇"
        elif "glossary_violation" in issue_types:
            return "检查术语使用，参考术语表修正专有名词翻译"
        elif "meaning_reversal" in issue_types:
            return "重新翻译，当前译文含义与原文相反或严重偏离"
        else:
            return "人工审核并根据上下文优化翻译质量"

class RepairLoop:
    """多轮修复引擎"""

    def __init__(self, config: dict, qa_type: str = "soft", target_lang: str = "ru-RU"):
        self.config = config.get("repair_loop", {})
        self.max_rounds = self.config.get("max_rounds", 3)
        self.rounds_config = self.config.get("rounds", {})
        self.qa_type = qa_type
        self.route_step = repair_step_for_qa_type(qa_type)
        self.target_lang = target_lang or "ru-RU"

        # 统计
        self.stats = {
            "total_tasks": 0,
            "repaired": 0,
            "escalated": 0,
            "by_round": {1: 0, 2: 0, 3: 0}
        }

    def run(self, tasks: List[RepairTask], data_df: pd.DataFrame,
            output_dir: str) -> Tuple[pd.DataFrame, List[dict]]:
        """
        执行多轮修复

        Returns:
            Tuple[pd.DataFrame, List[dict]]: (修复后的数据, escalation 记录)
        """
        from scripts.runtime_adapter import LLMClient, log_llm_progress

        self.stats["total_tasks"] = len(tasks)
        escalations = []

        print(f"🔧 Starting Repair Loop ({self.qa_type})")
        print(f"   Total tasks: {len(tasks)}")
        print(f"   Max rounds: {self.max_rounds}")
        sys.stdout.flush()

        os.makedirs(output_dir, exist_ok=True)

        # 写入心跳文件
        self._write_heartbeat(output_dir, "starting")

        for round_num in range(1, self.max_rounds + 1):
            # 获取当前轮次待修复任务
            pending_tasks = [t for t in tasks if t.status == "pending"]

            if not pending_tasks:
                print(f"✅ All tasks repaired by round {round_num - 1}")
                break

            round_config = self.rounds_config.get(round_num, self.rounds_config.get(1, {}))
            model = round_config.get("model", "claude-haiku-4-5-20251001")
            prompt_variant = round_config.get("prompt_variant", "standard")

            print(f"\n--- Round {round_num}/{self.max_rounds} ---")
            print(f"   Model: {model}")
            print(f"   Pending: {len(pending_tasks)} tasks")
            sys.stdout.flush()

            # 写入检查点
            self._write_checkpoint(output_dir, round_num, len(pending_tasks))

            # 执行修复
            client = LLMClient()

            for i, task in enumerate(pending_tasks):
                # 更新心跳
                if i % 10 == 0:
                    self._write_heartbeat(output_dir, f"round_{round_num}_task_{i}")

                # 构建修复 prompt
                prompt = self._build_repair_prompt(task, prompt_variant)

                try:
                    result = client.chat(
                        system=prompt["system"],
                        user=prompt["user"],
                        metadata={"step": self.route_step, "round": round_num, "qa_type": self.qa_type}
                    )

                    # 解析结果
                    repair_result = self._parse_repair_result(result.text, task)

                    # 验证修复结果
                    validation = self._validate_repair(repair_result, task)
                    repair_result["validation"] = validation
                    repair_result["success"] = validation.get("passed", False)

                    # 记录尝试
                    task.add_repair_attempt(round_num, model, repair_result)

                    if repair_result["success"]:
                        self.stats["repaired"] += 1
                        self.stats["by_round"][round_num] += 1

                        # 更新 DataFrame
                        data_df = self._apply_repair(data_df, task)

                except Exception as e:
                    task.add_repair_attempt(round_num, model, {
                        "success": False,
                        "error": str(e)
                    })

            print(f"   Repaired this round: {self.stats['by_round'][round_num]}")
            sys.stdout.flush()

        # 处理仍未修复的任务 -> Escalate
        for task in tasks:
            if task.status == "pending":
                task.escalate(f"Failed after {self.max_rounds} repair rounds")
                escalations.append(task.to_escalation_record())
                self.stats["escalated"] += 1

        # 写入完成标记
        self._write_done(output_dir)

        # 打印统计
        print(f"\n📊 Repair Loop Summary:")
        print(f"   Total: {self.stats['total_tasks']}")
        print(f"   Repaired: {self.stats['repaired']}")
        print(f"   Escalated: {self.stats['escalated']}")
        print(f"   By round: {self.stats['by_round']}")
        sys.stdout.flush()

        return data_df, escalations

    def _build_repair_prompt(self, task: RepairTask, variant: str) -> dict:
        """构建修复 prompt"""

        issue_desc = "\n".join([
            f"- {i.get('type', 'unknown')}: {i.get('detail', '')}"
            for i in task.issues
        ])
        frozen_token_sequence = _extract_frozen_tokens(task.source_text)
        frozen_token_hint = ""
        if frozen_token_sequence:
            frozen_token_hint = (
                "\n- Preserve the exact frozen token sequence from source, including duplicates and order:\n"
                f"  {' '.join(frozen_token_sequence)}"
            )

        if variant == "standard":
            system = f"""You are a translation repair specialist. Fix the following translation issues.

## Issues Found
{issue_desc}

## Constraints
- Target language: {self.target_lang}
- Max length: {task.max_length} characters (if specified)
- Preserve all placeholders exactly as they appear in source
- Preserve all frozen tag/placeholder tokens exactly, including duplicates and order{frozen_token_hint}
- Translate bracketed gameplay/status text such as [沉默]; keep the brackets, but translate the text inside them unless it is a frozen token.
- Maintain the original tone and style

## Output
Return ONLY the corrected translation, nothing else."""

        elif variant == "detailed":
            system = f"""You are an expert translation repair specialist. The previous repair attempt failed.

## Original Issues
{issue_desc}

## Previous Attempts
{json.dumps(task.repair_history, indent=2, ensure_ascii=False)}

## Constraints
- Target language: {self.target_lang}
- Max length: {task.max_length} characters (STRICT)
- ALL placeholders must be preserved exactly
- ALL frozen tag/placeholder tokens must preserve exact duplicates and order{frozen_token_hint}
- Bracketed gameplay/status text like [沉默] must be translated, not copied through unchanged.
- Meaning must match the source text

## Instructions
1. Analyze why previous repairs failed
2. Apply a different approach
3. Verify constraints before outputting

Return ONLY the corrected translation."""

        else:  # expert
            system = f"""You are a senior localization expert handling a difficult repair case.

## Source Text
{task.source_text}

## Current Translation (Problematic)
{task.current_translation}

## Issues
{issue_desc}

## Failed Repair History
{json.dumps(task.repair_history, indent=2, ensure_ascii=False)}

## Strict Constraints
- Target language: {self.target_lang}
- Max length: {task.max_length} chars
- Placeholders: Must match source exactly
- Frozen tag/token sequence: Must match source exactly, including duplicates and order{frozen_token_hint}
- Bracketed gameplay/status text like [沉默] must stay bracketed but the inner text must be translated into {self.target_lang}.
- Quality: Professional game localization standard

## Your Task
Provide a definitive fix. If impossible within constraints, indicate "[NEEDS_HUMAN]" at the start.

Return ONLY the corrected translation (or [NEEDS_HUMAN] + explanation)."""

        user = f"""Target language: {self.target_lang}
Source: {task.source_text}
Current translation: {task.current_translation}

Fix the issues and return the corrected translation:"""

        return {"system": system, "user": user}

    def _parse_repair_result(self, response_text: str, task: RepairTask) -> dict:
        """解析修复结果"""
        text = response_text.strip()

        # 检查是否标记为需要人工
        if text.startswith("[NEEDS_HUMAN]"):
            return {
                "translation": task.current_translation,
                "needs_human": True,
                "reason": text[13:].strip()
            }

        return {
            "translation": text,
            "needs_human": False
        }

    def _validate_repair(self, repair_result: dict, task: RepairTask) -> dict:
        """验证修复结果"""
        if repair_result.get("needs_human"):
            return {"passed": False, "reason": "Marked for human review"}

        translation = repair_result.get("translation", "")
        validation = {"passed": True, "checks": []}
        issue_types = {str(issue.get("type", "")).strip() for issue in task.issues if isinstance(issue, dict)}

        # 检查长度
        if task.max_length > 0 and len(translation) > task.max_length:
            validation["passed"] = False
            validation["checks"].append({
                "type": "length",
                "passed": False,
                "detail": f"{len(translation)} > {task.max_length}"
            })

        # 检查占位符
        source_phs = self._extract_placeholders(task.source_text)
        target_phs = self._extract_placeholders(translation)
        if source_phs != target_phs:
            validation["passed"] = False
            validation["checks"].append({
                "type": "placeholder",
                "passed": False,
                "detail": f"Source: {source_phs}, Target: {target_phs}"
            })

        source_frozen_tokens = _extract_frozen_tokens(task.source_text)
        target_frozen_tokens = _extract_frozen_tokens(translation)
        if source_frozen_tokens != target_frozen_tokens:
            validation["passed"] = False
            validation["checks"].append({
                "type": "frozen_token_sequence",
                "passed": False,
                "detail": f"Source: {source_frozen_tokens}, Target: {target_frozen_tokens}"
            })

        # 检查是否为空
        if not translation.strip():
            validation["passed"] = False
            validation["checks"].append({
                "type": "empty",
                "passed": False,
                "detail": "Translation is empty"
            })

        if META_RESPONSE_RE.search(translation):
            validation["passed"] = False
            validation["checks"].append({
                "type": "meta_response",
                "passed": False,
                "detail": "LLM returned a request-for-input/meta response instead of a translation"
            })

        if ("forbidden_hit" in issue_types or CJK_RE.search(task.current_translation or "")) and CJK_RE.search(translation):
            validation["passed"] = False
            validation["checks"].append({
                "type": "cjk_remaining",
                "passed": False,
                "detail": "Translation still contains CJK characters after repair"
            })

        return validation

    def _extract_placeholders(self, text: str) -> set:
        """提取占位符"""
        import re
        patterns = [
            r'⟦PH_\d+⟧',
            r'\{[^}]+\}',
            r'%[sd]',
            r'<[^>]+>'
        ]
        placeholders = set()
        for pattern in patterns:
            placeholders.update(re.findall(pattern, text))
        return placeholders

    def _apply_repair(self, df: pd.DataFrame, task: RepairTask) -> pd.DataFrame:
        """应用修复到 DataFrame"""
        if "string_id" not in df.columns:
            return df
        idx = df[df["string_id"].astype(str).str.strip() == _task_key(task.string_id)].index
        if len(idx) > 0:
            target_columns = _target_value_columns(list(df.columns))
            for column in target_columns:
                df.loc[idx[0], column] = task.final_translation
        return df

    def _write_checkpoint(self, output_dir: str, round_num: int, pending: int):
        """写入检查点"""
        checkpoint = {
            "timestamp": datetime.now().isoformat(),
            "round": round_num,
            "pending_tasks": pending,
            "stats": self.stats
        }
        path = os.path.join(output_dir, "repair_checkpoint.json")
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(checkpoint, f, indent=2)

    def _write_heartbeat(self, output_dir: str, status: str):
        """写入心跳文件"""
        path = os.path.join(output_dir, "repair_heartbeat.txt")
        with open(path, 'w') as f:
            f.write(f"{datetime.now().isoformat()} | {status}\n")

    def _write_done(self, output_dir: str):
        """写入完成标记"""
        path = os.path.join(output_dir, "repair_DONE")
        with open(path, 'w') as f:
            f.write(f"Completed at {datetime.now().isoformat()}\n")
            f.write(f"Stats: {json.dumps(self.stats)}\n")

def generate_escalation_report(escalations: List[dict], output_path: str):
    """生成人工审核文档"""

    if not escalations:
        print("✅ No escalations needed")
        return

    # CSV 格式 (方便人工处理)
    df = pd.DataFrame(escalations)

    # 展开嵌套字段
    df["issues_summary"] = df["issues"].apply(
        lambda x: "; ".join([f"{i.get('type')}: {i.get('detail', '')}" for i in x]) if x else ""
    )
    df["repair_attempts"] = df["repair_history"].apply(
        lambda x: len([h for h in x if h.get("round") != "escalation"]) if x else 0
    )
    df["last_attempted_fix"] = df["repair_history"].apply(
        lambda x: x[-2].get("attempted_fix", "") if len(x) >= 2 else ""
    )

    # 选择输出列
    output_cols = [
        "string_id",
        "source_text",
        "current_translation",
        "last_attempted_fix",
        "content_type",
        "max_length_target",
        "severity",
        "issues_summary",
        "repair_attempts",
        "suggested_action"
    ]

    # 筛选存在的列
    output_cols = [c for c in output_cols if c in df.columns]

    df[output_cols].to_csv(output_path, index=False, encoding='utf-8-sig')
    print(f"📋 Escalation report generated: {output_path}")
    print(f"   Total escalated: {len(escalations)}")

def build_parser():
    import argparse

    parser = argparse.ArgumentParser(description="Repair Loop v2.0 (flags-only CLI)")
    parser.add_argument("--input", required=True, help="Input CSV with translations")
    parser.add_argument(
        "--tasks",
        required=True,
        help="Repair work items: qa_hard report JSON or soft QA JSONL",
    )
    parser.add_argument("--output", required=True, help="Output repaired CSV")
    parser.add_argument(
        "--output-dir",
        required=True,
        help="Directory for repair artifacts (checkpoint snapshot, heartbeat, stats, escalation CSV)",
    )
    parser.add_argument(
        "--qa-type",
        choices=["hard", "soft"],
        default="soft",
        help="Repair mode: hard -> repair_hard, soft -> repair_soft_major",
    )
    parser.add_argument("--target-lang", default="ru-RU", help="Target language for repair output prompts")
    parser.add_argument("--config", default="config/repair_config.yaml")
    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()
    os.makedirs(args.output_dir, exist_ok=True)

    # 加载配置
    config = load_repair_config(args.config)

    # 加载数据
    df = pd.read_csv(args.input, encoding='utf-8')
    print(f"✅ Loaded {len(df)} rows from {args.input}")

    # 加载修复任务
    tasks = []
    try:
        with open(args.tasks, 'r', encoding='utf-8') as f:
            content = f.read().strip()
            data = None
            if content.startswith('{'):
                try:
                    data = json.loads(content)
                except json.JSONDecodeError:
                    data = None
            if isinstance(data, dict):
                if "errors" in data:
                    # Standard QA report format
                    for err in data["errors"]:
                        # Map 'source' to 'source_text' if needed
                        if "source" in err and "source_text" not in err:
                            err["source_text"] = err["source"]
                        if "target" in err and "current_translation" not in err:
                            err["current_translation"] = err["target"]
                        tasks.append(RepairTask(err))
                else:
                    # Maybe single object?
                    if "target" in data and "current_translation" not in data:
                        data["current_translation"] = data["target"]
                    tasks.append(RepairTask(data))
            else:
                # JSONL Format
                for line in content.splitlines():
                    if line.strip():
                        t = json.loads(line)
                        if "source" in t and "source_text" not in t:
                             t["source_text"] = t["source"]
                        if "target" in t and "current_translation" not in t:
                            t["current_translation"] = t["target"]
                        tasks.append(RepairTask(t))
    except Exception as e:
        print(f"❌ Failed to load tasks: {e}")
        return

    print(f"✅ Loaded {len(tasks)} repair tasks")

    if not tasks:
        print("⚠️ No repair tasks, copying input to output")
        df.to_csv(args.output, index=False, encoding='utf-8')
        return

    for task in tasks:
        hydrate_task_from_frame(task, df)

    # 执行修复
    repair_loop = RepairLoop(config, args.qa_type, target_lang=args.target_lang)
    repaired_df, escalations = repair_loop.run(tasks, df, args.output_dir)

    # 保存修复后的数据
    repaired_df.to_csv(args.output, index=False, encoding='utf-8')
    print(f"✅ Repaired data saved to {args.output}")

    # 生成 escalation 报告
    if escalations:
        escalation_path = os.path.join(
            args.output_dir,
            f"escalated_{args.qa_type}_qa.csv"
        )
        generate_escalation_report(escalations, escalation_path)

    # 保存修复统计
    stats_path = os.path.join(args.output_dir, f"repair_{args.qa_type}_stats.json")
    with open(stats_path, 'w', encoding='utf-8') as f:
        json.dump(repair_loop.stats, f, indent=2)

if __name__ == "__main__":
    main()
