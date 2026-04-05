#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Build a harness-first residual v2 slice on top of a repaired UI-art output.

This builder does not reopen a broad repair surface. It:
- enriches the current residual review queue with repair provenance
- separates manual-only vs auto-fixable vs near-limit rows
- reports family coverage against exact overrides and compact glossary
- prepares one final narrow auto-repair input for repeated low-ambiguity families
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

try:
    from scripts import build_ui_art_residual_slice as residual_v1
except ImportError:  # pragma: no cover
    import build_ui_art_residual_slice as residual_v1


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_BATCH_ROOT = REPO_ROOT / "data" / "incoming" / "ui_art_batch"
DEFAULT_BASE_RUN_DIR = DEFAULT_BATCH_ROOT / "runs" / "ui_art_full_rerun_run01"
DEFAULT_BASE_SLICE_DIR = DEFAULT_BASE_RUN_DIR / "residual_triage_slice01"
DEFAULT_OUT_DIR = DEFAULT_BASE_SLICE_DIR / "residual_v2_slice02"
DEFAULT_OVERRIDE_PATH = DEFAULT_BATCH_ROOT / "residual_patch_overrides.json"
DEFAULT_GLOSSARY_PATH = REPO_ROOT / "glossary" / "approved.yaml"

DEFAULT_MANUAL_AMBIGUITY_SOURCES: set[str] = set()
DEFAULT_HIGH_RISK_LORE_SOURCES: set[str] = set()

MANUAL_AMBIGUITY_SOURCES: set[str] = set(DEFAULT_MANUAL_AMBIGUITY_SOURCES)
HIGH_RISK_LORE_SOURCES: set[str] = set(DEFAULT_HIGH_RISK_LORE_SOURCES)

TITLE_NOUN_KEYWORDS = (
    "商店",
    "商城",
    "战场",
    "战区",
    "对决",
    "排位赛",
    "奖励",
    "召唤",
    "小店",
    "礼包",
    "公告",
)

SAFE_FAMILIES = {
    "trial_family",
    "door_power_family",
    "preview_family",
    "noun_title_family",
    "exact_title_family",
}
NARROW_AUTO_BLOCKER_THRESHOLD = 30


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


