#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

import style_sync_check

try:
    import yaml
except Exception:  # pragma: no cover
    yaml = None


REPO_ROOT = Path(__file__).resolve().parent.parent

DEFAULT_LIFECYCLE_CONTRACT = {
    "required_fields": ["asset_id", "asset_kind", "asset_path", "status", "approval_ref", "required_runtime_gate"],
    "asset_kind_enum": ["style_profile", "glossary", "policy", "report"],
    "status_enum": ["draft", "approved", "deprecated", "superseded"],
    "none_values": ["none", ""],
}


def _repo_relative(path: str) -> str:
    raw = Path(path)
    resolved = raw if raw.is_absolute() else (REPO_ROOT / raw).resolve()
    try:
        return resolved.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return resolved.as_posix()


def _is_repo_managed(path: str) -> bool:
    raw = Path(path)
    resolved = raw if raw.is_absolute() else (REPO_ROOT / raw).resolve()
    try:
        resolved.relative_to(REPO_ROOT)
        return True
    except ValueError:
        return False


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


def load_lifecycle_contract(path: str = "workflow/lifecycle_contract.yaml") -> Dict[str, Any]:
    return _load_yaml_dict(path, DEFAULT_LIFECYCLE_CONTRACT)


def load_lifecycle_registry(path: str = "workflow/lifecycle_registry.yaml") -> Dict[str, Any]:
    return _load_yaml_dict(path, {"version": "1.0", "entries": []})


def _none_values(contract: Dict[str, Any]) -> set[str]:
    return {str(value).strip() for value in (contract.get("none_values") or [])}


def _find_registry_entry(registry: Dict[str, Any], asset_path: str) -> Optional[Dict[str, Any]]:
    normalized_path = _repo_relative(asset_path)
    for entry in registry.get("entries", []) or []:
        if not isinstance(entry, dict):
            continue
        entry_path = _repo_relative(str(entry.get("asset_path") or ""))
        if entry_path == normalized_path:
            return entry
    return None


def _validate_registry_entry(
    entry: Dict[str, Any],
    contract: Dict[str, Any],
    *,
    asset_kind: str,
    asset_path: str,
) -> List[str]:
    issues: List[str] = []
    none_values = _none_values(contract)
    required_fields = contract.get("required_fields", []) or []
    asset_kind_enum = set(contract.get("asset_kind_enum", []) or [])
    status_enum = set(contract.get("status_enum", []) or [])

    for field in required_fields:
        value = entry.get(field)
        if value in (None, "", []):
            issues.append(f"LIFECYCLE_E001 missing {field} for {_repo_relative(asset_path)}")

    if asset_kind_enum and str(entry.get("asset_kind") or "") not in asset_kind_enum:
        issues.append(
            f"LIFECYCLE_E002 invalid asset_kind for {_repo_relative(asset_path)}: {entry.get('asset_kind')}"
        )
    if str(entry.get("asset_kind") or "") != asset_kind:
        issues.append(
            f"LIFECYCLE_E003 asset_kind mismatch for {_repo_relative(asset_path)}: expected {asset_kind}, got {entry.get('asset_kind')}"
        )

    status = str(entry.get("status") or "")
    if status_enum and status not in status_enum:
        issues.append(f"LIFECYCLE_E004 invalid status for {_repo_relative(asset_path)}: {status}")
    if bool(entry.get("required_runtime_gate")) and status != "approved":
        issues.append(f"LIFECYCLE_E005 runtime-gated asset is not approved: {_repo_relative(asset_path)} -> {status}")

    deprecated_by = str(entry.get("deprecated_by") or "").strip()
    if status == "deprecated" and deprecated_by in none_values:
        issues.append(f"LIFECYCLE_E006 deprecated asset missing deprecated_by: {_repo_relative(asset_path)}")
    if status == "approved" and deprecated_by not in none_values:
        issues.append(f"LIFECYCLE_E007 approved asset cannot set deprecated_by: {_repo_relative(asset_path)}")

    approval_ref = str(entry.get("approval_ref") or "").strip()
    if bool(entry.get("required_runtime_gate")) and not approval_ref:
        issues.append(f"LIFECYCLE_E008 runtime-gated asset missing approval_ref: {_repo_relative(asset_path)}")

    return issues


def _load_profile(style_profile_path: str) -> Dict[str, Any]:
    return _load_yaml_dict(style_profile_path, {})


