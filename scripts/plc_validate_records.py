#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Validate representative PLC governance artifacts against a local contract."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import yaml


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONTRACT = REPO_ROOT / "workflow" / "plc_governance_contract.yaml"


def _strip_ticks(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    text = value.strip()
    if len(text) >= 2 and text.startswith("`") and text.endswith("`"):
        text = text[1:-1].strip()
    lowered = text.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    if text.isdigit():
        return int(text)
    return text


def _normalize_yaml_value(value: Any) -> Any:
    if isinstance(value, list):
        if value and all(isinstance(item, dict) and len(item) == 1 for item in value):
            merged: Dict[str, Any] = {}
            for item in value:
                key, raw = next(iter(item.items()))
                merged[str(key)] = _normalize_yaml_value(raw)
            return merged
        return [_normalize_yaml_value(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _normalize_yaml_value(raw) for key, raw in value.items()}
    return _strip_ticks(value)


def _parse_markdown_block(lines: List[str], start: int = 0, indent: Optional[int] = None) -> Tuple[List[Any], int]:
    items: List[Any] = []
    index = start
    if indent is None:
        while index < len(lines) and not lines[index].strip():
            index += 1
        if index >= len(lines):
            return items, index
        indent = len(lines[index]) - len(lines[index].lstrip(" "))

    while index < len(lines):
        line = lines[index]
        if not line.strip():
            index += 1
            continue
        current_indent = len(line) - len(line.lstrip(" "))
        if current_indent < indent:
            break
        if current_indent > indent:
            break
        content = line[current_indent:].strip()
        if not content.startswith("- "):
            index += 1
            continue
        body = content[2:].strip()
        if ":" in body:
            key, value = body.split(":", 1)
            key = key.strip()
            value = value.strip()
            if value and value not in {">", "|"}:
                items.append({key: _strip_ticks(value)})
                index += 1
                continue

            child_indent: Optional[int] = None
            probe = index + 1
            while probe < len(lines):
                next_line = lines[probe]
                if not next_line.strip():
                    probe += 1
                    continue
                next_indent = len(next_line) - len(next_line.lstrip(" "))
                if next_indent <= current_indent:
                    break
                child_indent = next_indent
                break
            if child_indent is None:
                items.append({key: "" if value in {">", "|"} else []})
                index += 1
                continue
            child_lines: List[str] = []
            probe = index + 1
            while probe < len(lines):
                next_line = lines[probe]
                if not next_line.strip():
                    probe += 1
                    continue
                next_indent = len(next_line) - len(next_line.lstrip(" "))
                if next_indent < child_indent:
                    break
                child_lines.append(next_line)
                probe += 1

            first_child = next((line for line in child_lines if line.strip()), "")
            first_child_content = first_child[child_indent:].strip() if first_child else ""
            if value in {">", "|"} or (first_child and not first_child_content.startswith("- ")):
                prose_lines = [line[child_indent:].strip() for line in child_lines if line.strip()]
                items.append({key: " ".join(part for part in prose_lines if part)})
                index = probe
                continue

            child, new_index = _parse_markdown_block(lines, index + 1, child_indent)
            items.append({key: child})
            index = new_index
            continue

        items.append(_strip_ticks(body))
        index += 1
    return items, index


def load_contract(path: Path = DEFAULT_CONTRACT) -> Dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def parse_markdown_sections(path: Path) -> Dict[str, Any]:
    root_lines: List[str] = []
    sections: Dict[str, List[str]] = {}
    current: Optional[List[str]] = root_lines

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.rstrip()
        if line.startswith("## "):
            current = sections.setdefault(line[3:].strip(), [])
            continue
        if line.startswith("# "):
            continue
        if not line.strip():
            continue
        if current is not None:
            current.append(line)

    parsed: Dict[str, Any] = {}
    if root_lines:
        root_items, _ = _parse_markdown_block(root_lines)
        parsed["__root__"] = _normalize_yaml_value(root_items)
    else:
        parsed["__root__"] = {}
    for section, lines in sections.items():
        section_items, _ = _parse_markdown_block(lines)
        parsed[section] = _normalize_yaml_value(section_items)
    return parsed


def _is_empty(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    return False


def _ensure_required(container: Dict[str, Any], required: Iterable[str], label: str, errors: List[str]) -> None:
    for field in required:
        if field not in container or _is_empty(container[field]):
            errors.append(f"{label}: missing required field `{field}`")


def _ensure_enums(
    container: Dict[str, Any],
    enum_fields: Dict[str, List[str]],
    label: str,
    errors: List[str],
    *,
    allow_placeholders: bool = False,
) -> None:
    for field, allowed in enum_fields.items():
        if field not in container or _is_empty(container[field]):
            continue
        if allow_placeholders and isinstance(container[field], str):
            candidate = str(container[field])
            if "<" in candidate or ">" in candidate or "|" in candidate:
                continue
        if str(container[field]) not in {str(item) for item in allowed}:
            errors.append(f"{label}: invalid `{field}` value `{container[field]}`")


def _ensure_booleans(container: Dict[str, Any], fields: Iterable[str], label: str, errors: List[str]) -> None:
    for field in fields:
        if field not in container:
            continue
        if not isinstance(container[field], bool):
            errors.append(f"{label}: `{field}` must be boolean")


def _ensure_integers(
    container: Dict[str, Any],
    fields: Iterable[str],
    label: str,
    errors: List[str],
    *,
    allow_placeholders: bool = False,
) -> None:
    for field in fields:
        if field not in container or _is_empty(container[field]):
            continue
        if allow_placeholders and isinstance(container[field], str):
            candidate = str(container[field])
            if "<" in candidate or ">" in candidate:
                continue
        if isinstance(container[field], bool) or not isinstance(container[field], int):
            errors.append(f"{label}: `{field}` must be integer")


def validate_run_manifest(path: Path, rules: Dict[str, Any]) -> List[str]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    errors: List[str] = []
    _ensure_required(payload, rules.get("required_fields", []), path.name, errors)
    _ensure_enums(payload, rules.get("enum_fields", {}), path.name, errors)
    _ensure_booleans(payload, rules.get("boolean_fields", []), path.name, errors)
    return errors


def validate_markdown_artifact(path: Path, rules: Dict[str, Any], artifact_type: str) -> List[str]:
    parsed = parse_markdown_sections(path)
    root = parsed.get("__root__", {})
    is_template = path.name.endswith("_template.md")
    errors: List[str] = []
    _ensure_required(root, rules.get("required_top_level", []), f"{path.name} root", errors)
    _ensure_enums(root, rules.get("enum_fields", {}), f"{path.name} root", errors, allow_placeholders=is_template)
    _ensure_booleans(root, rules.get("boolean_fields", []), f"{path.name} root", errors)
    _ensure_integers(root, rules.get("integer_fields", []), f"{path.name} root", errors, allow_placeholders=is_template)

    for field, required_nested in (rules.get("required_nested", {}) or {}).items():
        value = root.get(field)
        if not isinstance(value, dict):
            errors.append(f"{path.name} root: `{field}` must be mapping")
            continue
        _ensure_required(value, required_nested, f"{path.name} {field}", errors)

    for section, required_fields in (rules.get("required_sections", {}) or {}).items():
        value = parsed.get(section)
        if value is None:
            errors.append(f"{path.name}: missing required section `{section}`")
            continue
        if required_fields and not isinstance(value, dict):
            errors.append(f"{path.name}: section `{section}` must be mapping")
            continue
        if required_fields:
            _ensure_required(value, required_fields, f"{path.name} section {section}", errors)

    if artifact_type == "session_start":
        handoff = parsed.get("Handoff", {})
        validation = parsed.get("Validation Decision", {})
        if isinstance(validation, dict) and "smoke run" in validation:
            smoke_value = str(validation.get("smoke run") or "").strip().lower()
            if not is_template and smoke_value not in {"required", "not required for this slice"}:
                errors.append(f"{path.name} section Validation Decision: invalid `smoke run` value `{validation.get('smoke run')}`")
        if isinstance(handoff, dict) and handoff.get("next_scope") == root.get("current_scope"):
            errors.append(f"{path.name} section Handoff: `next_scope` should advance beyond `current_scope`")
    return errors


def validate_artifact(contract: Dict[str, Any], artifact_type: str, path: Path) -> List[str]:
    rules = (contract.get("artifacts", {}) or {}).get(artifact_type)
    if not rules:
        return [f"{path.name}: unknown artifact type `{artifact_type}`"]
    if not path.exists():
        return [f"{path}: file does not exist"]
    if artifact_type == "run_manifest":
        return validate_run_manifest(path, rules)
    return validate_markdown_artifact(path, rules, artifact_type)


def collect_preset_records(contract: Dict[str, Any], presets: Iterable[str]) -> List[Tuple[str, Path]]:
    records: List[Tuple[str, Path]] = []
    available = contract.get("presets", {}) or {}
    for preset in presets:
        for entry in available.get(preset, []):
            records.append((str(entry["artifact_type"]), REPO_ROOT / str(entry["path"])))
    return records


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate representative PLC governance artifacts")
    parser.add_argument("--contract", default=str(DEFAULT_CONTRACT))
    parser.add_argument("--preset", action="append", choices=["representative", "templates"], default=[])
    parser.add_argument("--artifact-type", choices=["run_manifest", "session_start", "session_end", "milestone_state"])
    parser.add_argument("--path", action="append", default=[])
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    contract = load_contract(Path(args.contract))
    targets = collect_preset_records(contract, args.preset)
    if args.path:
        if not args.artifact_type:
            raise ValueError("--artifact-type is required when using --path")
        targets.extend((args.artifact_type, REPO_ROOT / item) for item in args.path)
    if not targets:
        targets = collect_preset_records(contract, ["representative"])

    failures: List[str] = []
    for artifact_type, path in targets:
        failures.extend(validate_artifact(contract, artifact_type, path))

    if failures:
        for failure in failures:
            print(f"FAIL: {failure}")
        return 1

    print(f"Validated {len(targets)} PLC governance artifact(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
