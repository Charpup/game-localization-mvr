#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
soft_qa_llm.py (v2.0 - Batch Mode)
LLM-based soft quality review for translations.

Purpose:
  Soft QA 的价值不是"打分"，而是输出可执行的 repair tasks，让 repair loop 能自动修。
  评审维度：style_officialness, anime_tone, terminology_consistency, ui_brevity, ambiguity

  BATCH processing: multiple items per LLM call to reduce prompt token waste.

Usage:
  python scripts/soft_qa_llm.py \\
    data/translated.csv workflow/style_guide.md data/glossary.yaml workflow/soft_qa_rubric.yaml \\
    --batch_size 15 --out_report data/qa_soft_report.json --out_tasks data/repair_tasks.jsonl

Environment:
  LLM_BASE_URL, LLM_API_KEY, LLM_MODEL (via runtime_adapter)
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

# 强制 unbuffered 与 UTF-8 输出 (兼容 Windows)
for stream in [sys.stdout, sys.stderr]:
    if stream:
        if hasattr(stream, 'reconfigure'):
            try:
                stream.reconfigure(encoding='utf-8', errors='replace', line_buffering=True)
            except Exception:
                pass # Fallback if reconfigure fails on certain streams

try:
    import yaml
except Exception:
    yaml = None

try:
    from scripts.runtime_adapter import LLMClient, LLMError, BatchConfig, get_batch_config, batch_llm_call, log_llm_progress
except ImportError:
    from runtime_adapter import LLMClient, LLMError, BatchConfig, get_batch_config, batch_llm_call, log_llm_progress

# v2.1: RAG and Semantic Scoring integration
try:
    from glossary_vectorstore import GlossaryVectorStore
    HAS_RAG = True
except ImportError:
    HAS_RAG = False

try:
    from semantic_scorer import SemanticScorer
    HAS_SEMANTIC = True
except ImportError:
    HAS_SEMANTIC = False

TOKEN_RE = re.compile(r"⟦(PH_\d+|TAG_\d+)⟧")


def load_text(p: str) -> str:
    """Load text file content."""
    with open(p, "r", encoding="utf-8") as f:
        return f.read().strip()


