#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Build a targeted residual triage slice from a UI-art full rerun.

The slice is derived from:
- qa_hard blocking rows
- soft_qa hard-gate violations
- siblings of assessment top true-residual source clusters

Outputs are written into a dedicated residual slice directory and used by the
serial repair runner.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

try:
    import yaml
except Exception:  # pragma: no cover
    yaml = None


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_BATCH_ROOT = REPO_ROOT / "data" / "incoming" / "ui_art_batch"
DEFAULT_BASE_RUN_DIR = DEFAULT_BATCH_ROOT / "runs" / "ui_art_full_rerun_run01"
DEFAULT_OVERRIDE_PATH = DEFAULT_BATCH_ROOT / "residual_patch_overrides.json"

DEFAULT_MANUAL_CREATIVE_SOURCES: set[str] = set()
DEFAULT_EXACT_PATCH_MAP: Dict[str, str] = {}
DEFAULT_PATCH_AVOID_LONG_FORMS: Dict[str, List[str]] = {}
DEFAULT_PROMO_HINT_SOURCES: set[str] = set()
DEFAULT_HEADLINE_EVENT_SOURCES: set[str] = set()
DEFAULT_PROMO_EXACT_SOURCES: set[str] = set()
DEFAULT_ITEM_EXACT_SOURCES: set[str] = set()
DEFAULT_HEADLINE_EXACT_SOURCES: set[str] = set()

MANUAL_CREATIVE_SOURCES: set[str] = set(DEFAULT_MANUAL_CREATIVE_SOURCES)
EXACT_PATCH_MAP: Dict[str, str] = dict(DEFAULT_EXACT_PATCH_MAP)
PATCH_AVOID_LONG_FORMS: Dict[str, List[str]] = dict(DEFAULT_PATCH_AVOID_LONG_FORMS)
PROMO_HINT_SOURCES: set[str] = set(DEFAULT_PROMO_HINT_SOURCES)
PROMO_EXACT_SOURCES: set[str] = set(DEFAULT_PROMO_EXACT_SOURCES)
ITEM_EXACT_SOURCES: set[str] = set(DEFAULT_ITEM_EXACT_SOURCES)
HEADLINE_EXACT_SOURCES: set[str] = set(DEFAULT_HEADLINE_EXACT_SOURCES)

ITEM_FAMILY_HINTS = ("试炼", "之力", "之门", "模式", "战场", "御中")
HEADLINE_EVENT_SOURCES: set[str] = set(DEFAULT_HEADLINE_EVENT_SOURCES)

LANE_PRIORITY = {
    "promo_exact_or_compound": 1,
    "item_skill_family_compact": 2,
    "headline_slogan_repair": 3,
    "badge_micro_gap_cleanup": 4,
    "creative_title_manual": 5,
}


