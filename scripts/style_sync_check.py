#!/usr/bin/env python3
import os
import re
from pathlib import Path
from typing import List, Tuple


try:
    import yaml  # type: ignore
except Exception:  # pragma: no cover
    yaml = None


STYLE_AGENT_PATH = Path(__file__).parent.parent / ".agent" / "workflows" / "style-guide.md"
STYLE_WORKFLOW_PATH = Path(__file__).parent.parent / "workflow" / "style_guide.md"
GENERATED_PATH = Path(__file__).parent.parent / "workflow" / "style_guide.generated.md"
STYLE_PROFILE_PATH = Path(__file__).parent.parent / "data" / "style_profile.yaml"


REQUIRED_SECTIONS = [
    "Tone",
    "Terminology",
    "Length",
    "Placeholder",
    "Quality Checklist",
]


def strip_frontmatter(content: str) -> str:
    if content.startswith("---"):
        parts = re.split(r"^---\s*$", content, maxsplit=2, flags=re.MULTILINE)
        if len(parts) >= 3:
            return parts[2].strip()
    return content.strip()


def normalize_content(content: str) -> str:
    return "\n".join([line.strip() for line in strip_frontmatter(content).splitlines() if line.strip()])


def missing_sections(content: str) -> list:
    out = []
    text = content.lower()
    section_aliases = {
        "Tone": ["tone", "register", "语气", "体裁", "官方"],
        "Terminology": ["terminology", "术语", "术语策略", "术语译法"],
        "Length": ["length", "长度", "按钮", "字数"],
        "Placeholder": ["placeholder", "占位符", "变量", "token"],
        "Quality Checklist": ["quality checklist", "checklist", "质量", "验收清单"],
    }
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
        else:
            if current in buckets:
                buckets[current].append(line.strip())
    return buckets


def validate_style_profile(path: Path) -> Tuple[bool, list]:
    issues = []
    if not path.exists():
        return False, ["style_profile not found: data/style_profile.yaml"]
    if yaml is None:
        return True, ["PyYAML not available, skipped schema checks"]
    try:
        with open(path, "r", encoding="utf-8") as f:
            profile = yaml.safe_load(f) or {}
    except Exception as e:
        return False, [f"style_profile parse failed: {e}"]

    if not isinstance(profile, dict):
        return False, ["style_profile invalid type, expected dict"]
    if not profile.get("project", {}).get("source_language"):
        issues.append("missing project.source_language")
    if not profile.get("project", {}).get("target_language"):
        issues.append("missing project.target_language")
    if not profile.get("ui", {}).get("length_constraints"):
        issues.append("missing ui.length_constraints")

    if issues:
        return False, issues
    return True, []


def check_sync() -> bool:
    print("🔍 Checking style guide synchronization and style profile readiness...")

    if not STYLE_AGENT_PATH.exists():
        print(f"❌ ERROR: Agent style guide missing at {STYLE_AGENT_PATH}")
        return False
    if not STYLE_WORKFLOW_PATH.exists():
        print(f"❌ ERROR: Workflow style guide missing at {STYLE_WORKFLOW_PATH}")
        return False
    if not STYLE_PROFILE_PATH.exists():
        print(f"⚠️ WARNING: style_profile missing at {STYLE_PROFILE_PATH}, bootstrap not initialized.")
        return False
    if not GENERATED_PATH.exists():
        print(f"⚠️ WARNING: style_guide.generated.md not found at {GENERATED_PATH}, bootstrap output may be stale.")
        return False

    agent_content = normalize_content(STYLE_AGENT_PATH.read_text(encoding="utf-8"))
    workflow_content = normalize_content(STYLE_WORKFLOW_PATH.read_text(encoding="utf-8"))
    generated_content = normalize_content(GENERATED_PATH.read_text(encoding="utf-8"))
    if agent_content != generated_content:
        print("⚠️ WARNING: workflow/style-guide.md and workflow/style_guide.generated.md differ.")
        print(f"   Agent: {STYLE_AGENT_PATH}")
        print(f"   Generated: {GENERATED_PATH}")
        return False
    if agent_content != workflow_content:
        print("⚠️ WARNING: .agent/workflows/style-guide.md and workflow/style_guide.md differ.")
        return False

    missing = missing_sections(agent_content)
    if missing:
        print(f"❌ ERROR: Style guide missing sections: {', '.join(missing)}")
        return False

    generated_sections = find_hash_target_sections(generated_content)
    normalized_section_keys = []
    for k in generated_sections:
        # Accept markdown headings such as "1. Tone" / "2. Terminology"
        no_prefix = re.sub(r"^\d+\.\s*", "", k).strip()
        normalized_section_keys.append(no_prefix)
    has_tone_or_register = any(("register" in k) or ("tone" in k) for k in normalized_section_keys)
    has_term = any("terminology" in k or "术语" in k for k in normalized_section_keys)
    if not (has_tone_or_register and has_term):
        print("⚠️ WARNING: generated guide lacks expected tone/term section structure markers.")

    profile_ok, profile_issues = validate_style_profile(STYLE_PROFILE_PATH)
    if not profile_ok:
        print("❌ ERROR: style_profile validation failed:")
        for item in profile_issues:
            print(f"   - {item}")
        return False

    print("✅ Success: style guides and style profile are in sync.")
    print("✅ style_sync_check: pass")
    return True


if __name__ == "__main__":
    if not check_sync():
        raise SystemExit(1)
    raise SystemExit(0)
