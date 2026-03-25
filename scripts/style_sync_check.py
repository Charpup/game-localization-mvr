#!/usr/bin/env python3
import json
import re
import sys
from pathlib import Path
from typing import List, Optional, Tuple

STYLE_SYNC_RULE_ID = "STEP0_STYLE_SYNC"
STYLE_SYNC_VERSION = "1.2"
STYLE_SYNC_MISSING_PROFILE = "STYLE_SYNC_E100"

STYLE_SYNC_REMEDIATION = (
    "Run scripts/style_guide_bootstrap.py first, then scripts/style_sync_check.py; "
    "if diffs remain, regenerate workflow/style_guide.md and .agent/workflows/style-guide.md from the same source."
)

STYLE_AGENT_PATH = Path(__file__).parent.parent / ".agent" / "workflows" / "style-guide.md"
STYLE_WORKFLOW_PATH = Path(__file__).parent.parent / "workflow" / "style_guide.md"
GENERATED_PATH = Path(__file__).parent.parent / "workflow" / "style_guide.generated.md"
STYLE_PROFILE_PATH = Path(__file__).parent.parent / "data" / "style_profile.yaml"
STYLE_GOVERNANCE_CONTRACT_PATH = Path(__file__).parent.parent / "workflow" / "style_governance_contract.yaml"

STYLE_PROFILE_CANDIDATES = [
    Path(__file__).parent.parent / "data" / "style_profile.yaml",
    Path(__file__).parent.parent / "config" / "style_profile.yaml",
    Path(__file__).parent.parent / "workflow" / "style_profile.yaml",
    Path(__file__).parent.parent / "config" / "workflow" / "style_profile.yaml",
    Path(__file__).parent.parent / "src" / "config" / "style_profile.yaml",
]

REQUIRED_PROFILE_FIELDS = {
    "project.source_language": "STYLE_SYNC_E101",
    "project.target_language": "STYLE_SYNC_E102",
    "style_contract.language_policy.no_over_localization": "STYLE_SYNC_E103",
    "style_contract.language_policy.no_over_literal": "STYLE_SYNC_E104",
    "style_contract.placeholder_protection.preserve_ph_tokens": "STYLE_SYNC_E105",
    "style_contract.placeholder_protection.preserve_markup": "STYLE_SYNC_E106",
    "style_contract.style_guard.character_name_policy": "STYLE_SYNC_E107",
    "style_contract.style_guard.proper_noun_strategy": "STYLE_SYNC_E108",
    "ui.length_constraints.button_max_chars": "STYLE_SYNC_E109",
    "ui.length_constraints.dialogue_max_chars": "STYLE_SYNC_E110",
    "ui.length_constraints.max_expansion_pct": "STYLE_SYNC_E111",
    "segmentation.backend_chain": "STYLE_SYNC_E112",
}

STYLE_GOVERNANCE_DEFAULT_CONTRACT = {
    "governance": {
        "required_fields": [],
        "status_enum": ["draft", "approved", "deprecated"],
        "approval_ref_prefixes": ["docs/decisions/", "docs/project_lifecycle/"],
        "none_values": ["none", ""],
    }
}


try:
    import yaml  # type: ignore
except Exception:  # pragma: no cover
    yaml = None


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


def strip_frontmatter(content: str) -> str:
    if content.startswith("---"):
        parts = re.split(r"^---\s*$", content, maxsplit=2, flags=re.MULTILINE)
        if len(parts) >= 3:
            return parts[2].strip()
    return content.strip()


def normalize_content(content: str) -> str:
    return "\n".join([line.strip() for line in strip_frontmatter(content).splitlines() if line.strip()])


def get_nested(data: dict, dotted_key: str):
    current = data
    for part in dotted_key.split("."):
        if not isinstance(current, dict) or part not in current:
            return None
        current = current.get(part)
    return current


def load_style_governance_contract() -> dict:
    if yaml is None or not STYLE_GOVERNANCE_CONTRACT_PATH.exists():
        return STYLE_GOVERNANCE_DEFAULT_CONTRACT
    try:
        with open(STYLE_GOVERNANCE_CONTRACT_PATH, "r", encoding="utf-8") as f:
            loaded = yaml.safe_load(f) or {}
    except Exception:
        return STYLE_GOVERNANCE_DEFAULT_CONTRACT
    if not isinstance(loaded, dict):
        return STYLE_GOVERNANCE_DEFAULT_CONTRACT
    return loaded


