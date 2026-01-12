#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
glossary_autopromote.py

Goal:
  Generate glossary proposals (NOT auto-approve) based on production evidence:
  - before/after RU changes (translated -> repaired)
  - terminology-related soft QA tasks

Approach:
  For each candidate row with changes, ask LLM to extract glossary candidate pairs:
    [{"term_zh": "...", "term_ru": "...", "confidence": 0.0-1.0, "note": "..."}]
  Then aggregate by (term_zh, term_ru, scope), detect conflicts against existing glossary,
  output:
    - proposals.yaml (human review)
    - patch.yaml (machine-applicable patch; still proposed by default)

Inputs:
  --before CSV (must include string_id, tokenized_zh or source_zh, target_text)
  --after  CSV (same schema)
  --glossary YAML (existing)
  --style style_guide.md
  --soft_tasks JSONL (optional)

Outputs:
  --out_proposals YAML (glossary_proposals.yaml)
  --out_patch YAML (glossary_patch.yaml)

Usage:
  python scripts/glossary_autopromote.py \\
    --before data/translated.csv \\
    --after data/repaired.csv \\
    --style workflow/style_guide.md \\
    --glossary glossary/zhCN_ruRU/base.yaml \\
    --soft_tasks data/repair_tasks.jsonl \\
    --language_pair "zh-CN->ru-RU" \\
    --scope "project_default" \\
    --min_support 5 \\
    --out_proposals data/glossary_proposals.yaml \\
    --out_patch data/glossary_patch.yaml
"""

import argparse
import csv
import json
import re
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple, Set

# Ensure UTF-8 output on Windows
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

try:
    import yaml
except ImportError:
    yaml = None

from runtime_adapter import LLMClient, LLMError

# Token pattern for placeholder detection
TOKEN_RE = re.compile(r"⟦(PH_\d+|TAG_\d+)⟧")


# -----------------------------
# IO Helpers
# -----------------------------

def read_csv_rows(path: str) -> List[Dict[str, str]]:
    """Read CSV file as list of dicts."""
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def read_jsonl(path: str) -> List[dict]:
    """Read JSONL file as list of dicts."""
    if not path or not Path(path).exists():
        return []
    out = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except Exception:
                continue
    return out


def load_text(path: str) -> str:
    """Load text file content."""
    if not Path(path).exists():
        return ""
    with open(path, "r", encoding="utf-8") as f:
        return f.read().strip()


def load_yaml_file(path: str) -> dict:
    """Load YAML file."""
    if yaml is None:
        raise RuntimeError("PyYAML required: pip install pyyaml")
    if not Path(path).exists():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def dump_yaml_file(path: str, obj: Any) -> None:
    """Write YAML file."""
    if yaml is None:
        raise RuntimeError("PyYAML required: pip install pyyaml")
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(obj, f, allow_unicode=True, sort_keys=False, default_flow_style=False)


# -----------------------------
# Glossary Data Structures
# -----------------------------

@dataclass
class GlossaryEntry:
    """A single glossary entry."""
    term_zh: str
    term_ru: str
    status: str = "proposed"
    notes: str = ""
    tags: List[str] = field(default_factory=list)
    confidence: float = 0.0


def load_glossary_entries(path: str) -> List[GlossaryEntry]:
    """Load glossary entries from YAML file."""
    if not path or not Path(path).exists():
        return []
    
    g = load_yaml_file(path)
    entries = []
    
    # Support both "entries" and legacy "candidates" format
    entry_list = g.get("entries") or g.get("candidates") or []
    
    if isinstance(entry_list, list):
        for it in entry_list:
            term_zh = (it.get("term_zh") or "").strip()
            term_ru = (it.get("term_ru") or it.get("ru_suggestion") or "").strip()
            status = (it.get("status") or "proposed").strip()
            notes = (it.get("notes") or it.get("note") or "").strip()
            tags = it.get("tags") or []
            confidence = float(it.get("confidence") or 0.0)
            
            if term_zh:
                entries.append(GlossaryEntry(
                    term_zh=term_zh,
                    term_ru=term_ru,
                    status=status,
                    notes=notes,
                    tags=tags if isinstance(tags, list) else [],
                    confidence=confidence
                ))
    
    return entries


def build_glossary_index(entries: List[GlossaryEntry]) -> Dict[str, Dict[str, List[GlossaryEntry]]]:
    """
    Build index: term_zh -> term_ru -> [entries...]
    Used for conflict detection.
    """
    idx: Dict[str, Dict[str, List[GlossaryEntry]]] = {}
    for e in entries:
        idx.setdefault(e.term_zh, {}).setdefault(e.term_ru, []).append(e)
    return idx


def glossary_to_text(entries: List[GlossaryEntry], max_entries: int = 100) -> str:
    """Convert glossary entries to text for LLM context."""
    lines = []
    for e in entries[:max_entries]:
        status_mark = "✓" if e.status == "approved" else "?"
        lines.append(f"[{status_mark}] {e.term_zh} → {e.term_ru}")
    return "\n".join(lines)


# -----------------------------
# LLM Prompting
# -----------------------------

def build_system_prompt(style: str, language_pair: str) -> str:
    """Build system prompt for term extraction."""
    return f"""\