def evaluate_runtime_governance(
    *,
    style_profile_path: str,
    glossary_path: str = "",
    policy_paths: Optional[Iterable[str]] = None,
    lifecycle_registry_path: str = "workflow/lifecycle_registry.yaml",
) -> Dict[str, Any]:
    issues: List[str] = []
    style_profile_resolved = _repo_relative(style_profile_path)
    contract = load_lifecycle_contract()
    registry = load_lifecycle_registry(lifecycle_registry_path)
    if not _is_repo_managed(style_profile_path):
        profile = _load_profile(style_profile_path)
        project = profile.get("project", {}) if isinstance(profile, dict) else {}
        ui = profile.get("ui", {}) if isinstance(profile, dict) else {}
        if not project.get("source_language") or not project.get("target_language"):
            issues.append("STYLE_RUNTIME_E010 external style profile missing project source/target")
        if not isinstance(ui, dict) or not ui.get("length_constraints"):
            issues.append("STYLE_RUNTIME_E011 external style profile missing ui.length_constraints")
        asset_statuses: Dict[str, Dict[str, Any]] = {}
        entry = _find_registry_entry(registry, style_profile_path)
        if entry is not None:
            issues.extend(
                _validate_registry_entry(
                    entry,
                    contract,
                    asset_kind="style_profile",
                    asset_path=style_profile_path,
                )
            )
            asset_statuses[style_profile_resolved] = {
                "asset_id": str(entry.get("asset_id") or ""),
                "asset_kind": str(entry.get("asset_kind") or ""),
                "status": str(entry.get("status") or ""),
                "required_runtime_gate": bool(entry.get("required_runtime_gate")),
            }
        return {
            "passed": not issues,
            "style_profile_path": style_profile_resolved,
            "style_profile_version": str(profile.get("version") or ""),
            "style_guide_id": "",
            "approval_ref": "",
            "lifecycle_registry_path": _repo_relative(lifecycle_registry_path),
            "issues": issues,
            "asset_statuses": asset_statuses,
        }
    ok, profile_issues, version = style_sync_check.validate_style_profile(Path(style_profile_path))
    if not ok:
        issues.extend(profile_issues)

    profile = _load_profile(style_profile_path)
    governance = profile.get("style_governance", {}) if isinstance(profile, dict) else {}
    if not isinstance(governance, dict):
        issues.append("STYLE_RUNTIME_E001 missing style_governance block")
        governance = {}

    status = str(governance.get("status") or "").strip()
    entry_audit = governance.get("entry_audit", {}) if isinstance(governance.get("entry_audit"), dict) else {}
    if status != "approved":
        issues.append(f"STYLE_RUNTIME_E002 style_governance.status must be approved, got {status or '<empty>'}")
    if entry_audit.get("loadable") is not True:
        issues.append("STYLE_RUNTIME_E003 style_governance.entry_audit.loadable must be true")
    if entry_audit.get("approved") is not True:
        issues.append("STYLE_RUNTIME_E004 style_governance.entry_audit.approved must be true")
    if entry_audit.get("deprecated") is not False:
        issues.append("STYLE_RUNTIME_E005 style_governance.entry_audit.deprecated must be false")

    asset_statuses: Dict[str, Dict[str, Any]] = {}
    assets = [{"path": style_profile_path, "kind": "style_profile", "required": True}]
    if glossary_path:
        assets.append({"path": glossary_path, "kind": "glossary", "required": False})
    for policy_path in policy_paths or []:
        assets.append({"path": policy_path, "kind": "policy", "required": False})

    for asset in assets:
        asset_path = str(asset["path"])
        asset_kind = str(asset["kind"])
        entry = _find_registry_entry(registry, asset_path)
        if entry is None:
            if asset.get("required"):
                issues.append(f"LIFECYCLE_E009 missing lifecycle entry for runtime-gated asset: {_repo_relative(asset_path)}")
                asset_statuses[_repo_relative(asset_path)] = {"status": "missing"}
            else:
                asset_statuses[_repo_relative(asset_path)] = {"status": "unregistered"}
            continue
        entry_issues = _validate_registry_entry(entry, contract, asset_kind=asset_kind, asset_path=asset_path)
        issues.extend(entry_issues)
        asset_statuses[_repo_relative(asset_path)] = {
            "asset_id": str(entry.get("asset_id") or ""),
            "asset_kind": str(entry.get("asset_kind") or ""),
            "status": str(entry.get("status") or ""),
            "required_runtime_gate": bool(entry.get("required_runtime_gate")),
        }

    return {
        "passed": not issues,
        "style_profile_path": style_profile_resolved,
        "style_profile_version": version,
        "style_guide_id": str(governance.get("style_guide_id") or ""),
        "approval_ref": str(governance.get("approval_ref") or ""),
        "lifecycle_registry_path": _repo_relative(lifecycle_registry_path),
        "issues": issues,
        "asset_statuses": asset_statuses,
    }


def format_runtime_governance_issues(report: Dict[str, Any]) -> str:
    lines = ["Phase 3 style governance gate failed:"]
    for issue in report.get("issues", []) or []:
        lines.append(f"- {issue}")
    return "\n".join(lines)