def missing_sections(content: str) -> list:
    text = content.lower()
    section_aliases = {
        "Tone": ["tone", "register", "语气", "体裁", "官方"],
        "Terminology": ["terminology", "术语", "术语策略", "术语译法"],
        "Length": ["length", "长度", "按钮", "字数"],
        "Placeholder": ["placeholder", "占位符", "变量", "token"],
        "Quality Checklist": ["quality checklist", "checklist", "质量", "验收清单"],
    }
    out = []
    for section, aliases in section_aliases.items():
        if not any(alias in text for alias in aliases):
            out.append(section)
    return out


def find_hash_target_sections(content: str) -> dict:
    buckets = {}
    lines = content.splitlines()
    current = "intro"
    for line in lines:
        m = re.match(r"^##+\s+(.*)$", line.strip())
        if m:
            current = m.group(1).strip().lower()
            buckets[current] = []
        elif current in buckets:
            buckets[current].append(line.strip())
    return buckets


def resolve_style_profile_path() -> Path:
    for path in STYLE_PROFILE_CANDIDATES:
        if path.exists():
            return path
    return STYLE_PROFILE_PATH


def build_gate_payload(
    status: str,
    version: str,
    rule_id: str,
    issues: List[str],
    remediation: Optional[str] = None,
    triggered_rule_ids: Optional[List[str]] = None,
):
    return {
        "rule_id": rule_id,
        "version": version,
        "status": status,
        "hard_gate": True,
        "issues": issues,
        "triggered_rule_ids": triggered_rule_ids or [],
        "remediation": remediation or STYLE_SYNC_REMEDIATION,
        "suggested_actions": [remediation or STYLE_SYNC_REMEDIATION],
    }


def validate_style_governance(profile: dict, contract: dict) -> List[str]:
    governance_contract = (contract.get("governance", {}) or {})
    required_fields = governance_contract.get("required_fields", []) or []
    status_enum = set(governance_contract.get("status_enum", []) or [])
    approval_ref_prefixes = governance_contract.get("approval_ref_prefixes", []) or []
    none_values = set(governance_contract.get("none_values", []) or [])
    issues: List[str] = []

    for dotted_key in required_fields:
        value = get_nested(profile, dotted_key)
        if value in (None, "", []):
            issues.append(f"STYLE_SYNC_E140: missing {dotted_key}")

    governance = profile.get("style_governance", {}) if isinstance(profile, dict) else {}
    if not isinstance(governance, dict):
        return issues + ["STYLE_SYNC_E141: style_governance must be a dict"]

    status = str(governance.get("status", "")).strip()
    if status_enum and status not in status_enum:
        issues.append(f"STYLE_SYNC_E142: invalid style_governance.status -> {status}")

    entry_audit = governance.get("entry_audit", {})
    if not isinstance(entry_audit, dict):
        issues.append("STYLE_SYNC_E143: style_governance.entry_audit must be a dict")
        return issues

    loadable = entry_audit.get("loadable")
    approved = entry_audit.get("approved")
    deprecated = entry_audit.get("deprecated")
    if status == "approved" and not (loadable is True and approved is True and deprecated is False):
        issues.append("STYLE_SYNC_E144: approved status requires loadable=true, approved=true, deprecated=false")
    if status == "draft" and approved is True:
        issues.append("STYLE_SYNC_E145: draft status may not set approved=true")
    if status == "deprecated" and not (deprecated is True and loadable is False):
        issues.append("STYLE_SYNC_E146: deprecated status requires deprecated=true and loadable=false")

    approval_ref = str(governance.get("approval_ref", "")).strip()
    if status != "draft" and approval_ref_prefixes and not any(approval_ref.startswith(prefix) for prefix in approval_ref_prefixes):
        issues.append(f"STYLE_SYNC_E147: approval_ref must start with one of {approval_ref_prefixes}")

    adr_refs = governance.get("adr_refs", [])
    if not isinstance(adr_refs, list):
        issues.append("STYLE_SYNC_E148: style_governance.adr_refs must be a list")
    else:
        for ref in adr_refs:
            ref_text = str(ref).strip()
            if not ref_text or ref_text in none_values:
                continue
            if not (Path(__file__).parent.parent / ref_text).exists():
                issues.append(f"STYLE_SYNC_E149: adr_ref missing -> {ref_text}")

    lineage = governance.get("lineage", {})
    if not isinstance(lineage, dict):
        issues.append("STYLE_SYNC_E150: style_governance.lineage must be a dict")
        return issues
    mirror_guides = lineage.get("mirror_guides", [])
    if mirror_guides is not None and not isinstance(mirror_guides, list):
        issues.append("STYLE_SYNC_E151: style_governance.lineage.mirror_guides must be a list")

    return issues


