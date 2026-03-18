#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Generate M4-4 cleanup decisions from M4-3 outputs + recent run manifests."""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional


CORE_STAGES = {
    "Connectivity": "scripts/llm_ping.py",
    "Normalize": "scripts/normalize_guard.py",
    "Translate": "scripts/translate_llm.py",
    "QA Hard": "scripts/qa_hard.py",
    "Rehydrate": "scripts/rehydrate_export.py",
    "Smoke Verify": "scripts/smoke_verify.py",
}


def _safe_load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _safe_load_jsonl(path: Path) -> List[dict]:
    if not path.exists():
        return []
    items: List[dict] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                items.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return items


def _stage_to_script(stage_name: str) -> Optional[str]:
    normalized = (stage_name or "").strip().lower()
    normalized = re.sub(r"\([^)]*\)", "", normalized).strip()
    normalized = re.sub(r"\s+", " ", normalized)
    for key, script in CORE_STAGES.items():
        if key.lower() in normalized:
            return script
    if normalized == "qa hard":
        return "scripts/qa_hard.py"
    if normalized == "smoke verify":
        return "scripts/smoke_verify.py"
    if "translate" in stage_name.lower():
        return "scripts/translate_llm.py"
    if "qa" in stage_name.lower():
        return "scripts/qa_hard.py"
    if "rehydrat" in stage_name.lower():
        return "scripts/rehydrate_export.py"
    if "verify" in stage_name.lower():
        return "scripts/smoke_verify.py"
    return None


def _collect_recent_manifests(smoke_runs_dir: Path, prefix: str, limit: int) -> List[Path]:
    entries: List[Path] = []
    for d in smoke_runs_dir.iterdir():
        if not d.is_dir() or not d.name.startswith(prefix):
            continue
        manifest = d / "run_manifest.json"
        if manifest.exists():
            entries.append(manifest)

    def _sort_key(manifest_path: Path) -> str:
        manifest = _safe_load_json(manifest_path)
        return manifest.get("timestamp", "") or manifest_path.parent.name

    entries.sort(key=_sort_key, reverse=True)
    return entries[:limit]


def _load_issues_for_run(run_dir: Path) -> List[dict]:
    jsonl = run_dir / "smoke_issues.jsonl"
    if jsonl.exists():
        return _safe_load_jsonl(jsonl)

    json_report = run_dir / "smoke_issues.json"
    report = _safe_load_json(json_report)
    return report.get("issues", []) if isinstance(report, dict) else []


def _run_id_from_manifest(path: Path) -> str:
    return _safe_load_json(path).get("run_id", path.parent.name) or path.parent.name