你是资深手游本地化术语工程师（{language_pair}）。

任务：从给定的中文源文与译文（修复前/修复后）中，抽取"可沉淀为术语表"的候选项。

要求：
1) 只抽取术语（专有名词、系统功能词、可复用的 UI/玩法词），不要抽整句。
2) term_zh 必须来自源文（直接出现），term_ru 必须来自译文（直接出现或显式等价写法）。
3) 如果修复前后译文发生变化，重点关注变化的部分。
4) confidence 分数规则：
   - 0.9+: 专有名词（人名/地名/技能名）
   - 0.7-0.9: 系统术语（功能名/道具名）
   - 0.5-0.7: 常用游戏词汇
   - <0.5: 不确定是否应该固定
5) 输出纯 JSON：{{"candidates": [{{"term_zh":"...", "term_ru":"...", "confidence":0.0-1.0, "note":"..."}}]}}
6) 不要输出解释文本，只输出 JSON。

风格规范（供参考，不是让你改文案）：
{style[:2000]}
"""


def build_user_prompt(
    row: dict,
    before_ru: str,
    after_ru: str,
    glossary_excerpt: str,
    scope: str,
    language_pair: str
) -> str:
    """Build user prompt for term extraction."""
    tokenized_zh = row.get("tokenized_zh") or row.get("source_zh") or ""
    string_id = row.get("string_id", "")
    
    return f"""\
language_pair={language_pair}
scope={scope}
string_id={string_id}
tokenized_zh={json.dumps(tokenized_zh, ensure_ascii=False)}
before_ru={json.dumps(before_ru or '', ensure_ascii=False)}
after_ru={json.dumps(after_ru or '', ensure_ascii=False)}

已有术语表（节选，避免重复提案；标记 ✓ 的 approved 必须尊重）：
{glossary_excerpt}

