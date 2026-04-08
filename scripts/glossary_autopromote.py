#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
glossary_autopromote.py (v2.1 - Batch Mode)

Generate glossary proposals from translation repair evidence and soft QA tasks.

Inputs:
  --before CSV (must include string_id, tokenized_zh/source_zh, target_text)
  --after CSV (same schema)
  --glossary YAML (existing glossary)
  --style_profile YAML (generated style profile, optional)

Outputs:
  --out_proposals YAML (glossary_proposals.yaml)
  --out_patch YAML (glossary_patch.yaml)
"""

import argparse
import csv
import json
import re
import os
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple, Set

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

try:
    import yaml
except ImportError:
    yaml = None

from runtime_adapter import LLMClient, LLMError

try:
    from batch_utils import BatchConfig, split_into_batches, format_progress
except ImportError:
    print("ERROR: batch_utils.py not found. Please ensure it exists in scripts/")
    sys.exit(1)

try:
    from progress_reporter import ProgressReporter
except ImportError:
    print("WARNING: progress_reporter.py not found. Metrics will be skipped.")
    ProgressReporter = None

TOKEN_RE = re.compile(r"⟦(PH_\d+|TAG_\d+)⟧")


def load_csv_rows(path: str) -> List[Dict[str, str]]:
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def load_jsonl(path: str) -> List[dict]:
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


def load_yaml_file(path: str) -> dict:
    if not path or not Path(path).exists():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        payload = yaml.safe_load(f) or {} if yaml is not None else {}
    return payload if isinstance(payload, dict) else {}


def load_style_profile(path: str) -> dict:
    return load_yaml_file(path)


def dump_yaml_file(path: str, obj: Any) -> None:
    if yaml is None:
        raise RuntimeError("PyYAML required: pip install pyyaml")
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(obj, f, allow_unicode=True, sort_keys=False, default_flow_style=False)


@dataclass
class GlossaryEntry:
    term_zh: str
    term_ru: str
    status: str = "proposed"
    notes: str = ""
    tags: List[str] = field(default_factory=list)
    confidence: float = 0.0


def load_glossary_entries(path: str) -> List[GlossaryEntry]:
    if not path or not Path(path).exists():
        return []
    g = load_yaml_file(path)
    entries = []
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
                entries.append(
                    GlossaryEntry(
                        term_zh=term_zh,
                        term_ru=term_ru,
                        status=status,
                        notes=notes,
                        tags=tags if isinstance(tags, list) else [],
                        confidence=confidence,
                    )
                )
    return entries


def build_glossary_index(entries: List[GlossaryEntry]) -> Dict[str, Dict[str, List[GlossaryEntry]]]:
    idx: Dict[str, Dict[str, List[GlossaryEntry]]] = {}
    for e in entries:
        idx.setdefault(e.term_zh, {}).setdefault(e.term_ru, []).append(e)
    return idx


def glossary_to_text(entries: List[GlossaryEntry], max_entries: int = 100) -> str:
    lines = []
    for e in entries[:max_entries]:
        status_mark = "✓" if e.status == "approved" else "?"
        lines.append(f"[{status_mark}] {e.term_zh} → {e.term_ru}")
    return "\n".join(lines)


def build_system_prompt_batch(glossary_excerpt: str) -> str:
    return (
        "你是资深手游本地化术语工程师（zh-CN → ru-RU）。\n"
        "任务：从给定的批量数据中，抽取'可沉淀为术语表'的候选项。\n\n"
        "输入：JSON 数组，每项包含 string_id、source_zh、before_ru、after_ru。\n"
        "输出：JSON 对象，包含 candidates 数组。\n\n"
        "输出格式（仅输出 JSON）：\n"
        "{\n"
        '  "candidates": [\n'
        "    {\n"
        '      "term_zh": "<中文原词>",\n'
        '      "term_ru": "<俄文对应词>",\n'
        '      "string_id": "<来源string_id>",\n'
        '      "confidence": 0.9,\n'
        '      "note": "<简短理由>"\n'
        "    }\n"
        "  ]\n"
        "}\n\n"
        "抽取规则：\n"
        "- 只抽名词/专有名词/系统词/UI词，不抽动词或整句。\n"
        "- 优先抽取 before_ru 和 after_ru 不同的词（说明是修正点）。\n"
        "- 每个 term_zh 在整个批次中只输出一次（去重）。\n"
        "- confidence 规则：专有名词 > 系统词 > 一般词。\n"
        "- 如果批次中没有可抽取的术语，输出 { \"candidates\": [] }。\n\n"
        f"现有术语表参考（避免重复）：\n{glossary_excerpt[:1500]}\n"
    )


def build_batch_input(rows: List[dict]) -> List[dict]:
    return [
        {
            "string_id": item.get("string_id", ""),
            "source_zh": item.get("source_zh", ""),
            "before_ru": item.get("before_ru", ""),
            "after_ru": item.get("after_ru", "")
        }
        for item in rows
    ]


def extract_candidates_from_response(text: str) -> List[dict]:
    text = (text or "").strip()
    try:
        obj = json.loads(text)
        if isinstance(obj, dict) and "candidates" in obj:
            return obj["candidates"]
    except json.JSONDecodeError:
        pass
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            obj = json.loads(text[start:end + 1])
            if isinstance(obj, dict) and "candidates" in obj:
                return obj["candidates"]
        except json.JSONDecodeError:
            pass
    return []


def token_counts(s: str) -> Dict[str, int]:
    d = {}
    for m in TOKEN_RE.finditer(s or ""):
        k = m.group(1)
        d[k] = d.get(k, 0) + 1
    return d


def build_row_maps(rows: List[Dict[str, str]]) -> Dict[str, Dict[str, str]]:
    m = {}
    for r in rows:
        sid = (r.get("string_id") or "").strip()
        if sid:
            m[sid] = r
    return m


def select_candidate_rows(before_map: Dict[str, Dict[str, str]], after_map: Dict[str, Dict[str, str]], soft_tasks: List[dict]) -> List[dict]:
    candidates = []
    seen_ids: Set[str] = set()
    for sid, arow in after_map.items():
        brow = before_map.get(sid)
        if not brow:
            continue
        b_ru = (brow.get("target_text") or "").strip()
        a_ru = (arow.get("target_text") or "").strip()
        if b_ru and a_ru and b_ru != a_ru:
            source_zh = arow.get("tokenized_zh") or arow.get("source_zh") or ""
            if token_counts(source_zh) != token_counts(a_ru):
                continue
            candidates.append({
                "string_id": sid,
                "source_zh": source_zh,
                "before_ru": b_ru,
                "after_ru": a_ru
            })
            seen_ids.add(sid)

    for t in soft_tasks:
        sid = (t.get("string_id") or "").strip()
        typ = (t.get("type") or "").lower()
        if sid and sid not in seen_ids and ("terminology" in typ or "term" in typ):
            arow = after_map.get(sid)
            brow = before_map.get(sid)
            if arow and brow:
                source_zh = arow.get("tokenized_zh") or arow.get("source_zh") or ""
                candidates.append({
                    "string_id": sid,
                    "source_zh": source_zh,
                    "before_ru": (brow.get("target_text") or ""),
                    "after_ru": (arow.get("target_text") or "")
                })
                seen_ids.add(sid)
    return candidates


@dataclass
class TermStats:
    term_zh: str
    term_ru: str
    support: int = 0
    total_confidence: float = 0.0
    examples: List[dict] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)
    conflicts: List[dict] = field(default_factory=list)
    style_note: str = ""

    @property
    def avg_confidence(self) -> float:
        return self.total_confidence / self.support if self.support > 0 else 0.0


def detect_conflicts(
    term_zh: str,
    term_ru: str,
    glossary_idx: Dict[str, Dict[str, List[GlossaryEntry]]],
) -> List[dict]:
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


def profile_alignment(
    term_zh: str,
    term_ru: str,
    forbidden_terms: Set[str],
    preferred_terms: Dict[str, str],
) -> tuple[str, bool, List[str]]:
    if term_zh in forbidden_terms:
        return "banned", True, [f"term_zh '{term_zh}' in forbidden_terms"]
    pref = preferred_terms.get(term_zh)
    if pref and pref != term_ru:
        return "proposed", True, [f"preferred translation mismatch, expected '{pref}'"]
    return "proposed", False, []


def process_batch(
    batch: List[dict],
    llm: LLMClient,
    glossary_excerpt: str,
    scope: str,
    batch_idx: int,
    max_retries: int = 2,
) -> Tuple[List[dict], Dict[str, Any]]:
    if not batch:
        return []

    system = build_system_prompt_batch(glossary_excerpt)
    batch_input = build_batch_input(batch)
    user_prompt = json.dumps(batch_input, ensure_ascii=False, indent=None)

    for attempt in range(max_retries + 1):
        try:
            result = llm.chat(
                system=system,
                user=user_prompt,
                temperature=0.1,
                metadata={
                    "step": "glossary_autopromote",
                    "batch_idx": batch_idx,
                    "batch_size": len(batch),
                    "scope": scope,
                    "attempt": attempt,
                },
                response_format={"type": "json_object"},
            )
            candidates = extract_candidates_from_response(result.text)
            metrics = {
                "request_id": getattr(result, "request_id", None),
                "usage": getattr(result, "usage", None),
                "model": result.model if hasattr(result, "model") else llm.default_model,
            }
            return candidates, metrics
        except Exception as e:
            if attempt >= max_retries:
                print(f"    ⚠️ Batch {batch_idx} error: {e}")
                return [], {}
            time.sleep(1)

    return [], {}


def build_profile_hints(profile: dict) -> Tuple[Set[str], Dict[str, str]]:
    terms = profile.get("terminology", {}) if isinstance(profile, dict) else {}
    forbidden = set()
    preferred = {}
    if isinstance(terms, dict):
        forbidden = {(str(x).strip()) for x in terms.get("forbidden_terms", []) if str(x).strip()}
        forbidden |= {(str(x).strip()) for x in terms.get("banned_terms", []) if str(x).strip()}
        for item in terms.get("preferred_terms", []) or []:
            if isinstance(item, dict):
                zh = str(item.get("term_zh", "")).strip()
                ru = str(item.get("term_ru", "")).strip()
                if zh and ru:
                    preferred[zh] = ru
    return forbidden, preferred


def main():
    ap = argparse.ArgumentParser(description="Glossary autopromote (Batch Mode v2.1)")
    ap.add_argument("--before", required=True, help="Before CSV (e.g., translated.csv)")
    ap.add_argument("--after", required=True, help="After CSV (e.g., repaired.csv)")
    ap.add_argument("--style", required=True, help="Style guide markdown")
    ap.add_argument("--style-profile", default="data/style_profile.yaml", help="Style profile YAML")
    ap.add_argument("--glossary", required=True, help="Existing glossary YAML")
    ap.add_argument("--soft_tasks", default=None, help="Soft QA tasks JSONL (optional)")
    ap.add_argument("--language_pair", default="zh-CN->ru-RU", help="Language pair")
    ap.add_argument("--scope", default="project_default", help="Scope tag (e.g., ip_naruto)")
    ap.add_argument("--batch_size", type=int, default=15, help="Items per batch")
    ap.add_argument("--min_support", type=int, default=1, help="Minimum occurrences to propose")
    ap.add_argument("--max_rows", type=int, default=500, help="Max rows to process (safety cap)")
    ap.add_argument("--out_proposals", default="data/glossary_proposals.yaml", help="Output proposals YAML")
    ap.add_argument("--out_patch", default="data/glossary_patch.yaml", help="Output patch YAML")
    ap.add_argument("--rejected", default="glossary/rejected.yaml", help="Rejected terms YAML")
    ap.add_argument("--dry-run", action="store_true", help="Validate configuration without LLM calls")
    args = ap.parse_args()

    print("🔄 Glossary Autopromote v2.1 (Batch Mode)")
    print(f"   Batch size: {args.batch_size}")
    print()

    before_rows = load_csv_rows(args.before)
    after_rows = load_csv_rows(args.after)
    before_map = build_row_maps(before_rows)
    after_map = build_row_maps(after_rows)

    glossary_entries = load_glossary_entries(args.glossary)
    glossary_idx = build_glossary_index(glossary_entries)
    glossary_excerpt = glossary_to_text(glossary_entries, max_entries=80)

    style_profile = load_style_profile(args.style_profile)
    forbidden_terms, preferred_terms = build_profile_hints(style_profile)
    if style_profile:
        print(f"✅ Loaded style profile: {args.style_profile}")
        print(f"   forbidden_terms={len(forbidden_terms)} preferred_terms={len(preferred_terms)}")

    rejected_entries = load_glossary_entries(args.rejected) if Path(args.rejected).exists() else []
    rejected_set = {(e.term_zh.strip(), e.term_ru.strip()) for e in rejected_entries}

    soft_tasks = load_jsonl(args.soft_tasks) if args.soft_tasks else []
    candidate_rows = select_candidate_rows(before_map, after_map, soft_tasks)
    print(f"📋 Found {len(candidate_rows)} candidate rows with changes")
    if len(candidate_rows) > args.max_rows:
        print(f"⚠️  Capping to {args.max_rows} rows")
        candidate_rows = candidate_rows[:args.max_rows]

    if args.dry_run:
        print("⚙️  Dry-run mode")
        config = BatchConfig(max_items=args.batch_size, max_tokens=4000)
        batches = split_into_batches(candidate_rows, config)
        print(f"   style_profile: {args.style_profile}")
        print(f"   Would create {len(batches)} batches")
        print("✅ Dry-run validation PASSED")
        return 0

    if not candidate_rows:
        dump_yaml_file(args.out_proposals, {"meta": {}, "proposals": []})
        dump_yaml_file(args.out_patch, {"op": "append_entries", "entries": []})
        print("ℹ️  No candidates found, nothing to propose")
        return 0

    llm = LLMClient()
    print(f"✅ LLM: {llm.default_model}")

    config = BatchConfig(max_items=args.batch_size, max_tokens=4000)
    config.text_fields = ["source_zh", "before_ru", "after_ru"]
    batches = split_into_batches(candidate_rows, config)
    print(f"   Batches: {len(batches)}")
    print()

    start_time = time.time()
    reporter = (
        ProgressReporter(
            "glossary_autopromote",
            str(Path(args.out_proposals).resolve().parent),
            len(candidate_rows),
        )
        if ProgressReporter
        else None
    )

    stats: Dict[Tuple[str, str], TermStats] = {}
    processed_batches = 0

    for batch_idx, batch in enumerate(batches):
        batch_start = time.time()
        candidates, metrics = process_batch(batch, llm, glossary_excerpt, args.scope, batch_idx)
        for c in candidates:
            term_zh = (c.get("term_zh") or "").strip()
            term_ru = (c.get("term_ru") or "").strip()
            conf = float(c.get("confidence") or 0.5)
            note = (c.get("note") or "").strip()
            string_id = (c.get("string_id") or "").strip()
            if not term_zh or not term_ru:
                continue
            k = (term_zh, term_ru)
            if k not in stats:
                stats[k] = TermStats(term_zh=term_zh, term_ru=term_ru)
            s = stats[k]
            s.support += 1
            s.total_confidence += conf
            if len(s.examples) < 5 and string_id:
                s.examples.append({"string_id": string_id})
            if note and len(s.notes) < 5 and note not in s.notes:
                s.notes.append(note)

        processed_batches += 1
        if reporter:
            latency_ms = int((time.time() - batch_start) * 1000)
            reporter.batch_complete(
                batch_idx + 1,
                len(batches),
                success_count=len(batch),
                failed_count=0,
                latency_ms=latency_ms,
                metadata={
                    "model": metrics.get("model", "unknown"),
                    "scope": args.scope,
                    "request_id": metrics.get("request_id"),
                    "usage": metrics.get("usage"),
                },
            )

        batch_time = time.time() - batch_start
        elapsed = time.time() - start_time
        if (batch_idx + 1) % 3 == 0 or batch_idx == len(batches) - 1:
            print(format_progress(processed_batches, len(batches), batch_idx + 1, len(batches), elapsed, batch_time))

    total_elapsed = time.time() - start_time
    print()
    print(f"✅ Processed {processed_batches} batches in {int(total_elapsed)}s")
    print(f"📊 Found {len(stats)} unique term pairs")

    proposals = []
    for k, s in sorted(stats.items(), key=lambda kv: (kv[1].support, kv[1].avg_confidence), reverse=True):
        if s.support < args.min_support:
            continue
        if (s.term_zh.strip(), s.term_ru.strip()) in rejected_set:
            continue

        conflicts = detect_conflicts(s.term_zh, s.term_ru, glossary_idx)
        s.conflicts = conflicts
        if conflicts:
            continue

        profile_status, requires_manual, profile_notes = profile_alignment(
            s.term_zh,
            s.term_ru,
            forbidden_terms,
            preferred_terms,
        )
        proposals.append({
            "term_zh": s.term_zh,
            "term_ru": s.term_ru,
            "status": profile_status,
            "confidence": round(s.avg_confidence, 4),
            "support": s.support,
            "scope": args.scope,
            "language_pair": args.language_pair,
            "evidence": {
                "examples": s.examples,
                "notes": s.notes,
            },
            "style_profile": {
                "requires_manual_confirmation": requires_manual,
                "notes": profile_notes,
            },
        })

    print(f"📝 Generated {len(proposals)} proposals")

    out_proposals = {
        "meta": {
            "version": 2,
            "mode": "batch",
            "generated_at": datetime.now().isoformat(),
            "min_support": args.min_support,
            "style_profile": {
                "path": args.style_profile,
                "forbidden_terms": len(forbidden_terms),
                "preferred_terms": len(preferred_terms),
            },
            "stats": {
                "candidate_rows": len(candidate_rows),
                "batches_processed": processed_batches,
                "unique_pairs": len(stats),
                "proposals": len(proposals),
            },
        },
        "proposals": proposals,
    }

    patch = {
        "op": "append_entries",
        "target_glossary": args.glossary,
        "generated_at": datetime.now().isoformat(),
        "entries": [
            {
                "term_zh": p["term_zh"],
                "term_ru": p["term_ru"],
                "status": p["status"],
                "tags": [args.scope],
                "confidence": p["confidence"],
                "notes": f"autopromote support={p['support']} scope={args.scope}",
                "requires_manual_confirmation": bool(p.get("style_profile", {}).get("requires_manual_confirmation", False)),
            }
            for p in proposals
        ],
    }

    dump_yaml_file(args.out_proposals, out_proposals)
    dump_yaml_file(args.out_patch, patch)

    print(f"\n✅ Output: {args.out_proposals}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