def _build_decisions_from_m4_3(
    coverage: List[dict],
    issue_hotspots: List[dict],
    manifests: List[Path],
    run_window: int,
) -> List[dict]:
    recent_runs = [(m, _safe_load_json(m)) for m in manifests[:run_window]]

    # Script touch matrix
    script_touch: Dict[str, set] = {}
    for manifest_path, manifest in recent_runs:
        run_id = manifest.get("run_id", manifest_path.parent.name)
        for stage in manifest.get("stages", []) or []:
            script = _stage_to_script(stage.get("name", ""))
            if not script:
                continue
            script_touch.setdefault(script, set()).add(run_id)

    # 补齐：M4-3 覆盖文件中的脚本
    for entry in coverage:
        if not isinstance(entry, dict):
            continue
        if entry.get("type") != "stage_coverage":
            continue
        script = entry.get("script")
        if isinstance(script, str) and script:
            # stage_coverage 已是本地统计的 0/1 触达结果，不再重复计数
            script_touch.setdefault(script, set())
            if isinstance(entry.get("touch_count"), int) and entry.get("touch_count", 0) > 0:
                for rid in entry.get("touched_run_ids", []) or []:
                    script_touch[script].add(str(rid))

    latest_run_ids: List[str] = []
    for manifest_path, manifest in recent_runs:
        if manifest:
            latest_run_ids.append(manifest.get("run_id", manifest_path.parent.name))
    latest_run_ids = [rid for rid in latest_run_ids if rid]

    # Hotspot summary
    p0_scripts = set()
    repair_scripts = set()
    for hs in issue_hotspots:
        if not isinstance(hs, dict):
            continue
        severity = str(hs.get("severity", "")).upper()
        stage = hs.get("stage", "")
        run_ids = hs.get("run_ids", []) or []
        if not stage:
            continue
        script = _stage_to_script(str(stage))
        if not script:
            continue
        if severity in {"P0"}:
            p0_scripts.add(script)
        elif severity in {"P1", "P2"}:
            repair_scripts.add(script)
        elif run_ids:
            repair_scripts.add(script)

    decisions: List[dict] = []
    all_scripts = set(script_touch.keys())
    all_scripts.update(CORE_STAGES.values())

    core_scripts = set(CORE_STAGES.values())
    for script in sorted(all_scripts):
        touched_run_count = len(script_touch.get(script, set()))
        touched_recent = [rid for rid in latest_run_ids if rid in script_touch.get(script, set())]
        if script in p0_scripts:
            decision = "BLOCK"
            reason = "P0 issue hotspot observed in M4-3."
        elif script in repair_scripts and touched_recent:
            decision = "REWORK"
            reason = "P1/P2 issue hotspot observed; keep in main for immediate follow-up."
        elif script in core_scripts:
            decision = "KEEP"
            reason = "Core stage script required by smoke pipeline."
        elif touched_recent:
            decision = "KEEP"
            reason = "Touched in recent 3 full runs; keep for validation before cleanup."
        elif touched_run_count == 0:
            decision = "OBSOLETE"
            reason = "Not reached in recent 3 full runs and not core."
        else:
            decision = "OBSOLETE"
            reason = "Low/zero reachability in recent 3 full runs."

        decisions.append({
            "type": "m4_4_decision",
            "script": script,
            "decision": decision,
            "reason": reason,
            "scope": f"latest_{run_window}_full_runs",
            "touch_count": touched_run_count,
            "touched_in_recent_runs": touched_recent,
            "first_seen_run_id": latest_run_ids[-1] if latest_run_ids else "",
            "last_seen_run_id": max(script_touch.get(script, {""})) if script_touch.get(script) else "",
        })

    decisions.sort(key=lambda d: (d["decision"], d["script"]))
    return decisions


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate M4-4 cleanup decision table.")
    repo_root = Path(__file__).resolve().parents[1]
    default_runs_dir = repo_root / "data" / "smoke_runs"
    parser.add_argument("--smoke-runs-dir", default=str(default_runs_dir), help="Directory containing run artifacts.")
    parser.add_argument("--coverage-jsonl", default=str(default_runs_dir / "M4_3_coverage_report.jsonl"), help="Path to M4-3 coverage report.")
    parser.add_argument("--issue-hotspots-jsonl", default=str(default_runs_dir / "M4_3_issue_hotspots.jsonl"), help="Path to M4-3 issue hotspots.")
    parser.add_argument("--run-prefix", default="manual_1000_full_", help="Prefix for latest full run dirs.")
    parser.add_argument("--run-window", type=int, default=3, help="How many latest full runs to consider.")
    parser.add_argument("--out", default=str(default_runs_dir / "M4_4_decision.jsonl"), help="Output JSONL path.")
    args = parser.parse_args()

    runs_dir = Path(args.smoke_runs_dir)
    coverage = _safe_load_jsonl(Path(args.coverage_jsonl))
    issue_hotspots = _safe_load_jsonl(Path(args.issue_hotspots_jsonl))
    manifests = _collect_recent_manifests(runs_dir, args.run_prefix, args.run_window)

    decisions = _build_decisions_from_m4_3(coverage, issue_hotspots, manifests, args.run_window)
    summary = {
        "type": "m4_4_decision_summary",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "scope": f"latest_{args.run_window}_full_runs",
        "run_manifest_paths": [str(p) for p in manifests],
        "runs_considered": len(manifests),
        "decision_counts": {
            "KEEP": sum(1 for item in decisions if item["decision"] == "KEEP"),
            "BLOCK": sum(1 for item in decisions if item["decision"] == "BLOCK"),
            "REWORK": sum(1 for item in decisions if item["decision"] == "REWORK"),
            "OBSOLETE": sum(1 for item in decisions if item["decision"] == "OBSOLETE"),
        },
        "input_files": {
            "coverage": str(args.coverage_jsonl),
            "issue_hotspots": str(args.issue_hotspots_jsonl),
        },
    }

    out_path = Path(args.out)
    with out_path.open("w", encoding="utf-8") as f:
        f.write(json.dumps(summary, ensure_ascii=False) + "\n")
        for d in decisions:
            f.write(json.dumps(d, ensure_ascii=False) + "\n")

    print(f"Wrote {len(decisions)} decisions -> {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