请输出 JSON candidates。仅抽取术语，不要抽整句。"""


def extract_json_obj(text: str) -> Optional[dict]:
    """Extract JSON object from LLM response."""
    text = (text or "").strip()
    
    # Try direct parse
    try:
        obj = json.loads(text)
        if isinstance(obj, dict):
            return obj
    except Exception:
        pass
    
    # Try to find JSON in text
    s = text.find("{")
    e = text.rfind("}")
    if s != -1 and e != -1 and e > s:
        try:
            obj = json.loads(text[s:e+1])
            if isinstance(obj, dict):
                return obj
        except Exception:
            pass
    
    return None


# -----------------------------
# Candidate Selection
# -----------------------------

def token_counts(s: str) -> Dict[str, int]:
    """Count placeholder tokens in string."""
    d = {}
    for m in TOKEN_RE.finditer(s or ""):
        k = m.group(1)
        d[k] = d.get(k, 0) + 1
    return d


def build_row_maps(rows: List[Dict[str, str]]) -> Dict[str, Dict[str, str]]:
    """Build string_id -> row mapping."""
    m = {}
    for r in rows:
        sid = (r.get("string_id") or "").strip()
        if sid:
            m[sid] = r
    return m


def select_candidate_ids(
    before: Dict[str, Dict[str, str]],
    after: Dict[str, Dict[str, str]],
    soft_tasks: List[dict]
) -> List[str]:
    """
    Select string_ids that are candidates for term extraction.
    Sources:
    1. Rows where before/after target_text differ (repair changes)
    2. Rows with terminology-related soft QA issues
    """
    ids: Set[str] = set()
    
    # Diff-based selection
    for sid, arow in after.items():
        brow = before.get(sid)
        if not brow:
            continue
        b_ru = (brow.get("target_text") or "").strip()
        a_ru = (arow.get("target_text") or "").strip()
        if b_ru and a_ru and b_ru != a_ru:
            ids.add(sid)
    
    # Soft task based selection (terminology issues)
    for t in soft_tasks:
        sid = (t.get("string_id") or "").strip()
        typ = (t.get("type") or "").lower()
        if sid and ("terminology" in typ or "term" in typ or "consistency" in typ):
            ids.add(sid)
    
    return sorted(ids)


# -----------------------------
# Aggregation & Conflict Detection
# -----------------------------

@dataclass
class TermStats:
    """Statistics for a (term_zh, term_ru) pair."""
    term_zh: str
    term_ru: str
    support: int = 0
    total_confidence: float = 0.0
    examples: List[dict] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)
    conflicts: List[dict] = field(default_factory=list)
    
    @property
    def avg_confidence(self) -> float:
        return self.total_confidence / self.support if self.support > 0 else 0.0


def detect_conflicts(
    term_zh: str,
    term_ru: str,
    glossary_idx: Dict[str, Dict[str, List[GlossaryEntry]]]
) -> List[dict]:
    """
    Check if this term pair conflicts with existing approved entries.
    Conflict: same term_zh has different approved term_ru.
    """
    conflicts = []
    existing = glossary_idx.get(term_zh, {})
    
    if existing:
        for ru, ents in existing.items():
            for e in ents:
                if e.status.lower() == "approved" and e.term_ru and e.term_ru != term_ru:
                    conflicts.append({
                        "type": "approved_conflict",
                        "approved_ru": e.term_ru,
                        "note": f"Conflicts with approved: {term_zh} → {e.term_ru}"
                    })
    
    return conflicts


# -----------------------------
# Main
# -----------------------------

def main():
    ap = argparse.ArgumentParser(description="Glossary autopromote from production evidence")
    
    # Input files
    ap.add_argument("--before", required=True, help="Before CSV (e.g., translated.csv)")
    ap.add_argument("--after", required=True, help="After CSV (e.g., repaired.csv)")
    ap.add_argument("--style", required=True, help="Style guide markdown")
    ap.add_argument("--glossary", required=True, help="Existing glossary YAML")
    ap.add_argument("--soft_tasks", default=None, help="Soft QA tasks JSONL (optional)")
    
    # Configuration
    ap.add_argument("--language_pair", default="zh-CN->ru-RU", help="Language pair")
    ap.add_argument("--scope", default="project_default", help="Scope tag (e.g., ip_naruto)")
    ap.add_argument("--min_support", type=int, default=5, help="Minimum occurrences to propose")
    ap.add_argument("--max_conflict_ratio", type=float, default=0.2, help="Max conflict ratio allowed")
    ap.add_argument("--max_rows", type=int, default=500, help="Max rows to process (safety cap)")
    
    # Output files
    ap.add_argument("--out_proposals", default="data/glossary_proposals.yaml", help="Output proposals YAML")
    ap.add_argument("--out_patch", default="data/glossary_patch.yaml", help="Output patch YAML")
    
    # Rejected terms (to avoid re-proposing)
    ap.add_argument("--rejected", default="glossary/rejected.yaml", 
                    help="Rejected terms YAML (avoid re-proposing)")
    
    # Dry-run mode
    ap.add_argument("--dry-run", action="store_true",
                    help="Validate configuration and count candidates without making LLM calls")
    
    args = ap.parse_args()
    
    print(f"🔄 Glossary Autopromote")
    print(f"   Before: {args.before}")
    print(f"   After: {args.after}")
    print(f"   Glossary: {args.glossary}")
    print(f"   Scope: {args.scope}")
    print(f"   Min support: {args.min_support}")
    print()
    
    # Load data
    before_rows = read_csv_rows(args.before)
    after_rows = read_csv_rows(args.after)
    before_map = build_row_maps(before_rows)
    after_map = build_row_maps(after_rows)
    
    style = load_text(args.style)
    glossary_entries = load_glossary_entries(args.glossary)
    glossary_idx = build_glossary_index(glossary_entries)
    glossary_excerpt = glossary_to_text(glossary_entries, max_entries=80)
    
    # Load rejected terms to avoid re-proposing
    rejected_entries = load_glossary_entries(args.rejected) if Path(args.rejected).exists() else []
    rejected_set = {(e.term_zh.strip(), e.term_ru.strip()) for e in rejected_entries}
    if rejected_entries:
        print(f"✅ Loaded {len(rejected_entries)} rejected terms (will skip)")
    
    soft_tasks = read_jsonl(args.soft_tasks) if args.soft_tasks else []
    
    # Select candidate rows
    candidate_ids = select_candidate_ids(before_map, after_map, soft_tasks)
    print(f"📋 Found {len(candidate_ids)} candidate rows with changes")
    
    if len(candidate_ids) > args.max_rows:
        print(f"⚠️  Capping to {args.max_rows} rows")
        candidate_ids = candidate_ids[:args.max_rows]
    
    # Dry-run mode
    if getattr(args, 'dry_run', False):
        print()
        print("=" * 60)
        print("DRY-RUN MODE - Validation Summary")
        print("=" * 60)
        print()
        print(f"[OK] Before CSV: {len(before_rows)} rows")
        print(f"[OK] After CSV: {len(after_rows)} rows")
        print(f"[OK] Style guide: {len(style)} chars")
        print(f"[OK] Existing glossary: {len(glossary_entries)} entries")
        print(f"[OK] Candidate rows: {len(candidate_ids)}")
        print(f"[OK] Language pair: {args.language_pair}")
        print(f"[OK] Scope: {args.scope}")
        
        # Check LLM env
        import os
        llm_model = os.getenv("LLM_MODEL", "")
        if llm_model:
            print(f"[OK] LLM model: {llm_model}")
        else:
            print(f"[WARN] LLM_MODEL not set")
        
        print()
        print("=" * 60)
        print("[OK] Dry-run validation PASSED")
        if candidate_ids:
            print(f"     {len(candidate_ids)} candidates would be processed in actual run")
        else:
            print(f"     No candidates found")
        print("=" * 60)
        return 0
    
    if not candidate_ids:
        print("ℹ️  No candidates found, nothing to propose")
        # Write empty outputs
        dump_yaml_file(args.out_proposals, {"meta": {}, "proposals": []})
        dump_yaml_file(args.out_patch, {"op": "append_entries", "entries": []})
        return 0
    
    # Initialize LLM
    llm = LLMClient()
    sys_prompt = build_system_prompt(style, args.language_pair)
    
    # Collect term statistics
    stats: Dict[Tuple[str, str], TermStats] = {}
    processed = 0
    errors = 0
    
    for sid in candidate_ids:
        arow = after_map.get(sid)
        brow = before_map.get(sid)
        if not arow or not brow:
            continue
        
        tokenized_zh = arow.get("tokenized_zh") or arow.get("source_zh") or ""
        before_ru = (brow.get("target_text") or "").strip()
        after_ru = (arow.get("target_text") or "").strip()
        
        # Skip if placeholder counts don't match (likely broken string)
        if token_counts(tokenized_zh) != token_counts(after_ru):
            continue
        
        # Build prompt and call LLM
        user_prompt = build_user_prompt(
            arow, before_ru, after_ru,
            glossary_excerpt, args.scope, args.language_pair
        )
        
        try:
            result = llm.chat(
                system=sys_prompt,
                user=user_prompt,
                temperature=0.1,
                metadata={"step": "glossary_autopromote", "scope": args.scope, "string_id": sid}
            )
            raw = result.text
            processed += 1
        except LLMError as e:
            errors += 1
            print(f"⚠️  LLM error for {sid}: {e}")
            continue
        
        # Parse response
        obj = extract_json_obj(raw)
        if not obj or "candidates" not in obj:
            continue
        
        # Process candidates
        for c in obj.get("candidates", []) or []:
            term_zh = (c.get("term_zh") or "").strip()
            term_ru = (c.get("term_ru") or "").strip()
            conf = float(c.get("confidence") or 0.0)
            note = (c.get("note") or "").strip()
            
            if not term_zh or not term_ru:
                continue
            
            # Validate: term_zh must appear in source
            if term_zh not in tokenized_zh:
                continue
            
            # Aggregate stats
            k = (term_zh, term_ru)
            if k not in stats:
                stats[k] = TermStats(term_zh=term_zh, term_ru=term_ru)
            
            s = stats[k]
            s.support += 1
            s.total_confidence += conf
            
            if len(s.examples) < 5:
                s.examples.append({
                    "string_id": sid,
                    "before_ru": before_ru[:120],
                    "after_ru": after_ru[:120]
                })
            
            if note and len(s.notes) < 5 and note not in s.notes:
                s.notes.append(note)
        
        # Progress
        if processed % 50 == 0:
            print(f"   Processed {processed}/{len(candidate_ids)} rows...")
    
    print(f"✅ Processed {processed} rows, {errors} errors")
    print(f"📊 Found {len(stats)} unique term pairs")
    
    # Conflict detection and filtering
    for (term_zh, term_ru), s in stats.items():
        s.conflicts = detect_conflicts(term_zh, term_ru, glossary_idx)
    
    # Filter by support and conflict
    proposals = []
    skipped_rejected = 0
    for k, s in sorted(stats.items(), key=lambda kv: (kv[1].support, kv[1].avg_confidence), reverse=True):
        if s.support < args.min_support:
            continue
        
        # Skip previously rejected terms
        if (s.term_zh.strip(), s.term_ru.strip()) in rejected_set:
            skipped_rejected += 1
            continue
        
        # Hard conflicts with approved entries are rejected
        if s.conflicts:
            print(f"⚠️  Conflict: {s.term_zh} → {s.term_ru} (conflicts with approved)")
            continue
        
        proposals.append({
            "term_zh": s.term_zh,
            "term_ru": s.term_ru,
            "status": "proposed",
            "confidence": round(s.avg_confidence, 4),
            "support": s.support,
            "scope": args.scope,
            "language_pair": args.language_pair,
            "evidence": {
                "examples": s.examples,
                "notes": s.notes,
            }
        })
    
    print(f"📝 Generated {len(proposals)} proposals")
    if skipped_rejected > 0:
        print(f"⏭️  Skipped {skipped_rejected} previously rejected terms")
    
    # Build output structures
    out_proposals = {
        "meta": {
            "version": 1,
            "generated_at": datetime.now().isoformat(),
            "generated_from": {
                "before": args.before,
                "after": args.after,
                "soft_tasks": args.soft_tasks,
            },
            "language_pair": args.language_pair,
            "scope": args.scope,
            "min_support": args.min_support,
            "stats": {
                "candidate_rows": len(candidate_ids),
                "processed": processed,
                "unique_pairs": len(stats),
                "proposals": len(proposals),
            }
        },
        "proposals": proposals
    }
    
    # Patch: entries to append (all as proposed)
    patch = {
        "op": "append_entries",
        "target_glossary": args.glossary,
        "generated_at": datetime.now().isoformat(),
        "entries": [
            {
                "term_zh": p["term_zh"],
                "term_ru": p["term_ru"],
                "status": "proposed",
                "tags": [args.scope],
                "confidence": p["confidence"],
                "notes": f"autopromote support={p['support']} scope={args.scope}",
            }
            for p in proposals
        ]
    }
    
    # Write outputs
    dump_yaml_file(args.out_proposals, out_proposals)
    dump_yaml_file(args.out_patch, patch)
    
    print()
    print(f"✅ Wrote proposals: {args.out_proposals}")
    print(f"✅ Wrote patch: {args.out_patch}")
    print()
    print(f"📋 Next steps:")
    print(f"   1. Review proposals in {args.out_proposals}")
    print(f"   2. Edit status to 'approved' for confirmed terms")
    print(f"   3. Apply patch: python scripts/glossary_apply_patch.py --patch {args.out_patch}")
    
    return 0


if __name__ == "__main__":
    exit(main())
