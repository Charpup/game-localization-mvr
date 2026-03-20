#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
soft_qa_llm.py (v2.2 - Style Profile + Ambiguity checks)
LLM-based soft quality review for translations.

Review dimensions:
  - terminology_consistency
  - style_contract
  - length
  - placeholders
  - ambiguity_high_risk
"""

import argparse
import csv
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Dict, List, Any, Optional

def configure_standard_streams() -> None:
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        if not stream:
            continue
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
            except Exception:
                pass

try:
    import yaml
except Exception:
    yaml = None

from runtime_adapter import (
    LLMClient,
    LLMError,
    BatchConfig,
    get_batch_config,
    batch_llm_call,
    log_llm_progress,
)
from batch_utils import BatchConfig as SplitBatchConfig, split_into_batches

try:
    from glossary_vectorstore import GlossaryVectorStore
    HAS_RAG = True
except Exception:
    HAS_RAG = False

try:
    from semantic_scorer import SemanticScorer
    HAS_SEMANTIC = True
except Exception:
    HAS_SEMANTIC = False

from translate_llm import load_glossary, GlossaryEntry

TOKEN_RE = re.compile(r"⟦(PH_\d+|TAG_\d+)⟧")


def load_text(p: str) -> str:
    with open(p, "r", encoding="utf-8") as f:
        return f.read().strip()


def load_yaml(p: str) -> dict:
    if yaml is None:
        raise RuntimeError("PyYAML required: pip install pyyaml")
    with open(p, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_style_profile(path: str) -> dict:
    if not path or not os.path.exists(path):
        return {}
    return load_yaml(path)


def read_csv(p: str) -> List[Dict[str, str]]:
    with open(p, "r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_json(p: str, obj: Any) -> None:
    Path(p).parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


def append_jsonl(p: str, items: List[dict]) -> None:
    Path(p).parent.mkdir(parents=True, exist_ok=True)
    with open(p, "a", encoding="utf-8") as f:
        for it in items:
            f.write(json.dumps(it, ensure_ascii=False) + "\n")


def token_counts(s: str) -> Dict[str, int]:
    d = {}
    for m in TOKEN_RE.finditer(s or ""):
        d[m.group(1)] = d.get(m.group(1), 0) + 1
    return d


def build_style_contract_block(profile: dict) -> str:
    if not profile:
        return "- style_profile unavailable"
    proj = profile.get("project", {}) or {}
    style = profile.get("style_contract", {}) or {}
    ui = profile.get("ui", {}) or {}
    limits = ui.get("length_constraints", {}) or {}
    guard = style.get("style_guard", {}) or {}
    terms = profile.get("terminology", {}) or {}
    lines = [
        f"- Source/Target: {proj.get('source_language', 'zh-CN')} → {proj.get('target_language', 'ru-RU')}",
        f"- Style policy: over_localization={style.get('language_policy', {}).get('no_over_localization', True)}, over_literal={style.get('language_policy', {}).get('no_over_literal', True)}",
        f"- Placeholder hard protection: {style.get('placeholder_protection', {}).get('preserve_ph_tokens', True)}",
        f"- UI length: button≤{limits.get('button_max_chars', 18)}; dialogue≤{limits.get('dialogue_max_chars', 120)}",
        f"- Character name policy: {guard.get('character_name_policy', 'keep')}",
        f"- Proper noun strategy: {guard.get('proper_noun_strategy', 'hybrid')}",
        f"- Humor restraint: {guard.get('no_humor_overreach', True)}",
    ]
    for t in terms.get("forbidden_terms", [])[:10]:
        lines.append(f"- Forbidden term: {t}")
    return "\n".join(lines)


def build_system_batch(style: str, glossary_summary: str, style_profile: Optional[dict] = None) -> str:
    return (
        "你是手游本地化软质检（zh-CN → ru-RU）。\n\n"
        "任务：分析翻译质量，仅列出有问题的项。\n\n"
        "检查维度（只报问题，不要夸）：\n"
        "- 术语一致性（glossary）\n"
        "- 术语歧义高风险（同一中文术语映射不稳定）\n"
        "- style_contract（禁用语体、角色名策略、变量保护）\n"
        "- UI 长度（按钮/文本上限）\n"
        "- 占位符保护\n"
        "- 标点与符号（中文括号、引号、变量语义）\n\n"
        "输出格式（硬性，仅输出 JSON）：\n"
        "{\n"
        '  "items": [\n'
        "    {\n"
        '      "id": "<id>",\n'
        '      "severity": "minor|major",\n'
        '      "issue_type": "terminology|style_contract|length|placeholder|ambiguity_high_risk|punctuation|mistranslation",\n'
        '      "problem": "<一句话描述问题>",\n'
        '      "suggestion": "<一句话给出修复方向>",\n'
        '      "preferred_fix_ru": "<可选：建议的修复后俄文>"\n'
        "    }\n"
        "  ]\n"
        "}\n"
        "规则：\n"
        "- 没问题则项目不出现在 items 中。\n"
        "- problem/suggestion 为短句。\n"
        "- 每个 id 只输出一条最严重项。\n\n"
        f"术语表摘要（前 50 条）：\n{glossary_summary[:1500]}\n\n"
        f"style_guide（节选）：\n{style[:1000]}\n"
        f"style_contract：\n{build_style_contract_block(style_profile or {})}\n"
    )


def build_user_prompt(items: List[Dict]) -> str:
    return json.dumps(items, ensure_ascii=False, indent=2)


def build_glossary_summary(entries: List[GlossaryEntry], max_entries: int = 50) -> str:
    approved = [e for e in entries if e.status.lower() == "approved"][:max_entries]
    if not approved:
        return "(无)"
    return "\n".join([f"- {e.term_zh} → {e.term_ru}" for e in approved])


def preflight_tasks(rows: List[Dict[str, str]], style_profile: dict, glossary_entries: List[GlossaryEntry]) -> List[dict]:
    tasks: List[dict] = []
    seen = set()
    style_profile = style_profile or {}
    ui = style_profile.get("ui", {}) or {}
    limits = ui.get("length_constraints", {}) or {}
    btn_max = int(limits.get("button_max_chars", 18))
    dlg_max = int(limits.get("dialogue_max_chars", 120))
    forbidden = set([str(t).strip() for t in style_profile.get("terminology", {}).get("forbidden_terms", []) if str(t).strip()])
    preferred = style_profile.get("terminology", {}).get("preferred_terms", []) or []
    preferred_map = {str(p.get("term_zh", "")).strip(): str(p.get("term_ru", "")).strip() for p in preferred if isinstance(p, dict)}

    glossary_map = {}
    for e in glossary_entries:
        if e.status == "approved" and e.term_zh:
            glossary_map[e.term_zh] = e.term_ru

    for r in rows:
        sid = str(r.get("string_id") or r.get("id") or "")
        if not sid:
            continue

        src = r.get("source_zh") or r.get("tokenized_zh") or ""
        tgt = r.get("target_text") or ""
        module = (r.get("module_tag") or "").strip().lower()
        max_len = r.get("max_length_target") or r.get("max_len_target")
        if max_len:
            try:
                ml = int(max_len)
                if ml > 0 and len(tgt) > ml:
                    tasks.append({"string_id": sid, "type": "length", "severity": "major", "note": "target length exceeds limit", "problem": "长度超限", "suggestion": "缩短翻译", "suggested_fix": tgt})
                    seen.add((sid, "length"))
            except Exception:
                pass
        else:
            limit = btn_max if module in {"ui_button", "button", "tab"} else dlg_max
            if limit and len(tgt) > limit:
                tasks.append({"string_id": sid, "type": "length", "severity": "minor", "note": f"target length > {limit}", "problem": "疑似长度过长", "suggestion": "压缩文本", "suggested_fix": tgt})
                seen.add((sid, "length"))

        if token_counts(src) != token_counts(tgt):
            key = (sid, "placeholder")
            if key not in seen:
                tasks.append({"string_id": sid, "type": "placeholder", "severity": "major", "note": "token_count_mismatch", "problem": "占位符保护失败", "suggestion": "保持 token 数一致", "suggested_fix": tgt})
                seen.add(key)

        for t in forbidden:
            if t and t in src and t in tgt:
                key = (sid, "forbidden")
                if key not in seen:
                    tasks.append({"string_id": sid, "type": "style_contract", "severity": "major", "note": f"forbidden term {t}", "problem": "命中禁译项", "suggestion": "使用替代术语", "suggested_fix": tgt})
                    seen.add(key)

        for zh, ru in glossary_map.items():
            if zh in src and ru and ru not in tgt:
                if (sid, "term") not in seen:
                    tasks.append({"string_id": sid, "type": "terminology", "severity": "minor", "note": f"missing glossary term {zh}->{ru}", "problem": "疑似术语未按既定译法出现", "suggestion": f"优先使用 {ru}", "suggested_fix": tgt})
                    seen.add((sid, "term"))

        for zh, ru in preferred_map.items():
            if zh and ru and zh in src and ru not in tgt and (sid, "style_pref") not in seen:
                tasks.append({"string_id": sid, "type": "style_contract", "severity": "minor", "note": f"preferred form mismatch for {zh}", "problem": "与风格偏好译法不一致", "suggestion": f"优先使用 {ru}", "suggested_fix": tgt})
                seen.add((sid, "style_pref"))

    return tasks


def process_batch_results(batch_items: List[Dict]) -> List[dict]:
    valid_tasks = []
    for t in batch_items:
        sid = t.get("id", "").strip()
        if not sid:
            continue
        issue_type = str(t.get("issue_type", "issue")).strip()
        valid_tasks.append({
            "string_id": sid,
            "type": issue_type,
            "severity": t.get("severity", "minor"),
            "note": f"{t.get('problem', '')} | Suggestion: {t.get('suggestion', '')}",
            "suggested_fix": t.get("preferred_fix_ru", ""),
        })
    return valid_tasks


def merge_tasks(pref: List[dict], llm_tasks: List[dict], cap_per_row: int = 1) -> List[dict]:
    merged = []
    seen = set()
    for task in pref + llm_tasks:
        sid = task.get("string_id") or task.get("id")
        typ = task.get("type") or task.get("issue_type")
        if not sid:
            continue
        key = (str(sid), typ)
        if key in seen:
            continue
        seen.add(key)
        if sum(1 for x in merged if x.get("string_id") == sid) >= cap_per_row:
            continue
        merged.append(task)
    return merged


def main():
    configure_standard_streams()
    ap = argparse.ArgumentParser(description="LLM-based soft QA (Batch Mode v2.2)")
    ap.add_argument("translated_csv", nargs="?", help="Input translated.csv")
    ap.add_argument("--input", help="Alias for translated_csv")
    ap.add_argument("style_guide_md", nargs="?", default="workflow/style_guide.md", help="Style guide file")
    ap.add_argument("glossary_yaml", nargs="?", default="data/glossary.yaml", help="Glossary file")
    ap.add_argument("rubric_yaml", nargs="?", default="workflow/soft_qa_rubric.yaml", help="rubric config")
    ap.add_argument("--style-profile", default="data/style_profile.yaml", help="Style profile")
    ap.add_argument("--batch_size", type=int, default=15)
    ap.add_argument("--model", default="claude-haiku-4-5-20251001")
    ap.add_argument("--max_batch_tokens", type=int, default=4000)
    ap.add_argument("--out_report", default="data/qa_soft_report.json")
    ap.add_argument("--out_tasks", default="data/repair_tasks.jsonl")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--enable-rag", action="store_true")
    ap.add_argument("--enable-semantic", action="store_true")
    ap.add_argument("--rag-top-k", type=int, default=15)
    ap.add_argument("--resume", action="store_true")
    args = ap.parse_args()

    input_path = args.input or args.translated_csv
    if not input_path:
        ap.print_help()
        return 1

    print(f"🔍 Soft QA v2.2 (Batch Mode + Style Profile)")
    use_rag = args.enable_rag and HAS_RAG
    use_semantic = args.enable_semantic and HAS_SEMANTIC

    if args.enable_rag and not HAS_RAG:
        print("⚠️  RAG requested but glossary_vectorstore not available")
    if args.enable_semantic and not HAS_SEMANTIC:
        print("⚠️  Semantic requested but semantic_scorer not available")

    rows = read_csv(input_path)
    style = load_text(args.style_guide_md)
    style_profile = load_style_profile(args.style_profile)

    glossary_entries = []
    if args.glossary_yaml and Path(args.glossary_yaml).exists():
        glossary_entries, _ = load_glossary(args.glossary_yaml)
    glossary_summary = build_glossary_summary(glossary_entries)

    rows_with_target = [r for r in rows if r.get("target_text")]
    print(f"✅ Loaded {len(rows)} rows, target rows {len(rows_with_target)}")

    pre_tasks = preflight_tasks(rows_with_target, style_profile, glossary_entries)

    if args.dry_run:
        print("⚙️  dry-run mode")
        report = {
            "version": "2.2",
            "mode": "batch",
            "has_findings": bool(pre_tasks),
            "summary": {"major": 0, "minor": 0, "total_tasks": len(pre_tasks)},
            "outputs": {"repair_tasks_jsonl": args.out_tasks},
            "metadata": {"generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"), "dry_run": True},
        }
        if pre_tasks:
            for t in pre_tasks:
                t["severity"] = t.get("severity", "minor")
            major = sum(1 for x in pre_tasks if x.get("severity") == "major")
            report["summary"]["major"] = major
            report["summary"]["minor"] = len(pre_tasks) - major
            append_jsonl(args.out_tasks, pre_tasks)
        write_json(args.out_report, report)
        print("✅ Dry-run complete.")
        return 0

    llm = LLMClient()
    start_time = time.time()
    major = 0
    minor = 0

    batch_rows = []
    for r in rows_with_target:
        src = r.get("source_zh") or r.get("tokenized_zh") or ""
        tgt = r.get("target_text") or ""
        batch_rows.append({"id": r.get("string_id"), "source_text": f"SRC: {src} | TGT: {tgt}"})

    try:
        batch_results = batch_llm_call(
            step="soft_qa",
            rows=batch_rows,
            model=args.model,
            system_prompt=build_system_batch(style, glossary_summary, style_profile=style_profile),
            user_prompt_template=build_user_prompt,
            content_type="normal",
            retry=1,
            allow_fallback=True,
            partial_match=True,
            output_dir=str(Path(args.out_report).parent),
        )
        llm_tasks = process_batch_results(batch_results)
    except Exception as e:
        print(f"❌ Soft QA failed: {e}")
        return 1

    all_tasks = merge_tasks(pre_tasks, llm_tasks)
    if all_tasks:
        append_jsonl(args.out_tasks, all_tasks)
        major = sum(1 for t in all_tasks if t.get("severity") == "major")
        minor = len(all_tasks) - major

    elapsed = int(time.time() - start_time)
    report = {
        "version": "2.2",
        "mode": "batch",
        "has_findings": bool(all_tasks),
        "summary": {
            "major": major,
            "minor": minor,
            "total_tasks": len(all_tasks),
            "rows_processed": len(rows_with_target),
            "runtime_seconds": elapsed,
            "preflight_tasks": len(pre_tasks),
        },
        "outputs": {"repair_tasks_jsonl": args.out_tasks},
        "metadata": {"generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"), "rubric_profile_version": (style_profile.get("version") or "")},
    }
    write_json(args.out_report, report)

    print(f"📊 Soft QA Summary: rows={len(rows_with_target)} major={major} minor={minor} total={len(all_tasks)}")
    if all_tasks:
        print(f"✅ Report: {args.out_report}")
        print(f"✅ Tasks: {args.out_tasks}")
    return 0


if __name__ == "__main__":
    exit(main())