def write_jsonl(path: Path, items: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for item in items:
            fh.write(json.dumps(item, ensure_ascii=False) + "\n")


def select_fieldnames(rows: List[Dict[str, Any]]) -> List[str]:
    fieldnames: List[str] = []
    for row in rows:
        for key in row.keys():
            if key not in fieldnames:
                fieldnames.append(key)
    return fieldnames


def normalize_source(text: str) -> str:
    return residual_v1.normalize_source(text)


def apply_override_policy(override_path: Path) -> None:
    globals()["MANUAL_AMBIGUITY_SOURCES"] = set(DEFAULT_MANUAL_AMBIGUITY_SOURCES)
    globals()["HIGH_RISK_LORE_SOURCES"] = set(DEFAULT_HIGH_RISK_LORE_SOURCES)
    payload = read_json(override_path)
    if not payload:
        return
    ambiguity_sources = payload.get("manual_ambiguity_sources")
    if isinstance(ambiguity_sources, list):
        globals()["MANUAL_AMBIGUITY_SOURCES"] = {
            normalize_source(item) for item in ambiguity_sources if normalize_source(item)
        }
    lore_sources = payload.get("high_risk_lore_sources")
    if isinstance(lore_sources, list):
        globals()["HIGH_RISK_LORE_SOURCES"] = {
            normalize_source(item) for item in lore_sources if normalize_source(item)
        }


def load_compact_glossary(glossary_path: Path, override_path: Path) -> Tuple[Dict[str, str], set[str]]:
    exact_map = dict(residual_v1.EXACT_PATCH_MAP)
    payload = read_json(override_path)
    for section in ("badge_micro_1c_exact", "promo_exact", "item_skill_exact", "headline_exact"):
        for source, target in (payload.get(section) or {}).items():
            source_text = normalize_source(str(source))
            target_text = str(target or "").strip()
            if source_text and target_text:
                exact_map[source_text] = target_text

    compact_terms: set[str] = set(exact_map.keys())
    if glossary_path.exists() and yaml is not None:
        data = yaml.safe_load(glossary_path.read_text(encoding="utf-8")) or {}
        for entry in data.get("entries") or []:
            if str(entry.get("status") or "") != "approved":
                continue
            source = normalize_source(str(entry.get("term_zh") or ""))
            target = str(entry.get("term_ru") or "").strip()
            if not source or not target:
                continue
            compact_terms.add(source)
            exact_map.setdefault(source, target)
    return exact_map, compact_terms


def build_issue_map(qa_report: Dict[str, Any], soft_report: Dict[str, Any], soft_tasks: List[Dict[str, Any]]) -> Dict[str, set[str]]:
    issue_map: Dict[str, set[str]] = defaultdict(set)
    for item in qa_report.get("errors") or []:
        sid = str(item.get("string_id") or "")
        issue_type = str(item.get("type") or "").strip()
        if sid and issue_type:
            issue_map[sid].add(issue_type)
    for item in (soft_report.get("hard_gate") or {}).get("violations") or []:
        sid = str(item.get("string_id") or "")
        issue_type = str(item.get("type") or "").strip()
        if sid and issue_type:
            issue_map[sid].add(issue_type)
    for item in soft_tasks:
        sid = str(item.get("string_id") or item.get("id") or "")
        issue_type = str(item.get("type") or item.get("issue_type") or "").strip()
        if sid and issue_type:
            issue_map[sid].add(issue_type)
    return issue_map


def detect_family(source: str) -> str:
    normalized = normalize_source(source)
    if normalized.endswith("试炼"):
        return "trial_family"
    if normalized.endswith("预览"):
        return "preview_family"
    if "之门" in normalized or "之力" in normalized:
        return "door_power_family"
    if normalized in residual_v1.EXACT_PATCH_MAP:
        return "exact_title_family"
    if any(keyword in normalized for keyword in TITLE_NOUN_KEYWORDS):
        return "noun_title_family"
    if "·" in normalized or "・" in normalized:
        return "nameplate_title_family"
    return "singleton_family"


def infer_leakage_origin(row: Dict[str, str], family_key: str) -> str:
    category = str(row.get("ui_art_category") or "")
    previous_lane = str(row.get("residual_lane") or "")
    if category != "title_name_short":
        return ""
    if previous_lane in {"item_skill_family_compact", "promo_exact_or_compound", "headline_slogan_repair"}:
        return previous_lane
    if family_key in {"trial_family", "preview_family", "door_power_family"}:
        return f"{family_key}_into_title_name_short"
    if family_key in {"noun_title_family", "nameplate_title_family"}:
        return "headline_title_leakage"
    return ""


def manual_bucket_for(source: str, category: str, issue_types: set[str]) -> str:
    normalized = normalize_source(source)
    if normalized in residual_v1.MANUAL_CREATIVE_SOURCES:
        return "manual_creative_titles"
    if normalized in MANUAL_AMBIGUITY_SOURCES or "ambiguity_high_risk" in issue_types:
        return "manual_ambiguity_terms"
    if category == "label_generic_short" and {"terminology", "ambiguity_high_risk"} & issue_types:
        return "manual_ambiguity_terms"
    if normalized in HIGH_RISK_LORE_SOURCES and normalized not in residual_v1.EXACT_PATCH_MAP:
        return "manual_ambiguity_terms"
    return ""


def auto_fix_candidate_for(
    row: Dict[str, str],
    family_key: str,
    issue_types: set[str],
    repeated_count: int,
    exact_map: Dict[str, str],
    compact_terms: set[str],
    manual_bucket: str,
) -> bool:
    if manual_bucket:
        return False
    if {"ambiguity_high_risk", "placeholder"} & issue_types:
        return False
    source = normalize_source(row.get("source_zh", ""))
    category = str(row.get("ui_art_category") or "")
    severity = str(row.get("severity") or "")
    if source in exact_map or source in compact_terms:
        return True
    if repeated_count < 2:
        return False
    if family_key not in SAFE_FAMILIES:
        return False
    if category not in {"title_name_short", "item_skill_name", "promo_short", "label_generic_short"}:
        return False
    return severity in {"warning", "major", "critical"}


def narrow_lane_for(row: Dict[str, str], family_key: str) -> str:
    severity = str(row.get("severity") or "")
    if severity == "warning":
        return "warning_family_compact"
    if family_key == "door_power_family" or str(row.get("ui_art_category") or "") == "item_skill_name":
        return "lore_skill_compact"
    return "canonical_title_compact"


def repair_hint_for(source: str, lane: str, family_key: str) -> str:
    normalized = normalize_source(source)
    if lane == "canonical_title_compact":
        if family_key == "trial_family":
            return "Compact short-title repair for repeated trial family. Keep one compact core noun and avoid explanatory wording."
        if family_key == "preview_family":
            return "Compact preview title repair. Keep only the preview head term; no descriptive tail."
        return "Compact canonical title repair. Keep proper nouns, use at most 1-2 content words, no explanation chain."
    if lane == "lore_skill_compact":
        if "之门" in normalized:
            return "Compact lore/title repair for gate-family names. Keep a short canonical core plus врата if needed."
        if "之力" in normalized:
            return "Compact lore/title repair for power-family names. Keep a short canonical power title in 1-2 words."
        return "Compact lore skill/title repair. Preserve canonical lore meaning; no explanatory expansion."
    return "Warning-only compact repair. Shorten carefully without changing meaning."


def enrich_review_rows(
    review_rows: List[Dict[str, str]],
    translated_rows: List[Dict[str, str]],
    qa_report: Dict[str, Any],
    soft_report: Dict[str, Any],
    soft_tasks: List[Dict[str, Any]],
    exact_map: Dict[str, str],
    compact_terms: set[str],
) -> Tuple[List[Dict[str, str]], Dict[str, Any]]:
    translated_map = {str(row.get("string_id") or ""): row for row in translated_rows}
    issue_map = build_issue_map(qa_report, soft_report, soft_tasks)
    source_counter = Counter(normalize_source(row.get("source_zh", "")) for row in review_rows if normalize_source(row.get("source_zh", "")))
    family_counter = Counter()
    manual_counter = Counter()
    auto_fix_counter = Counter()
    blocker_auto_rows = 0

    enriched: List[Dict[str, str]] = []
    for review_row in review_rows:
        sid = str(review_row.get("string_id") or "")
        translated = translated_map.get(sid, {})
        source = normalize_source(review_row.get("source_zh") or translated.get("source_zh") or "")
        family_key = detect_family(source)
        issue_types = issue_map.get(sid, set())
        manual_bucket = manual_bucket_for(source, str(review_row.get("ui_art_category") or translated.get("ui_art_category") or ""), issue_types)
        repeated_count = int(source_counter.get(source, 0))
        auto_fix_candidate = auto_fix_candidate_for(
            review_row,
            family_key,
            issue_types,
            repeated_count,
            exact_map,
            compact_terms,
            manual_bucket,
        )
        narrow_lane = narrow_lane_for(review_row, family_key) if auto_fix_candidate else ""
        current_ru = str(
            translated.get("target_text")
            or translated.get("target_ru")
            or translated.get("target")
            or ""
        )
        enriched_row = dict(review_row)
        enriched_row["source_zh"] = source or str(review_row.get("source_zh") or "")
        enriched_row["current_ru"] = current_ru
        enriched_row["residual_lane"] = str(translated.get("residual_lane") or "")
        enriched_row["ui_art_strategy_hint"] = str(translated.get("ui_art_strategy_hint") or "")
        enriched_row["translation_mode"] = str(translated.get("translation_mode") or "")
        enriched_row["residual_issue_types"] = "|".join(sorted(issue_types))
        enriched_row["manual_bucket"] = manual_bucket
        enriched_row["auto_fix_candidate"] = "true" if auto_fix_candidate else "false"
        enriched_row["title_headline_leakage_origin"] = infer_leakage_origin(translated or review_row, family_key)
        enriched_row["family_key"] = family_key
        enriched_row["repeated_source_count"] = str(repeated_count)
        enriched_row["exact_patch_covered"] = "true" if source in exact_map else "false"
        enriched_row["compact_glossary_covered"] = "true" if source in compact_terms else "false"
        enriched_row["narrow_lane"] = narrow_lane
        enriched_row["repair_hint_v2"] = repair_hint_for(source, narrow_lane, family_key) if narrow_lane else ""
        enriched.append(enriched_row)

        family_counter[family_key] += 1
        if manual_bucket:
            manual_counter[manual_bucket] += 1
        if auto_fix_candidate:
            auto_fix_counter[narrow_lane] += 1
            if str(review_row.get("severity") or "") in {"major", "critical"}:
                blocker_auto_rows += 1

    manifest = {
        "review_queue_total": len(review_rows),
        "family_counts": dict(family_counter),
        "manual_bucket_counts": dict(manual_counter),
        "auto_fix_lane_counts": dict(auto_fix_counter),
        "auto_fix_blocker_rows": blocker_auto_rows,
        "distinct_repeated_sources": sum(1 for _, count in source_counter.items() if count >= 2),
        "justified_for_narrow_auto": blocker_auto_rows >= NARROW_AUTO_BLOCKER_THRESHOLD,
        "narrow_auto_threshold": NARROW_AUTO_BLOCKER_THRESHOLD,
    }
    return enriched, manifest


def build_family_coverage_diff(
    enriched_rows: List[Dict[str, str]],
    exact_map: Dict[str, str],
    compact_terms: set[str],
) -> Dict[str, Any]:
    grouped: Dict[str, Dict[str, Any]] = {}
    for row in enriched_rows:
        source = normalize_source(row.get("source_zh", ""))
        if not source:
            continue
        group = grouped.setdefault(
            source,
            {
                "source_zh": source,
                "total_rows": 0,
                "categories": Counter(),
                "reasons": Counter(),
                "family_key": row.get("family_key", ""),
                "manual_bucket": row.get("manual_bucket", ""),
                "auto_fix_candidate_rows": 0,
                "blocker_rows": 0,
                "current_targets": Counter(),
            },
        )
        group["total_rows"] += 1
        group["categories"][str(row.get("ui_art_category") or "")] += 1
        group["reasons"][str(row.get("reason") or "")] += 1
        group["current_targets"][str(row.get("current_ru") or "")] += 1
        if str(row.get("auto_fix_candidate") or "") == "true":
            group["auto_fix_candidate_rows"] += 1
        if str(row.get("severity") or "") in {"major", "critical"}:
            group["blocker_rows"] += 1

    repeated_rows: List[Dict[str, Any]] = []
    uncovered_candidates: List[Dict[str, Any]] = []
    for source, item in grouped.items():
        if int(item["total_rows"]) < 2:
            continue
        exact_covered = source in exact_map
        compact_covered = source in compact_terms
        unique_targets = [target for target in item["current_targets"].keys() if target]
        row = {
            "source_zh": source,
            "total_rows": int(item["total_rows"]),
            "blocker_rows": int(item["blocker_rows"]),
            "family_key": str(item["family_key"]),
            "manual_bucket": str(item["manual_bucket"]),
            "auto_fix_candidate_rows": int(item["auto_fix_candidate_rows"]),
            "exact_patch_covered": exact_covered,
            "compact_glossary_covered": compact_covered,
            "category_counts": dict(item["categories"]),
            "reason_counts": dict(item["reasons"]),
            "unique_current_targets": unique_targets[:6],
            "recommended_action": (
                "manual"
                if item["manual_bucket"]
                else "deterministic"
                if exact_covered or compact_covered
                else "llm_narrow"
                if str(item["family_key"]) in SAFE_FAMILIES
                else "observe"
            ),
        }
        repeated_rows.append(row)
        if (
            row["recommended_action"] == "llm_narrow"
            and row["auto_fix_candidate_rows"] > 0
            and row["blocker_rows"] > 0
        ):
            uncovered_candidates.append(row)

    repeated_rows.sort(key=lambda row: (-int(row["blocker_rows"]), -int(row["total_rows"]), str(row["source_zh"])))
    uncovered_candidates.sort(key=lambda row: (-int(row["blocker_rows"]), -int(row["auto_fix_candidate_rows"]), str(row["source_zh"])))
    return {
        "repeated_residual_sources": repeated_rows,
        "uncovered_repeated_family_candidates": uncovered_candidates,
    }


def family_coverage_markdown(payload: Dict[str, Any]) -> str:
    lines = [
        "# UI Art Residual V2 Family Coverage Diff",
        "",
        "## Top Repeated Residual Sources",
        "| Source | Rows | Blockers | Family | Action | Exact | Compact |",
        "|---|---:|---:|---|---|---|---|",
    ]
    for row in payload.get("repeated_residual_sources", [])[:25]:
        lines.append(
            f"| {row['source_zh']} | {row['total_rows']} | {row['blocker_rows']} | {row['family_key']} | "
            f"{row['recommended_action']} | {row['exact_patch_covered']} | {row['compact_glossary_covered']} |"
        )
    lines.extend(
        [
            "",
            "## Uncovered Repeated Family Candidates",
            "```json",
            json.dumps(payload.get("uncovered_repeated_family_candidates", [])[:20], ensure_ascii=False, indent=2),
            "```",
        ]
    )
    return "\n".join(lines) + "\n"


def build_v2_slice(base_run_dir: Path, base_slice_dir: Path, out_dir: Path, override_path: Path, glossary_path: Path) -> Dict[str, Any]:
    base_run_dir = Path(base_run_dir)
    base_slice_dir = Path(base_slice_dir)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    residual_v1.apply_override_asset(Path(override_path))
    apply_override_policy(Path(override_path))
    exact_map, compact_terms = load_compact_glossary(Path(glossary_path), Path(override_path))
    translated_rows, _ = read_csv(base_slice_dir / "ui_art_translated_repaired.csv")
    review_rows, _ = read_csv(base_slice_dir / "ui_art_residual_review_queue.csv")
    qa_report = read_json(base_slice_dir / "ui_art_qa_hard_report.json")
    soft_report = read_json(base_slice_dir / "ui_art_soft_qa_report.json")
    soft_tasks = read_jsonl(base_slice_dir / "ui_art_soft_tasks.jsonl")

    enriched_rows, separation_manifest = enrich_review_rows(
        review_rows=review_rows,
        translated_rows=translated_rows,
        qa_report=qa_report,
        soft_report=soft_report,
        soft_tasks=soft_tasks,
        exact_map=exact_map,
        compact_terms=compact_terms,
    )
    coverage_diff = build_family_coverage_diff(enriched_rows, exact_map, compact_terms)

    blocker_rows = [row for row in enriched_rows if str(row.get("severity") or "") in {"major", "critical"}]
    warning_rows = [row for row in enriched_rows if str(row.get("severity") or "") == "warning"]
    manual_creative = [row for row in enriched_rows if str(row.get("manual_bucket") or "") == "manual_creative_titles"]
    manual_ambiguity = [row for row in enriched_rows if str(row.get("manual_bucket") or "") == "manual_ambiguity_terms"]
    auto_fix_rows = [row for row in enriched_rows if str(row.get("auto_fix_candidate") or "") == "true"]

    repair_rows: List[Dict[str, str]] = []
    patch_entries: List[Dict[str, Any]] = []
    for row in auto_fix_rows:
        source = normalize_source(row.get("source_zh", ""))
        current_ru = str(row.get("current_ru") or "")
        compact_term = exact_map.get(source, "")
        translation_mode = "prefill_exact" if compact_term else "llm"
        prefill_target = compact_term
        repaired = dict(row)
        repaired["source_text"] = source
        repaired["current_target_text"] = current_ru
        repaired["translation_mode"] = translation_mode
        repaired["prefill_target_ru"] = prefill_target
        repaired["residual_lane"] = str(row.get("narrow_lane") or "")
        repaired["residual_prompt_hint"] = str(row.get("repair_hint_v2") or "")
        repair_rows.append(repaired)
        if translation_mode == "prefill_exact" and compact_term:
            patch_entries.append(
                {
                    "term_zh": source,
                    "term_ru": compact_term,
                    "status": "approved",
                    "tags": ["ui", "art", "short", "mobile"],
                    "preferred_compact": True,
                    "avoid_long_form": [current_ru] if current_ru and current_ru != compact_term else [],
                    "note": "Residual V2 exact compact mapping.",
                }
            )

    outputs = {
        "enriched_review_queue": out_dir / "ui_art_residual_v2_review_queue_enriched.csv",
        "blocker_rows": out_dir / "ui_art_residual_v2_blocker_rows.csv",
        "near_limit_rows": out_dir / "ui_art_residual_v2_near_limit_nonblocking.csv",
        "manual_creative": out_dir / "ui_art_residual_v2_manual_creative_titles.csv",
        "manual_ambiguity": out_dir / "ui_art_residual_v2_manual_ambiguity_terms.csv",
        "auto_fix_rows": out_dir / "ui_art_residual_v2_auto_fixable_repeated_titles.csv",
        "repair_input": out_dir / "ui_art_residual_v2_repair_input.csv",
        "repair_tasks": out_dir / "ui_art_residual_v2_repair_tasks.jsonl",
        "patch_glossary": out_dir / "ui_art_residual_v2_patch_glossary.yaml",
        "coverage_json": out_dir / "ui_art_residual_v2_family_coverage_diff.json",
        "coverage_md": out_dir / "ui_art_residual_v2_family_coverage_diff.md",
        "manifest": out_dir / "ui_art_residual_v2_manifest.json",
    }

    write_csv(outputs["enriched_review_queue"], enriched_rows, select_fieldnames(enriched_rows))
    write_csv(outputs["blocker_rows"], blocker_rows, select_fieldnames(blocker_rows))
    write_csv(outputs["near_limit_rows"], warning_rows, select_fieldnames(warning_rows))
    if manual_creative:
        write_csv(outputs["manual_creative"], manual_creative, select_fieldnames(manual_creative))
    if manual_ambiguity:
        write_csv(outputs["manual_ambiguity"], manual_ambiguity, select_fieldnames(manual_ambiguity))
    if auto_fix_rows:
        write_csv(outputs["auto_fix_rows"], auto_fix_rows, select_fieldnames(auto_fix_rows))
    if repair_rows:
        write_csv(outputs["repair_input"], repair_rows, select_fieldnames(repair_rows))
    write_jsonl(
        outputs["repair_tasks"],
        [
            {
                "string_id": row.get("string_id", ""),
                "source_zh": row.get("source_zh", ""),
                "current_target_text": row.get("current_target_text", ""),
                "narrow_lane": row.get("residual_lane", ""),
                "manual_bucket": row.get("manual_bucket", ""),
                "family_key": row.get("family_key", ""),
                "translation_mode": row.get("translation_mode", ""),
                "prefill_target_ru": row.get("prefill_target_ru", ""),
                "repair_hint_v2": row.get("residual_prompt_hint", ""),
            }
            for row in repair_rows
        ],
    )
    residual_v1.write_patch_glossary(outputs["patch_glossary"], patch_entries)
    write_json(outputs["coverage_json"], coverage_diff)
    outputs["coverage_md"].write_text(family_coverage_markdown(coverage_diff), encoding="utf-8")

    manifest = {
        "base_run_dir": str(base_run_dir),
        "base_slice_dir": str(base_slice_dir),
        "out_dir": str(out_dir),
        "review_queue_total": len(enriched_rows),
        "blocker_rows": len(blocker_rows),
        "warning_rows": len(warning_rows),
        "manual_creative_rows": len(manual_creative),
        "manual_ambiguity_rows": len(manual_ambiguity),
        "auto_fix_candidate_rows": len(auto_fix_rows),
        "repair_input_rows": len(repair_rows),
        "patch_glossary_entries": len(patch_entries),
        "justified_for_narrow_auto": bool(separation_manifest["justified_for_narrow_auto"]),
        "narrow_auto_threshold": int(separation_manifest["narrow_auto_threshold"]),
        "separation": separation_manifest,
        "coverage_summary": {
            "repeated_residual_sources": len(coverage_diff["repeated_residual_sources"]),
            "uncovered_repeated_family_candidates": len(coverage_diff["uncovered_repeated_family_candidates"]),
        },
    }
    write_json(outputs["manifest"], manifest)
    return manifest


def main() -> int:
    ap = argparse.ArgumentParser(description="Build a UI-art residual v2 slice.")
    ap.add_argument("--base-run-dir", default=str(DEFAULT_BASE_RUN_DIR))
    ap.add_argument("--base-slice-dir", default=str(DEFAULT_BASE_SLICE_DIR))
    ap.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    ap.add_argument("--override-path", default=str(DEFAULT_OVERRIDE_PATH))
    ap.add_argument("--glossary-path", default=str(DEFAULT_GLOSSARY_PATH))
    args = ap.parse_args()

    manifest = build_v2_slice(
        base_run_dir=Path(args.base_run_dir),
        base_slice_dir=Path(args.base_slice_dir),
        out_dir=Path(args.out_dir),
        override_path=Path(args.override_path),
        glossary_path=Path(args.glossary_path),
    )
    print(f"[OK] Residual V2 blocker rows: {manifest['blocker_rows']}")
    print(f"[OK] Residual V2 auto-fix rows: {manifest['auto_fix_candidate_rows']}")
    print(f"[OK] Justified for narrow auto: {manifest['justified_for_narrow_auto']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