def validate_style_profile(path: Path) -> Tuple[bool, List[str], str]:
    if not path.exists():
        return False, [f"{STYLE_SYNC_MISSING_PROFILE}: style profile missing: {path}"], STYLE_SYNC_VERSION

    if yaml is None:
        return True, ["PyYAML not available, skipped schema checks"], STYLE_SYNC_VERSION

    try:
        with open(path, "r", encoding="utf-8") as f:
            profile = yaml.safe_load(f) or {}
    except Exception as e:
        return False, [f"STYLE_SYNC_E199: style profile parse failed: {e}"], STYLE_SYNC_VERSION

    if not isinstance(profile, dict):
        return False, ["STYLE_SYNC_E198: style_profile invalid type, expected dict"], STYLE_SYNC_VERSION

    version = str(profile.get("version", STYLE_SYNC_VERSION))
    issues: List[str] = []
    contract = load_style_governance_contract()

    if not profile.get("version"):
        issues.append("STYLE_SYNC_E120: missing version")

    for dotted_key, issue_code in REQUIRED_PROFILE_FIELDS.items():
        value = get_nested(profile, dotted_key)
        if value in (None, "", []):
            issues.append(f"{issue_code}: missing {dotted_key}")

    forbidden_terms = get_nested(profile, "terminology.forbidden_terms")
    preferred_terms = get_nested(profile, "terminology.preferred_terms")
    if forbidden_terms is None:
        issues.append("STYLE_SYNC_E113: missing terminology.forbidden_terms")
    elif not isinstance(forbidden_terms, list):
        issues.append("STYLE_SYNC_E114: terminology.forbidden_terms must be a list")

    if preferred_terms is None:
        issues.append("STYLE_SYNC_E115: missing terminology.preferred_terms")
    elif not isinstance(preferred_terms, list):
        issues.append("STYLE_SYNC_E116: terminology.preferred_terms must be a list")

    preserve_tokens = get_nested(profile, "style_contract.placeholder_protection.variables")
    if preserve_tokens is not None and not isinstance(preserve_tokens, list):
        issues.append("STYLE_SYNC_E122: placeholder_protection.variables must be a list")

    ui_constraints = profile.get("ui", {}).get("length_constraints", {})
    for key in ("button_max_chars", "dialogue_max_chars"):
        max_len = ui_constraints.get(key)
        if max_len is not None:
            try:
                if int(max_len) <= 0:
                    issues.append(f"STYLE_SYNC_E123: {key} must be > 0")
            except Exception:
                issues.append(f"STYLE_SYNC_E123: {key} must be integer")

    preferred_map = {}
    for item in preferred_terms or []:
        if isinstance(item, dict):
            zh = str(item.get("term_zh", "")).strip()
            ru = str(item.get("term_ru", "")).strip()
            if zh:
                preferred_map[zh] = ru
    for term in forbidden_terms or []:
        t = str(term).strip()
        if t in preferred_map:
            issues.append(f"STYLE_SYNC_E121: forbidden term conflict -> {t} appears in preferred_terms")

    issues.extend(validate_style_governance(profile, contract))

    return (len(issues) == 0), issues, version