def read_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def read_jsonl(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    items: List[Dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        items.append(json.loads(line))
    return items


def write_jsonl(path: Path, items: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for item in items:
            fh.write(json.dumps(item, ensure_ascii=False) + "\n")


def read_csv(path: Path) -> Tuple[List[Dict[str, str]], List[str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        rows = list(reader)
        return rows, list(reader.fieldnames or [])


def write_csv(path: Path, rows: List[Dict[str, str]], fieldnames: Iterable[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(fieldnames))
        writer.writeheader()
        writer.writerows(rows)


def normalize_source(text: str) -> str:
    return "".join(str(text or "").split())


def apply_override_asset(path: Path) -> None:
    globals()["MANUAL_CREATIVE_SOURCES"] = set(DEFAULT_MANUAL_CREATIVE_SOURCES)
    globals()["EXACT_PATCH_MAP"] = dict(DEFAULT_EXACT_PATCH_MAP)
    globals()["PATCH_AVOID_LONG_FORMS"] = dict(DEFAULT_PATCH_AVOID_LONG_FORMS)
    globals()["PROMO_HINT_SOURCES"] = set(DEFAULT_PROMO_HINT_SOURCES)
    globals()["HEADLINE_EVENT_SOURCES"] = set(DEFAULT_HEADLINE_EVENT_SOURCES)
    globals()["PROMO_EXACT_SOURCES"] = set(DEFAULT_PROMO_EXACT_SOURCES)
    globals()["ITEM_EXACT_SOURCES"] = set(DEFAULT_ITEM_EXACT_SOURCES)
    globals()["HEADLINE_EXACT_SOURCES"] = set(DEFAULT_HEADLINE_EXACT_SOURCES)

    payload = read_json(path)
    if not payload:
        return

    exact_patch_map = dict(EXACT_PATCH_MAP)
    for section in ("badge_micro_1c_exact", "promo_exact", "item_skill_exact", "headline_exact"):
        for source, target in (payload.get(section) or {}).items():
            source_text = normalize_source(str(source))
            target_text = str(target or "").strip()
            if source_text and target_text:
                exact_patch_map[source_text] = target_text
                if section == "promo_exact":
                    globals()["PROMO_EXACT_SOURCES"].add(source_text)
                elif section == "item_skill_exact":
                    globals()["ITEM_EXACT_SOURCES"].add(source_text)
                elif section == "headline_exact":
                    globals()["HEADLINE_EXACT_SOURCES"].add(source_text)

    manual_sources = payload.get("manual_sources")
    if isinstance(manual_sources, list):
        globals()["MANUAL_CREATIVE_SOURCES"] = {normalize_source(item) for item in manual_sources if normalize_source(item)}
    avoid_long_forms = payload.get("avoid_long_forms")
    if isinstance(avoid_long_forms, dict):
        globals()["PATCH_AVOID_LONG_FORMS"] = {
            normalize_source(source): [str(item).strip() for item in values if str(item).strip()]
            for source, values in avoid_long_forms.items()
            if normalize_source(source) and isinstance(values, list)
        }
    promo_sources = payload.get("promo_hint_sources")
    if isinstance(promo_sources, list):
        globals()["PROMO_HINT_SOURCES"] = {normalize_source(item) for item in promo_sources if normalize_source(item)}
    headline_sources = payload.get("headline_event_sources")
    if isinstance(headline_sources, list):
        globals()["HEADLINE_EVENT_SOURCES"] = {normalize_source(item) for item in headline_sources if normalize_source(item)}
    globals()["EXACT_PATCH_MAP"] = exact_patch_map


def hard_issue_map(report: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
    by_id: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for item in report.get("errors") or []:
        sid = str(item.get("string_id") or "")
        if sid:
            by_id[sid].append(item)
    return by_id


def soft_issue_map(report: Dict[str, Any], tasks: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    by_id: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for item in (report.get("hard_gate") or {}).get("violations") or []:
        sid = str(item.get("string_id") or "")
        if sid:
            by_id[sid].append(item)
    for item in tasks:
        sid = str(item.get("string_id") or item.get("id") or "")
        if sid:
            by_id[sid].append(item)
    return by_id


def top_true_residual_sources(assessment: Dict[str, Any]) -> set[str]:
    rows = (((assessment.get("soft_qa") or {}).get("noise_split") or {}).get("true_residual") or {}).get("top_sources") or []
    return {str(item[0]) for item in rows if isinstance(item, list) and item}


def classify_lane(row: Dict[str, str], issue_types: set[str]) -> str:
    normalized = normalize_source(row.get("source_zh", ""))
    category = str(row.get("ui_art_category") or "")
    if normalized in MANUAL_CREATIVE_SOURCES or "ambiguity_high_risk" in issue_types:
        return "creative_title_manual"
    if category == "badge_micro_1c" and (
        "compact_mapping_missing" in issue_types or str(row.get("compact_mapping_status") or "") == "manual_review_required"
    ):
        return "badge_micro_gap_cleanup"
    if (
        category == "slogan_long"
        or normalized in HEADLINE_EVENT_SOURCES
        or "headline_budget_overflow" in issue_types
        or "line_budget_overflow" in issue_types
        or normalized in HEADLINE_EXACT_SOURCES
    ):
        return "headline_slogan_repair"
    if (
        normalized in PROMO_HINT_SOURCES
        or "预览" in normalized
        or category == "promo_short"
        or "promo_expansion_forbidden" in issue_types
    ):
        return "promo_exact_or_compound"
    if normalized in ITEM_EXACT_SOURCES or any(token in normalized for token in ITEM_FAMILY_HINTS):
        return "item_skill_family_compact"
    if category in {"title_name_short", "label_generic_short"}:
        return "headline_slogan_repair"
    return "creative_title_manual"


def repair_hint(row: Dict[str, str], lane: str) -> str:
    source = normalize_source(row.get("source_zh", ""))
    category = str(row.get("ui_art_category") or "")
    if lane == "promo_exact_or_compound":
        if source.endswith("预览"):
            return "Short promo/title repair. Keep only compact preview/header wording; no Превью, no extra explanation."
        return "Compact promo/title repair. Keep qualifier + core noun only."
    if lane == "item_skill_family_compact":
        if source.endswith("试炼"):
            return "Use a compact trial-family title, ideally one short hyphenated or two-word form ending with тест."
        if "之力" in source:
            return "Use a compact 1-2 word power title. Prefer short noun phrase over literal explanation."
        if "之门" in source:
            return "Use a compact gate title, ideally concise '<core> врата'."
        return "Use a compact canonical skill/title form in at most 1-2 content words."
    if lane == "headline_slogan_repair":
        if category == "slogan_long":
            return "Headline-only repair. Keep the same line count as source and do not expand into sentences."
        return "Short title repair. Keep 1-2 content words max and preserve proper nouns."
    if lane == "badge_micro_gap_cleanup":
        return "Exact compact badge form only."
    return "Do not auto-repair unless a safe compact form exists."


def build_patch_glossary_entries(rows: List[Dict[str, str]]) -> List[Dict[str, Any]]:
    entries: List[Dict[str, Any]] = []
    seen = set()
    for row in rows:
        source = normalize_source(row.get("source_zh", ""))
        target = str(row.get("prefill_target_ru") or "").strip()
        if not source or not target or (source, target) in seen:
            continue
        if str(row.get("translation_mode") or "") != "prefill_exact":
            continue
        avoid_long_form = list(PATCH_AVOID_LONG_FORMS.get(source, []))
        current_target = str(row.get("current_target_text") or "").strip()
        if current_target and current_target != target and current_target not in avoid_long_form:
            avoid_long_form.append(current_target)
        entries.append(
            {
                "term_zh": source,
                "term_ru": target,
                "status": "approved",
                "tags": ["ui", "art", "short", "mobile"],
                "preferred_compact": True,
                "avoid_long_form": avoid_long_form,
                "note": "Residual triage exact compact mapping.",
            }
        )
        seen.add((source, target))
    return entries


def build_manifest_rows(
    prepared_rows: List[Dict[str, str]],
    translated_rows: List[Dict[str, str]],
    qa_report: Dict[str, Any],
    soft_report: Dict[str, Any],
    soft_tasks: List[Dict[str, Any]],
    assessment: Dict[str, Any],
) -> Tuple[List[Dict[str, str]], Dict[str, Any]]:
    prepared_map = {str(row.get("string_id") or ""): row for row in prepared_rows}
    translated_map = {str(row.get("string_id") or ""): row for row in translated_rows}
    hard_map = hard_issue_map(qa_report)
    soft_map = soft_issue_map(soft_report, soft_tasks)
    top_sources = top_true_residual_sources(assessment)

    candidate_ids = set(hard_map.keys())
    candidate_ids.update(str(item.get("string_id") or "") for item in (soft_report.get("hard_gate") or {}).get("violations") or [] if str(item.get("string_id") or ""))
    for row in prepared_rows:
        if normalize_source(row.get("source_zh", "")) in top_sources:
            candidate_ids.add(str(row.get("string_id") or ""))

    merged_rows: List[Dict[str, str]] = []
    lane_counts: Counter[str] = Counter()
    mode_counts: Counter[str] = Counter()
    issue_type_counts: Counter[str] = Counter()
    source_counts: Counter[str] = Counter()

    for sid in sorted(candidate_ids):
        prepared = prepared_map.get(sid)
        translated = translated_map.get(sid)
        if not prepared or not translated:
            continue
        source = normalize_source(prepared.get("source_zh", ""))
        hard_items = hard_map.get(sid, [])
        soft_items = soft_map.get(sid, [])
        issue_types = {
            str(item.get("type") or item.get("issue_type") or "").strip()
            for item in [*hard_items, *soft_items]
            if str(item.get("type") or item.get("issue_type") or "").strip()
        }
        if source in top_sources:
            source_counts[source] += 1
        for issue_type in issue_types:
            issue_type_counts[issue_type] += 1

        lane = classify_lane(prepared, issue_types)
        hint = repair_hint(prepared, lane)
        compact_term = EXACT_PATCH_MAP.get(source, str(prepared.get("ui_art_compact_term") or "").strip())
        translation_mode = "llm"
        prefill = ""
        manual_reason = ""
        if lane == "creative_title_manual":
            translation_mode = "manual_hold"
            manual_reason = "creative_or_ambiguous_title"
        elif lane == "badge_micro_gap_cleanup":
            if compact_term:
                translation_mode = "prefill_exact"
                prefill = compact_term
            elif len(str(translated.get("target_text") or translated.get("target_ru") or "").strip()) <= 2:
                translation_mode = "prefill_exact"
                prefill = str(translated.get("target_text") or translated.get("target_ru") or "").strip()
                compact_term = prefill
            else:
                translation_mode = "manual_hold"
                manual_reason = "badge_missing_approved_mapping"
        elif compact_term and source in EXACT_PATCH_MAP:
            translation_mode = "prefill_exact"
            prefill = compact_term
        elif lane == "promo_exact_or_compound" and compact_term and str(prepared.get("ui_art_strategy_hint") or "") == "promo_exact_head":
            translation_mode = "prefill_exact"
            prefill = compact_term

        row_out = dict(translated)
        row_out.update(prepared)
        row_out["current_target_text"] = str(translated.get("target_text") or translated.get("target_ru") or "")
        row_out["residual_lane"] = lane
        row_out["residual_prompt_hint"] = hint
        row_out["translation_mode"] = translation_mode
        row_out["prefill_target_ru"] = prefill
        row_out["ui_art_compact_term"] = compact_term or str(prepared.get("ui_art_compact_term") or "")
        row_out["residual_issue_types"] = "|".join(sorted(issue_types))
        row_out["residual_manual_reason"] = manual_reason
        row_out["residual_priority"] = str(LANE_PRIORITY.get(lane, 99))
        row_out["residual_from_top_true_source"] = "true" if source in top_sources else "false"
        merged_rows.append(row_out)
        lane_counts[lane] += 1
        mode_counts[translation_mode] += 1

    merged_rows.sort(
        key=lambda row: (
            int(row.get("residual_priority") or "99"),
            int(row.get("batch_row_id") or "0"),
        )
    )

    manifest = {
        "candidate_total": len(merged_rows),
        "lane_counts": dict(lane_counts),
        "translation_mode_counts": dict(mode_counts),
        "issue_type_counts": dict(issue_type_counts),
        "top_true_residual_source_hits": source_counts.most_common(20),
    }
    return merged_rows, manifest


def select_fieldnames(rows: List[Dict[str, str]]) -> List[str]:
    fieldnames: List[str] = []
    for row in rows:
        for key in row.keys():
            if key not in fieldnames:
                fieldnames.append(key)
    return fieldnames


def write_patch_glossary(path: Path, entries: List[Dict[str, Any]], source_name: str = "", description: str = "") -> None:
    payload = {
        "meta": {
            "scope": "batch_override",
            "language_pair": "zh-CN->ru-RU",
            "version": 1,
            "source": source_name or path.parent.name or path.stem,
            "description": description or "Batch-local exact compact overrides for a UI-art residual triage slice.",
        },
        "entries": entries,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    if yaml is None:
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return
    path.write_text(yaml.safe_dump(payload, allow_unicode=True, sort_keys=False), encoding="utf-8")


def build_slice(base_run_dir: Path, out_dir: Path, override_path: Path | None = None) -> Dict[str, Any]:
    base_run_dir = Path(base_run_dir)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    if override_path is not None:
        apply_override_asset(Path(override_path))

    prepared_rows, _ = read_csv(base_run_dir / "source_ui_art_prepared.csv")
    translated_rows, _ = read_csv(base_run_dir / "ui_art_translated.csv")
    qa_report = read_json(base_run_dir / "ui_art_qa_hard_report.json")
    soft_report = read_json(base_run_dir / "ui_art_soft_qa_report.json")
    soft_tasks = read_jsonl(base_run_dir / "ui_art_soft_tasks.jsonl")
    assessment = read_json(base_run_dir / "ui_art_full_rerun_assessment.json")

    candidate_rows, manifest = build_manifest_rows(
        prepared_rows=prepared_rows,
        translated_rows=translated_rows,
        qa_report=qa_report,
        soft_report=soft_report,
        soft_tasks=soft_tasks,
        assessment=assessment,
    )

    auto_rows = [row for row in candidate_rows if str(row.get("translation_mode") or "") != "manual_hold"]
    manual_rows = [row for row in candidate_rows if str(row.get("translation_mode") or "") == "manual_hold"]
    patch_glossary_entries = build_patch_glossary_entries(candidate_rows)

    manifest.update(
        {
            "base_run_dir": str(base_run_dir),
            "out_dir": str(out_dir),
            "auto_repair_rows": len(auto_rows),
            "manual_seed_rows": len(manual_rows),
            "patch_glossary_entries": len(patch_glossary_entries),
        }
    )

    candidate_csv = out_dir / "ui_art_residual_candidates.csv"
    repair_input_csv = out_dir / "ui_art_residual_repair_input.csv"
    manual_seed_csv = out_dir / "ui_art_residual_manual_queue_seed.csv"
    manifest_json = out_dir / "ui_art_residual_manifest.json"
    repair_tasks = out_dir / "ui_art_residual_repair_tasks.jsonl"
    patch_glossary = out_dir / "ui_art_residual_patch_glossary.yaml"

    if candidate_rows:
        write_csv(candidate_csv, candidate_rows, select_fieldnames(candidate_rows))
    if auto_rows:
        write_csv(repair_input_csv, auto_rows, select_fieldnames(auto_rows))
    if manual_rows:
        write_csv(manual_seed_csv, manual_rows, select_fieldnames(manual_rows))

    task_items = [
        {
            "string_id": row.get("string_id", ""),
            "source_zh": row.get("source_zh", ""),
            "ui_art_category": row.get("ui_art_category", ""),
            "residual_lane": row.get("residual_lane", ""),
            "translation_mode": row.get("translation_mode", ""),
            "current_target_text": row.get("current_target_text", ""),
            "prefill_target_ru": row.get("prefill_target_ru", ""),
            "residual_prompt_hint": row.get("residual_prompt_hint", ""),
            "residual_issue_types": row.get("residual_issue_types", ""),
            "residual_manual_reason": row.get("residual_manual_reason", ""),
        }
        for row in candidate_rows
    ]
    write_jsonl(repair_tasks, task_items)
    write_json(manifest_json, manifest)
    write_patch_glossary(
        patch_glossary,
        patch_glossary_entries,
        source_name=out_dir.name,
        description="Batch-local exact compact overrides for a UI-art residual triage slice.",
    )
    return manifest


def main() -> int:
    ap = argparse.ArgumentParser(description="Build a UI-art residual triage slice.")
    ap.add_argument("--base-run-dir", default=str(DEFAULT_BASE_RUN_DIR))
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--override-path", default=str(DEFAULT_OVERRIDE_PATH))
    args = ap.parse_args()

    manifest = build_slice(Path(args.base_run_dir), Path(args.out_dir), Path(args.override_path))
    print(f"[OK] Residual candidate rows: {manifest['candidate_total']}")
    print(f"[OK] Auto repair rows: {manifest['auto_repair_rows']}")
    print(f"[OK] Manual seed rows: {manifest['manual_seed_rows']}")
    print(f"[OK] Residual slice manifest -> {Path(args.out_dir) / 'ui_art_residual_manifest.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
