#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from review_governance import read_json, read_jsonl, write_json, write_jsonl

try:
    import yaml
except Exception:  # pragma: no cover
    yaml = None


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_ADR_REFS = [
    "docs/decisions/ADR-0001-project-continuity-framework.md",
    "docs/decisions/ADR-0002-skill-governance-framework.md",
    "docs/decisions/ADR-0003-operator-control-plane-operating-model.md",
]
OPEN_REVIEW_STATUSES = {"pending", "acknowledged", "in_review"}
WINDOWS_ABSOLUTE_RE = re.compile(r"^[A-Za-z]:[\\/]")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_yaml_dict(path: str, default: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    if yaml is None:
        return dict(default or {})
    file_path = Path(path)
    if not file_path.is_absolute():
        file_path = REPO_ROOT / file_path
    if not file_path.exists():
        return dict(default or {})
    try:
        loaded = yaml.safe_load(file_path.read_text(encoding="utf-8")) or {}
    except Exception:
        return dict(default or {})
    return loaded if isinstance(loaded, dict) else dict(default or {})


def load_operator_card_contract() -> Dict[str, Any]:
    return _load_yaml_dict("workflow/operator_card_contract.yaml", {})


def _looks_like_windows_absolute(path: str) -> bool:
    return bool(WINDOWS_ABSOLUTE_RE.match(str(path or "").strip()))


def _resolve_path(path: str, *, base: Optional[Path] = None) -> Optional[Path]:
    text = str(path or "").strip()
    if not text:
        return None
    if _looks_like_windows_absolute(text):
        if base is not None:
            localized = (base / Path(text.replace("\\", "/")).name).resolve()
            if localized.exists():
                return localized
        return Path(text)
    raw = Path(text)
    if raw.is_absolute():
        return raw
    if base is not None:
        candidate = (base / raw).resolve()
        if candidate.exists():
            return candidate
    return (REPO_ROOT / raw).resolve()


def _first_existing(paths: Iterable[str], *, base: Path) -> Optional[Path]:
    for item in paths:
        candidate = _resolve_path(item, base=base)
        if candidate and candidate.exists():
            return candidate
    return None


def _find_verify_report(run_dir: Path, manifest: Dict[str, Any]) -> Tuple[Optional[Path], Dict[str, Any]]:
    artifacts = manifest.get("artifacts", {}) or {}
    verify_path = _first_existing(
        [
            str(artifacts.get("smoke_verify_json") or ""),
            str(artifacts.get("verify_report_json") or ""),
        ],
        base=run_dir,
    )
    if verify_path is None:
        matches = sorted(run_dir.glob("smoke_verify_*.json"))
        verify_path = matches[-1] if matches else None
    return verify_path, read_json(str(verify_path)) if verify_path else {}


def _ticket_paths(run_dir: Path, manifest: Dict[str, Any]) -> Tuple[Optional[Path], Optional[Path]]:
    artifacts = manifest.get("artifacts", {}) or {}
    ticket_path = _first_existing(
        [
            str(artifacts.get("smoke_review_tickets_jsonl") or ""),
            str(artifacts.get("review_tickets_jsonl") or ""),
        ],
        base=run_dir,
    )
    feedback_path = _first_existing(
        [
            str(artifacts.get("smoke_feedback_log_jsonl") or ""),
            str(artifacts.get("feedback_log_jsonl") or ""),
        ],
        base=run_dir,
    )
    return ticket_path, feedback_path


def _kpi_path(run_dir: Path, manifest: Dict[str, Any]) -> Optional[Path]:
    artifacts = manifest.get("artifacts", {}) or {}
    return _first_existing(
        [
            str(artifacts.get("smoke_governance_kpi_json") or ""),
            str(artifacts.get("kpi_report_json") or ""),
        ],
        base=run_dir,
    )


def _canonical_status(manifest: Dict[str, Any], verify_payload: Dict[str, Any]) -> str:
    verify_status = str(verify_payload.get("overall") or verify_payload.get("status") or "").strip().upper()
    if verify_status in {"PASS", "WARN", "BLOCKED", "FAILED", "FAIL"}:
        return {"PASS": "pass", "WARN": "warn", "BLOCKED": "blocked", "FAILED": "failed", "FAIL": "failed"}[verify_status]
    return str(manifest.get("overall_status") or manifest.get("status") or "unknown").strip().lower() or "unknown"


def _runtime_health_title(status: str) -> str:
    mapping = {
        "pass": "Runtime passed",
        "warn": "Runtime completed with warnings",
        "blocked": "Runtime blocked",
        "failed": "Runtime failed",
    }
    return mapping.get(status, f"Runtime status: {status}")


def _recommended_actions_for_status(status: str) -> List[str]:
    if status == "failed":
        return ["inspect blocking stage", "rerun after fixing runtime failure"]
    if status == "blocked":
        return ["inspect blocked gates", "resolve review or governance blockers"]
    if status == "warn":
        return ["inspect warning-producing stages", "confirm no manual follow-up is needed"]
    return ["archive run evidence", "continue to the next planned scope"]


def _review_ticket_card(ticket: Dict[str, Any], *, run_id: str, owner: str, artifact_refs: Dict[str, str], adr_refs: List[str]) -> Dict[str, Any]:
    review_status = str(ticket.get("review_status") or "pending")
    is_open = review_status in OPEN_REVIEW_STATUSES
    reason_codes = ticket.get("reason_codes") or []
    summary = f"{ticket.get('queue_reason') or 'manual review required'}"
    if reason_codes:
        summary = f"{summary}; reason_codes={','.join(str(code) for code in reason_codes)}"
    return {
        "card_id": f"card:{ticket.get('ticket_id')}",
        "card_type": "review_ticket",
        "status": "open" if is_open else "closed",
        "priority": str(ticket.get("priority") or "P2"),
        "title": f"Review ticket {ticket.get('string_id') or ticket.get('ticket_id')}",
        "summary": summary,
        "run_id": run_id,
        "target_locale": str(ticket.get("target_locale") or "unknown"),
        "artifact_refs": artifact_refs,
        "evidence_refs": [artifact_refs.get("manifest", ""), artifact_refs.get("review_tickets", "")],
        "adr_refs": adr_refs,
        "recommended_actions": ["assign reviewer", "record feedback decision"] if is_open else ["confirm ticket closure"],
        "owner": str(ticket.get("review_owner") or owner),
    }


def validate_operator_cards(cards: List[Dict[str, Any]]) -> None:
    contract = load_operator_card_contract()
    required_fields = contract.get("required_fields", []) or []
    card_type_enum = set(contract.get("card_type_enum", []) or [])
    status_enum = set(contract.get("status_enum", []) or [])
    priority_enum = set(contract.get("priority_enum", []) or [])
    for card in cards:
        missing = [field for field in required_fields if card.get(field) in (None, "", [])]
        if missing:
            raise ValueError(f"Operator card missing required field(s): {', '.join(missing)}")
        if card_type_enum and card["card_type"] not in card_type_enum:
            raise ValueError(f"Unsupported operator card type: {card['card_type']}")
        if status_enum and card["status"] not in status_enum:
            raise ValueError(f"Unsupported operator card status: {card['status']}")
        if priority_enum and card["priority"] not in priority_enum:
            raise ValueError(f"Unsupported operator card priority: {card['priority']}")


def _summary_md(report: Dict[str, Any]) -> str:
    lines = [
        "# Operator Summary",
        "",
        f"- generated_at: `{report['generated_at']}`",
        f"- run_id: `{report['run_id']}`",
        f"- overall_runtime_health: `{report['overall_runtime_health']['status']}`",
        f"- open_operator_cards: `{report['open_operator_cards']}`",
        "",
        "## Review Workload",
        f"- total_review_tickets: `{report['open_review_workload']['total_review_tickets']}`",
        f"- pending_review_tickets: `{report['open_review_workload']['pending_review_tickets']}`",
        "",
        "## Governance Drift",
        f"- drift_count: `{report['governance_drift_summary']['drift_count']}`",
        "",
        "## KPI Snapshot",
        f"- manual_intervention_rate: `{report['kpi_snapshot']['manual_intervention_rate']}`",
        f"- feedback_closure_rate: `{report['kpi_snapshot']['feedback_closure_rate']}`",
        "",
        "## Next Recommended Actions",
    ]
    for action in report["next_recommended_actions"]:
        lines.append(f"- `{action}`")
    lines.extend(["", "## Artifact Refs"])
    for label, path in report["artifact_refs"].items():
        lines.append(f"- `{label}`: `{path}`")
    lines.extend(["", "## Evidence Refs"])
    for ref in report["evidence_refs"]:
        lines.append(f"- `{ref}`")
    lines.extend(["", "## ADR Refs"])
    for ref in report["adr_refs"]:
        lines.append(f"- `{ref}`")
    return "\n".join(lines) + "\n"


def build_operator_artifacts(
    *,
    run_dir: str,
    owner: str = "Codex",
    adr_refs: Optional[List[str]] = None,
) -> Dict[str, Any]:
    run_path = Path(run_dir).resolve()
    manifest_path = run_path / "run_manifest.json"
    manifest = read_json(str(manifest_path))
    if not manifest:
        raise FileNotFoundError(f"run manifest missing: {manifest_path}")

    run_id = str(manifest.get("run_id") or run_path.name)
    verify_path, verify_payload = _find_verify_report(run_path, manifest)
    ticket_path, feedback_path = _ticket_paths(run_path, manifest)
    kpi_path = _kpi_path(run_path, manifest)
    review_tickets = read_jsonl(str(ticket_path)) if ticket_path else []
    feedback_logs = read_jsonl(str(feedback_path)) if feedback_path else []
    kpi_payload = read_json(str(kpi_path)) if kpi_path else {}

    cards_dir = REPO_ROOT / "data" / "operator_cards" / run_id
    reports_dir = REPO_ROOT / "data" / "operator_reports" / run_id
    cards_path = cards_dir / "operator_cards.jsonl"
    summary_json_path = reports_dir / "operator_summary.json"
    summary_md_path = reports_dir / "operator_summary.md"

    artifact_refs = {
        "manifest": str(manifest_path),
        "verify_report": str(verify_path) if verify_path else "",
        "review_tickets": str(ticket_path) if ticket_path else "",
        "feedback_log": str(feedback_path) if feedback_path else "",
        "kpi_report": str(kpi_path) if kpi_path else "",
        "operator_cards": str(cards_path),
        "operator_summary_json": str(summary_json_path),
        "operator_summary_md": str(summary_md_path),
    }
    evidence_refs = [path for path in [artifact_refs["manifest"], artifact_refs["verify_report"], artifact_refs["kpi_report"], artifact_refs["review_tickets"]] if path]
    effective_adr_refs = [ref for ref in (adr_refs or DEFAULT_ADR_REFS) if ref]

    cards: List[Dict[str, Any]] = []
    for ticket in review_tickets:
        cards.append(_review_ticket_card(ticket, run_id=run_id, owner=owner, artifact_refs=artifact_refs, adr_refs=effective_adr_refs))

    canonical_status = _canonical_status(manifest, verify_payload)
    if canonical_status in {"warn", "blocked", "failed"}:
        cards.append(
            {
                "card_id": f"card:runtime_alert:{run_id}",
                "card_type": "runtime_alert",
                "status": "open",
                "priority": "P0" if canonical_status in {"blocked", "failed"} else "P1",
                "title": _runtime_health_title(canonical_status),
                "summary": f"Manifest/verify resolved runtime health to {canonical_status}.",
                "run_id": run_id,
                "target_locale": str(manifest.get("target_lang") or "unknown"),
                "artifact_refs": artifact_refs,
                "evidence_refs": evidence_refs,
                "adr_refs": effective_adr_refs,
                "recommended_actions": _recommended_actions_for_status(canonical_status),
                "owner": owner,
            }
        )

    drift_reasons: List[str] = []
    kpi_runtime_status = str(((kpi_payload.get("runtime_summary") or {}).get("overall_status")) or "").strip().lower()
    if kpi_runtime_status and kpi_runtime_status != canonical_status:
        drift_reasons.append(f"kpi runtime_summary.overall_status={kpi_runtime_status} != canonical_status={canonical_status}")
    deprecated_count = int(((kpi_payload.get("lifecycle_summary") or {}).get("deprecated_asset_usage_count")) or 0)
    if deprecated_count > 0:
        drift_reasons.append(f"deprecated_asset_usage_count={deprecated_count}")
    runtime_governance = manifest.get("runtime_governance", {}) or {}
    if runtime_governance and runtime_governance.get("passed") is False:
        drift_reasons.append("runtime governance reported failed")
    if drift_reasons:
        cards.append(
            {
                "card_id": f"card:governance_drift:{run_id}",
                "card_type": "governance_drift",
                "status": "open",
                "priority": "P1",
                "title": "Governance drift detected",
                "summary": "; ".join(drift_reasons),
                "run_id": run_id,
                "target_locale": str(manifest.get("target_lang") or "unknown"),
                "artifact_refs": artifact_refs,
                "evidence_refs": evidence_refs,
                "adr_refs": effective_adr_refs,
                "recommended_actions": ["inspect lifecycle and KPI artifacts", "rebuild operator summary after correcting drift"],
                "owner": owner,
            }
        )

    review_summary = (kpi_payload.get("review_summary") or {}) if isinstance(kpi_payload, dict) else {}
    pending_review_tickets = int(review_summary.get("pending_review_tickets") or 0)
    manual_intervention_rate = float(review_summary.get("manual_intervention_rate") or 0.0)
    feedback_closure_rate = float(review_summary.get("feedback_closure_rate") or 0.0)
    if pending_review_tickets > 0 or manual_intervention_rate > 0:
        cards.append(
            {
                "card_id": f"card:kpi_watch:{run_id}",
                "card_type": "kpi_watch",
                "status": "open",
                "priority": "P1" if pending_review_tickets > 0 else "P2",
                "title": "Review workload requires monitoring",
                "summary": f"pending_review_tickets={pending_review_tickets}; manual_intervention_rate={manual_intervention_rate}",
                "run_id": run_id,
                "target_locale": str(manifest.get("target_lang") or "unknown"),
                "artifact_refs": artifact_refs,
                "evidence_refs": evidence_refs,
                "adr_refs": effective_adr_refs,
                "recommended_actions": ["inspect open review tickets", "track feedback closure"],
                "owner": owner,
            }
        )

    open_cards = [card for card in cards if card["status"] == "open"]
    if open_cards:
        next_actions: List[str] = []
        for card in open_cards:
            for action in card.get("recommended_actions") or []:
                if action not in next_actions:
                    next_actions.append(str(action))
        cards.append(
            {
                "card_id": f"card:decision_required:{run_id}",
                "card_type": "decision_required",
                "status": "open",
                "priority": "P0" if canonical_status in {"blocked", "failed"} else "P1",
                "title": "Operator decision required",
                "summary": f"{len(open_cards)} open operator cards require follow-up before archival.",
                "run_id": run_id,
                "target_locale": str(manifest.get("target_lang") or "unknown"),
                "artifact_refs": artifact_refs,
                "evidence_refs": evidence_refs,
                "adr_refs": effective_adr_refs,
                "recommended_actions": next_actions or ["review open operator cards"],
                "owner": owner,
            }
        )

    validate_operator_cards(cards)
    write_jsonl(str(cards_path), cards)

    report = {
        "generated_at": _now_iso(),
        "run_id": run_id,
        "run_dir": str(run_path),
        "overall_runtime_health": {
            "status": canonical_status,
            "verify_status": str(verify_payload.get("overall") or verify_payload.get("status") or ""),
            "manifest_status": str(manifest.get("overall_status") or manifest.get("status") or ""),
        },
        "open_review_workload": {
            "total_review_tickets": len(review_tickets),
            "pending_review_tickets": pending_review_tickets,
            "feedback_entries": len(feedback_logs),
        },
        "governance_drift_summary": {
            "drift_count": len(drift_reasons),
            "reasons": drift_reasons,
        },
        "kpi_snapshot": {
            "manual_intervention_rate": manual_intervention_rate,
            "feedback_closure_rate": feedback_closure_rate,
            "pending_review_tickets": pending_review_tickets,
        },
        "open_operator_cards": len([card for card in cards if card["status"] == "open"]),
        "next_recommended_actions": list((cards[-1].get("recommended_actions") if cards and cards[-1]["card_type"] == "decision_required" else _recommended_actions_for_status(canonical_status))),
        "artifact_refs": artifact_refs,
        "evidence_refs": evidence_refs,
        "adr_refs": effective_adr_refs,
    }
    write_json(str(summary_json_path), report)
    summary_md_path.parent.mkdir(parents=True, exist_ok=True)
    summary_md_path.write_text(_summary_md(report), encoding="utf-8")

    return {
        "run_id": run_id,
        "cards_path": str(cards_path),
        "summary_json_path": str(summary_json_path),
        "summary_md_path": str(summary_md_path),
        "open_card_count": report["open_operator_cards"],
        "report": report,
        "cards": cards,
    }


def _cards_by_status(cards: List[Dict[str, Any]], status: str) -> List[Dict[str, Any]]:
    if status == "all":
        return cards
    return [card for card in cards if card.get("status") == status]


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Agent-first operator control plane for run artifacts")
    sub = parser.add_subparsers(dest="command", required=True)

    summarize = sub.add_parser("summarize", help="Build operator cards and operator summary artifacts for a run directory")
    summarize.add_argument("--run-dir", required=True, help="Run directory containing run_manifest.json")
    summarize.add_argument("--owner", default="Codex", help="Default operator owner")
    summarize.add_argument("--adr-ref", action="append", default=[], help="ADR references to embed in cards and summary")

    cards = sub.add_parser("cards", help="List operator cards for a run directory")
    cards.add_argument("--run-dir", required=True, help="Run directory containing run_manifest.json")
    cards.add_argument("--status", default="all", choices=["all", "open", "closed"], help="Filter cards by status")
    cards.add_argument("--owner", default="Codex", help="Default operator owner")
    cards.add_argument("--adr-ref", action="append", default=[], help="ADR references to embed in cards")

    inspect = sub.add_parser("inspect", help="Inspect a single operator card by id")
    inspect.add_argument("--run-dir", required=True, help="Run directory containing run_manifest.json")
    inspect.add_argument("--card-id", required=True, help="Operator card id")
    inspect.add_argument("--owner", default="Codex", help="Default operator owner")
    inspect.add_argument("--adr-ref", action="append", default=[], help="ADR references to embed in cards")
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    result = build_operator_artifacts(
        run_dir=args.run_dir,
        owner=args.owner,
        adr_refs=args.adr_ref or None,
    )
    if args.command == "summarize":
        print(json.dumps({
            "status": "ok",
            "run_id": result["run_id"],
            "cards_path": result["cards_path"],
            "summary_json_path": result["summary_json_path"],
            "summary_md_path": result["summary_md_path"],
            "open_card_count": result["open_card_count"],
        }, ensure_ascii=False))
        return 0
    if args.command == "cards":
        print(json.dumps(_cards_by_status(result["cards"], args.status), ensure_ascii=False, indent=2))
        return 0
    for card in result["cards"]:
        if str(card.get("card_id") or "") == args.card_id:
            print(json.dumps(card, ensure_ascii=False, indent=2))
            return 0
    print(json.dumps({"status": "not_found", "card_id": args.card_id}, ensure_ascii=False))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