def load_yaml(p: str) -> dict:
    """Load YAML file."""
    if yaml is None:
        raise RuntimeError("PyYAML required: pip install pyyaml")
    with open(p, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_qa_config(target_lang: str) -> dict:
    """Load QA rules from config based on target language.
    
    Args:
        target_lang: Target language code (e.g., 'ru-RU', 'en-US')
    
    Returns:
        Dict with QA rules for the language
    """
    lang_code = target_lang.split('-')[0]
    config_file = Path(__file__).parent.parent / 'config' / 'qa_rules' / f"{lang_code}.yaml"
    if config_file.exists():
        with open(config_file, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f) or {}
    return {}


def read_csv(p: str) -> List[Dict[str, str]]:
    """Read CSV file as list of dicts."""
    with open(p, "r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_json(p: str, obj: Any) -> None:
    """Write JSON file."""
    Path(p).parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


def append_jsonl(p: str, items: List[dict]) -> None:
    """Append items to JSONL file."""
    Path(p).parent.mkdir(parents=True, exist_ok=True)
    with open(p, "a", encoding="utf-8") as f:
        for it in items:
            f.write(json.dumps(it, ensure_ascii=False) + "\n")


def token_counts(s: str) -> Dict[str, int]:
    """Count tokens in string."""
    d = {}
    for m in TOKEN_RE.finditer(s or ""):
        k = m.group(1)
        d[k] = d.get(k, 0) + 1
    return d


# Import glossary logic from translate_llm (lazy import to avoid sys.exit on import errors)
_load_glossary = None
_build_glossary_constraints = None
_GlossaryEntry = None

def _import_translate_llm():
    """Lazy import translate_llm to avoid blocking pytest on ImportError."""
    global _load_glossary, _build_glossary_constraints, _GlossaryEntry
    if _load_glossary is None:
        try:
            from scripts.translate_llm import load_glossary, build_glossary_constraints, GlossaryEntry
        except ImportError:
            from translate_llm import load_glossary, build_glossary_constraints, GlossaryEntry
        _load_glossary = load_glossary
        _build_glossary_constraints = build_glossary_constraints
        _GlossaryEntry = GlossaryEntry
    return _load_glossary, _build_glossary_constraints, _GlossaryEntry


def load_glossary(path: str):
    """Load glossary from YAML file (wrapper with lazy import)."""
    load_fn, _, _ = _import_translate_llm()
    return load_fn(path)


def build_glossary_constraints(glossary: list, source_zh: str) -> dict:
    """Build glossary constraints (wrapper with lazy import)."""
    _, build_fn, _ = _import_translate_llm()
    return build_fn(glossary, source_zh)


class GlossaryEntry:
    """Proxy for translate_llm.GlossaryEntry with lazy import."""
    
    def __init__(self, term_zh: str, term_ru: str, status: str, notes: str = ""):
        self.term_zh = term_zh
        self.term_ru = term_ru
        self.status = status
        self.notes = notes
    
    @classmethod
    def _get_real_class(cls):
        _, _, entry_class = _import_translate_llm()
        return entry_class


def build_system_batch(style: str, glossary_summary: str, source_lang: str = "zh-CN", target_lang: str = "ru-RU") -> str:
    """Build system prompt for batch soft QA with dynamic language support.
    
    Args:
        style: Style guide content
        glossary_summary: Compact glossary summary
        source_lang: Source language code (default: zh-CN)
        target_lang: Target language code (default: ru-RU)
    
    Returns:
        System prompt string for the language pair
    """
    # Load QA config for target language
    qa_config = load_qa_config(target_lang)
    lang_code = target_lang.split('-')[0]
    
    # Load language-specific system prompt if available
    prompt_file = Path(__file__).parent.parent / 'config' / 'prompts' / lang_code / 'soft_qa_system.txt'
    if prompt_file.exists():
        base_prompt = prompt_file.read_text(encoding='utf-8')
    else:
        # Fallback to Russian (legacy behavior)
        base_prompt = f"你是手游本地化软质检（{source_lang} → {target_lang}）。\n\n"
    
    # Build grammar checks section for EN
    grammar_section = ""
    if lang_code == "en":
        grammar_rules = qa_config.get("grammar_checks", [])
        if grammar_rules:
            grammar_section = "\n英语语法检查:\n"
            for rule in grammar_rules:
                grammar_section += f"- {rule}\n"
    
    # Build dimension checks
    dimensions = qa_config.get("dimensions", [
        "terminology",
        "tone", 
        "brevity",
        "ambiguity"
    ])
    
    dim_text = "\n".join([f"- {d}" for d in dimensions])
    
    return (
        f"{base_prompt}\n"
        f"任务：分析翻译质量，仅列出有问题的项。\n\n"
        f"检查维度（只报问题，不要夸）：\n{dim_text}\n"
        f"{grammar_section}"
        "\n输出格式（硬性，仅输出 JSON）：\n"
        "{\n"
        '  "items": [\n'
        "    {\n"
        '      "id": "<id>",\n'
        '      "severity": "minor|major",\n'
        '      "issue_type": "terminology|tone|brevity|ambiguity|mistranslation|format|punctuation",\n'
        '      "problem": "<一句话描述问题>",\n'
        '      "suggestion": "<一句话给出修复方向>",\n'
        '      "preferred_fix": "<可选：建议的修复后译文>"\n'
        "    }\n"
        "  ]\n"
        "}\n"
        "规则：\n"
        '- 没问题则项目不出现在 items 中。\n'
        "- problem/suggestion 必须短句。\n"
        "- 每个有问题的 id 只输出一个最严重的 item。\n\n"
        f"术语表摘要（前 50 条）：\n{glossary_summary[:1500]}\n\n"
        f"style_guide（节选）：\n{style[:1000]}\n"
    )


def build_user_prompt(items: List[Dict], source_lang: str = "zh-CN", target_lang: str = "ru-RU") -> str:
    """Build user prompt for soft QA from batch items.
    
    Args:
        items: List of batch items with id and source_text
        source_lang: Source language code (for labeling)
        target_lang: Target language code (for labeling)
    """
    src_label = source_lang.split('-')[0].upper()
    tgt_label = target_lang.split('-')[0].upper()
    
    candidates = []
    for it in items:
        # Re-split source_text to get source and target
        parts = it.get("source_text", "").split(" | TGT: ")
        src_text = parts[0].replace("SRC: ", "") if len(parts) > 0 else ""
        tgt_text = parts[1] if len(parts) > 1 else ""
        
        candidates.append({
            "string_id": it["id"],
            f"source_{src_label.lower()}": src_text,
            f"target_{tgt_label.lower()}": tgt_text
        })
    
    return json.dumps(candidates, ensure_ascii=False, indent=2)


def build_glossary_summary(entries, max_entries: int = 50) -> str:
    """Build compact glossary summary."""
    # Handle both GlossaryEntry objects from lazy import and plain dicts
    approved = []
    for e in entries:
        if hasattr(e, 'status'):
            status = e.status.lower() if e.status else ""
            term_zh = e.term_zh
            term_ru = e.term_ru
        else:
            status = (e.get("status") or "").lower()
            term_zh = e.get("term_zh", "")
            term_ru = e.get("term_ru", "")
        if status == "approved":
            approved.append((term_zh, term_ru))
    
    approved = approved[:max_entries]
    if not approved:
        return "(无)"
    lines = [f"- {zh} → {ru}" for zh, ru in approved]
    return "\n".join(lines)


def process_batch_results(batch_items: List[Dict], target_lang: str = "ru-RU") -> List[dict]:
    """Normalize batch output items into task dicts.
    
    Args:
        batch_items: Raw batch results from LLM
        target_lang: Target language code
    
    Returns:
        List of normalized task dicts
    """
    valid_tasks = []
    tgt_code = target_lang.split('-')[0]
    
    for t in batch_items:
        # Support both old preferred_fix_ru and new preferred_fix
        suggested_fix = t.get("preferred_fix") or t.get(f"preferred_fix_{tgt_code}") or ""
        
        valid_tasks.append({
            "string_id": t.get("id", ""),
            "type": t.get("issue_type", "issue"),
            "severity": t.get("severity", "minor"),
            "note": f"{t.get('problem', '')} | Suggestion: {t.get('suggestion', '')}",
            "suggested_fix": suggested_fix,
        })
    return valid_tasks


def main():
    ap = argparse.ArgumentParser(description="LLM-based soft QA (Batch Mode v2.0)")
    ap.add_argument("translated_csv", nargs="?", help="Input translated.csv")
    ap.add_argument("--input", help="Alias for translated_csv")
    ap.add_argument("style_guide_md", nargs="?", default="workflow/style_guide.md", help="Style guide file")
    ap.add_argument("glossary_yaml", nargs="?", default="data/glossary.yaml", help="Glossary file")
    ap.add_argument("rubric_yaml", nargs="?", default="workflow/soft_qa_rubric.yaml", help="Soft QA rubric config (legacy, ignored)")
    ap.add_argument("--batch_size", type=int, default=15, help="Items per batch")
    ap.add_argument("--model", default="claude-haiku-4-5-20251001", help="Model override")
    ap.add_argument("--max_batch_tokens", type=int, default=4000, help="Max tokens per batch")
    ap.add_argument("--out_report", default="data/qa_soft_report.json", help="Output report JSON")
    ap.add_argument("--out_tasks", default="data/repair_tasks.jsonl", help="Output repair tasks JSONL")
    ap.add_argument("--dry-run", action="store_true", 
                    help="Validate configuration without making LLM calls")
    ap.add_argument("--enable-rag", action="store_true",
                    help="Enable RAG-based dynamic glossary injection (requires glossary_vectorstore)")
    ap.add_argument("--enable-semantic", action="store_true",
                    help="Enable semantic scoring pre-filter (requires semantic_scorer)")
    ap.add_argument("--rag-top-k", type=int, default=15,
                    help="Top-K terms to retrieve for RAG (default: 15)")
    ap.add_argument("--resume", action="store_true", help="Resume from existing tasks file")
    args = ap.parse_args()

    # Resolve input path
    input_path = args.input or args.translated_csv
    if not input_path:
        ap.print_help()
        return 1

    print(f"🔍 Soft QA v2.1 (Batch Mode + RAG/Semantic)")
    
    # Feature flags
    use_rag = args.enable_rag and HAS_RAG
    use_semantic = args.enable_semantic and HAS_SEMANTIC
    
    if args.enable_rag and not HAS_RAG:
        print("⚠️  RAG requested but glossary_vectorstore not available")
    if args.enable_semantic and not HAS_SEMANTIC:
        print("⚠️  Semantic scoring requested but semantic_scorer not available")
    
    # Load resources
    rows = read_csv(input_path)
    style = load_text(args.style_guide_md)

    glossary_path = args.glossary_yaml
    glossary_entries = []
    if glossary_path and Path(glossary_path).exists():
        glossary_entries, _ = load_glossary(glossary_path)
    
    glossary_summary = build_glossary_summary(glossary_entries)
    
    # Initialize RAG vector store if enabled
    glossary_store = None
    if use_rag:
        print("   Initializing RAG vector store...")
        glossary_store = GlossaryVectorStore(glossary_path)
        glossary_store.load_glossary()
        glossary_store.build_index()
    
    # Initialize semantic scorer if enabled
    semantic_scorer = None
    if use_semantic:
        print("   Initializing semantic scorer...")
        semantic_scorer = SemanticScorer()
    
    print(f"✅ Loaded {len(rows)} rows from {input_path}")
    print(f"   Glossary: {len(glossary_entries)} entries")
    if use_rag:
        print(f"   RAG: Enabled (top_k={args.rag_top_k})")
    if use_semantic:
        print(f"   Semantic scoring: Enabled")
    
    # Filter rows with target_text
    rows_with_target = [r for r in rows if r.get("target_text")]
    print(f"   Rows with translations: {len(rows_with_target)}")
    
    # Semantic pre-scoring if enabled
    semantic_scores = {}
    if use_semantic and rows_with_target:
        print("   Running semantic pre-scoring...")
        pairs = [{
            "id": r.get("string_id", ""),
            "source_zh": r.get("source_zh") or r.get("tokenized_zh") or "",
            "target_ru": r.get("target_text", "")
        } for r in rows_with_target]
        scores = semantic_scorer.score_batch(pairs)
        semantic_scores = {s["id"]: s for s in scores}
        stats = semantic_scorer.get_statistics(scores)
        print(f"   Semantic stats: OK={stats['ok']}, Warning={stats['warning']}, Error={stats['error']}, Avg={stats['avg_score']:.3f}")
    
    # Dry-run mode
    if getattr(args, 'dry_run', False):
        print()
        print("=" * 60)
        print("DRY-RUN MODE - Validation Summary")
        print("=" * 60)
        
        # Calculate estimated batches using batch config
        config_inst = get_batch_config()
        b_size = config_inst.get_batch_size(args.model, "normal")
        total_batches = (len(rows_with_target) + b_size - 1) // b_size if b_size > 0 else 1
        
        print(f"[OK] Would create ~{total_batches} batches (size: ~{b_size})")
        print(f"[OK] Average batch size: {len(rows_with_target) / max(1, total_batches):.1f}")
        print()
        print("[OK] Dry-run validation PASSED")
        print("=" * 60)
        return 0

    # Initialize LLM
    try:
        llm = LLMClient()
        print(f"✅ LLM: {llm.default_model}")
    except LLMError as e:
        print(f"❌ LLM Error: {e}")
        return 1

    print()

    # Split into batches (logic handled by batch_llm_call internally)
    start_time = time.time()
    major = 0
    minor = 0
    all_tasks = 0
    batch_errors = 0

    # Prepare rows for batch_llm_call
    # Source text for soft QA needs both ZH and RU
    batch_rows = []
    for r in rows_with_target:
        src = r.get("source_zh") or r.get("tokenized_zh") or ""
        tgt = r.get("target_text") or ""
        batch_rows.append({
            "id": r.get("string_id"),
            "source_text": f"SRC: {src} | TGT: {tgt}"
        })

    # Resume logic
    output_dir = os.path.dirname(args.out_report) or "reports"
    checkpoint_path = os.path.join(output_dir, "soft_qa_checkpoint.json")
    if args.resume and os.path.exists(checkpoint_path):
        try:
            with open(checkpoint_path, 'r', encoding='utf-8') as f:
                cp = json.load(f)
                skip_count = cp.get("rows_processed", 0)
                if skip_count > 0:
                    print(f"   ⏩ Resuming from checkpoint: skipping {skip_count} rows")
                    batch_rows = batch_rows[skip_count:]
        except Exception as e:
            print(f"   ⚠️ Failed to load checkpoint: {e}")

    # Calculate batches for logging
    config_inst = get_batch_config()
    b_size = config_inst.get_batch_size(args.model, "normal")
    total_batches = (len(batch_rows) + b_size - 1) // b_size if b_size > 0 else 1

    # Execute batch call
    try:
        batch_results = batch_llm_call(
            step="soft_qa",
            rows=batch_rows,
            model=args.model,
            system_prompt=build_system_batch(style, glossary_summary),
            user_prompt_template=build_user_prompt,
            content_type="normal",
            retry=1,
            allow_fallback=True,
            partial_match=True,
            output_dir=output_dir
        )
        
        print("   Batch results received, processing tasks...")
        tasks = process_batch_results(batch_results)
        
        if tasks:
            append_jsonl(args.out_tasks, tasks)
            all_tasks = len(tasks)
            for t in tasks:
                if t.get("severity") == "major":
                    major += 1
                else:
                    minor += 1
                    
    except Exception as e:
        print(f"❌ Soft QA failed: {e}")
        return 1

    # Calculate batches for report
    config_inst = get_batch_config()
    b_size = config_inst.get_batch_size(args.model, "normal")
    total_batches = (len(batch_rows) + b_size - 1) // b_size if b_size > 0 else 1

    # Write report - includes partial result handling
    # Check for failed batches
    failed_batches_path = "reports/soft_qa_failed_batches.json"
    failed_batches_info = None
    if os.path.exists(failed_batches_path):
        try:
            with open(failed_batches_path, "r", encoding="utf-8") as f:
                failed_batches_info = json.load(f)
        except Exception:
            pass

    report = {
        "version": "2.1",
        "mode": "batch",
        "has_findings": (major + minor) > 0,
        "summary": {
            "major": major,
            "minor": minor,
            "total_tasks": all_tasks,
            "batch_errors": batch_errors,
            "rows_processed": len(rows_with_target),
            "batches_processed": total_batches,
        },
        "outputs": {
            "repair_tasks_jsonl": args.out_tasks,
        },
        "metadata": {
            "partial": failed_batches_info is not None,
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        }
    }
    
    if failed_batches_info:
        report["failed_batches"] = failed_batches_info
    
    write_json(args.out_report, report)

    # Print summary
    total_elapsed = time.time() - start_time
    print()
    print(f"📊 Soft QA Summary:")
    print(f"   Rows processed: {len(rows_with_target)}")
    print(f"   Major issues: {major}")
    print(f"   Minor issues: {minor}")
    print(f"   Total tasks: {all_tasks}")
    print(f"   Total time: {int(total_elapsed)}s")
    print()
    print(f"✅ Report: {args.out_report}")
    if all_tasks > 0:
        print(f"✅ Repair tasks: {args.out_tasks}")

    return 0


if __name__ == "__main__":
    exit(main())