def check_sync() -> bool:
    print("🔍 Checking style guide synchronization and style profile readiness...")

    profile_path = resolve_style_profile_path()
    gate = build_gate_payload("running", STYLE_SYNC_VERSION, STYLE_SYNC_RULE_ID, [])
    
    def fail_gate(issue: str, remediation: str, extra_issues: Optional[List[str]] = None, version: Optional[str] = None) -> bool:
        issues = [issue]
        if extra_issues:
            issues.extend(extra_issues)
        triggered = [item.split(":", 1)[0] for item in issues if ":" in item]
        gate["status"] = "failed"
        gate["version"] = version or gate["version"]
        gate["issues"] = issues
        gate["triggered_rule_ids"] = triggered
        gate["remediation"] = remediation
        gate["suggested_actions"] = [remediation]
        print(json.dumps(gate, ensure_ascii=False))
        return False

    if not STYLE_AGENT_PATH.exists():
        print(f"❌ ERROR: Agent style guide missing. Checked: {STYLE_AGENT_PATH}")
        return fail_gate(
            "STYLE_SYNC_E130: agent style guide missing",
            "Generate .agent/workflows/style-guide.md via scripts/style_guide_bootstrap.py",
        )

    if not STYLE_WORKFLOW_PATH.exists():
        print(f"❌ ERROR: Workflow style guide missing. Checked: {STYLE_WORKFLOW_PATH}")
        return fail_gate(
            "STYLE_SYNC_E131: workflow style guide missing",
            "Ensure workflow/style_guide.md exists and mirrors .agent/workflows/style-guide.md",
        )

    if not profile_path.exists():
        print(f"❌ ERROR: style_profile missing. Checked candidates: {[str(p) for p in STYLE_PROFILE_CANDIDATES]}")
        return fail_gate(
            f"{STYLE_SYNC_MISSING_PROFILE}: style profile missing: {profile_path}",
            "Run scripts/style_guide_bootstrap.py",
        )

    if not GENERATED_PATH.exists():
        print(f"⚠️ ERROR: generated style guide missing at {GENERATED_PATH}")
        return fail_gate(
            "STYLE_SYNC_E132: generated style guide missing",
            "Run scripts/style_guide_bootstrap.py and scripts/style_guide_generate.py",
        )

    agent_content = normalize_content(STYLE_AGENT_PATH.read_text(encoding="utf-8"))
    workflow_content = normalize_content(STYLE_WORKFLOW_PATH.read_text(encoding="utf-8"))
    generated_content = normalize_content(GENERATED_PATH.read_text(encoding="utf-8"))
    if agent_content != workflow_content:
        print("⚠️ WARNING: .agent/workflows/style-guide.md and workflow/style_guide.md diverged.")
        print(f"   Agent: {STYLE_AGENT_PATH}")
        print(f"   Workflow: {STYLE_WORKFLOW_PATH}")
        return fail_gate(
            "STYLE_SYNC_E133: agent/workflow style guide mismatch",
            "Rerun style guide source sync and ensure .agent/workflows/style-guide.md == workflow/style_guide.md",
        )

    if agent_content != generated_content:
        print("⚠️ WARNING: generated style guide diverged from source guide.")
        print(f"   Agent: {STYLE_AGENT_PATH}")
        print(f"   Generated: {GENERATED_PATH}")
        return fail_gate(
            "STYLE_SYNC_E134: generated style guide mismatch",
            "Run scripts/style_guide_generate.py from the latest source guide.",
        )

    missing = missing_sections(agent_content)
    if missing:
        print(f"❌ ERROR: Style guide missing sections: {', '.join(missing)}")
        return fail_gate(
            f"STYLE_SYNC_E135: missing style sections: {', '.join(missing)}",
            "补齐 style_guide 的 Tone / Terminology / Length / Placeholder / Quality Checklist",
        )

    generated_sections = find_hash_target_sections(generated_content)
    normalized_section_keys = []
    for k in generated_sections:
        no_prefix = re.sub(r"^\d+\.\s*", "", k).strip()
        normalized_section_keys.append(no_prefix)
    has_tone_or_register = any(("register" in k) or ("tone" in k) for k in normalized_section_keys)
    has_term = any("terminology" in k or "术语" in k for k in normalized_section_keys)
    if not (has_tone_or_register and has_term):
        print("⚠️ WARNING: generated guide lacks expected tone/terminology structure markers.")

    profile_ok, profile_issues, profile_version = validate_style_profile(profile_path)
    if not profile_ok:
        print(f"❌ ERROR: style_profile validation failed: {profile_path}")
        for item in profile_issues:
            print(f"   - {item}")
        return fail_gate(
            profile_issues[0] if profile_issues else "STYLE_SYNC_E199: unknown style profile validation failure",
            "补齐 style_profile.yaml 关键字段后重跑 scripts/style_guide_bootstrap.py 与 scripts/style_sync_check.py",
            extra_issues=profile_issues[1:],
            version=profile_version,
        )

    gate["status"] = "pass"
    gate["version"] = profile_version or STYLE_SYNC_VERSION
    gate["triggered_rule_ids"] = []
    gate["suggested_actions"] = []
    print("✅ Success: style guides and style profile are in sync.")
    print("✅ style_sync_check: pass")
    print(json.dumps(gate, ensure_ascii=False))
    return True


if __name__ == "__main__":
    configure_standard_streams()
    if not check_sync():
        raise SystemExit(1)
    raise SystemExit(0)
