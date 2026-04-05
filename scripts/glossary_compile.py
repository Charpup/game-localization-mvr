#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
glossary_compile.py

Compile approved glossary entries into runtime-ready artifact.

Usage:
    python scripts/glossary_compile.py \
        --approved glossary/approved.yaml \
        --out_compiled glossary/compiled.yaml \
        --language_pair zh-CN->ru-RU \
        --genre anime \
        --franchise naruto \
        [--resolve_by_scope]  # Auto-resolve conflicts by scope priority
        [--tag release-v1]    # Optional version tag

Outputs:
    - glossary/compiled.yaml (on success)
    - glossary/compiled.lock.json (on success)
    - glossary/conflicts_report.json (if conflicts and no --resolve_by_scope)

Conflict handling:
    - Default: FAIL FAST - exit with error if conflicts found
    - --resolve_by_scope: Auto-resolve by priority (project > ip > genre > base)
"""

import argparse
import csv
import hashlib
import json
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple

try:
    import yaml
except ImportError:
    print("❌ Error: PyYAML is required. Install with: pip install pyyaml")
    sys.exit(1)


# Scope priority (higher = more specific, wins)
SCOPE_PRIORITY = {
    "project": 4,
    "ip": 3,
    "genre": 2,
    "base": 1,
    "": 0
}
COMPILED_PASSTHROUGH_FIELDS = [
    "targets",
    "status",
    "language_pair",
    "tags",
    "confidence",
    "preferred_compact",
    "avoid_long_form",
    "note",
    "notes",
    "source",
    "source_file",
]


def configure_standard_streams() -> None:
    if sys.platform != 'win32':
        return
    import io
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        if not stream or not hasattr(stream, "buffer"):
            continue
        try:
            wrapped = io.TextIOWrapper(stream.buffer, encoding='utf-8', errors='replace')
            setattr(sys, stream_name, wrapped)
        except Exception:
            pass


def load_approved(path: str) -> List[Dict[str, Any]]:
    """Load approved entries from a single YAML and inherit file-level metadata when useful."""
    yaml_path = Path(path)
    if not yaml_path.exists():
        return []

    with open(yaml_path, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f) or {}

    meta = data.get("meta", {}) if isinstance(data, dict) else {}
    inherited_scope = str(meta.get("scope", "")).strip()
    inherited_language_pair = str(meta.get("language_pair", "")).strip()
    inherited_source = str(meta.get("source", yaml_path.as_posix())).strip() or yaml_path.as_posix()

    entries: List[Dict[str, Any]] = []
    raw_entries = data.get("entries", []) if isinstance(data, dict) else []
    for raw_entry in raw_entries:
        if not isinstance(raw_entry, dict):
            continue
        entry = dict(raw_entry)
        if inherited_scope and not str(entry.get("scope", "")).strip():
            entry["scope"] = inherited_scope
        if inherited_language_pair and not str(entry.get("language_pair", "")).strip():
            entry["language_pair"] = inherited_language_pair
        if not str(entry.get("source_file", "")).strip():
            entry["source_file"] = yaml_path.as_posix()
        if not str(entry.get("source", "")).strip():
            entry["source"] = inherited_source
        entries.append(entry)

    return entries


def load_approved_sources(paths: List[str]) -> List[Dict[str, Any]]:
    """Load and concatenate entries from multiple approved YAML files."""
    merged: List[Dict[str, Any]] = []
    for path in paths:
        merged.extend(load_approved(path))
    return merged


def detect_conflicts(entries: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    """
    Detect conflicts: same term_zh with different term_ru.
    
    Returns: {term_zh: [list of conflicting entries]}
    """
    by_term = defaultdict(list)
    
    for e in entries:
        term_zh = (e.get("term_zh") or "").strip()
        if term_zh:
            by_term[term_zh].append(e)
    
    conflicts = {}
    for term_zh, group in by_term.items():
        unique_ru = set((e.get("term_ru") or "").strip() for e in group)
        if len(unique_ru) > 1:
            conflicts[term_zh] = group
    
    return conflicts


def resolve_by_scope(entries: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Resolve conflicts by selecting highest priority scope.
    
    Returns: winning entry
    """
    if not entries:
        return {}
    
    def scope_key(e):
        scope = (e.get("scope") or "").strip().lower()
        return SCOPE_PRIORITY.get(scope, 0)
    
    # Sort by scope priority descending
    sorted_entries = sorted(entries, key=scope_key, reverse=True)
    return sorted_entries[0]


def build_compiled_entry(entry: Dict[str, Any]) -> Dict[str, Any]:
    compiled = {
        "term_zh": (entry.get("term_zh") or "").strip(),
        "term_ru": (entry.get("term_ru") or "").strip(),
        "scope": entry.get("scope", "base"),
    }
    for field in COMPILED_PASSTHROUGH_FIELDS:
        value = entry.get(field)
        if value in (None, "", [], {}):
            continue
        compiled[field] = value
    return compiled


def compile_entries(entries: List[Dict[str, Any]], 
                    resolve_conflicts: bool = False) -> Tuple[List[Dict[str, Any]], Dict]:
    """
    Compile entries, handling conflicts.
    
    Returns: (compiled_entries, conflicts_report)
    """
    conflicts = detect_conflicts(entries)
    conflicts_report = {
        "has_conflicts": bool(conflicts),
        "conflicts": []
    }
    
    if conflicts:
        for term_zh, group in conflicts.items():
            conflict_entry = {
                "term_zh": term_zh,
                "candidates": [
                    {
                        "term_ru": e.get("term_ru", ""),
                        "scope": e.get("scope", "base"),
                        "approved_at": e.get("approved_at", "")
                    }
                    for e in group
                ],
                "resolution": None
            }
            
            if resolve_conflicts:
                winner = resolve_by_scope(group)
                conflict_entry["resolution"] = {
                    "term_ru": winner.get("term_ru", ""),
                    "scope": winner.get("scope", "base"),
                    "method": "scope_priority"
                }
            
            conflicts_report["conflicts"].append(conflict_entry)
    
    if conflicts and not resolve_conflicts:
        # Fail fast - return empty compiled
        return [], conflicts_report
    
    # Build compiled entries (deduplicated)
    compiled = {}
    for e in entries:
        term_zh = (e.get("term_zh") or "").strip()
        if not term_zh:
            continue
        
        if term_zh in conflicts:
            if resolve_conflicts:
                # Use resolved winner
                winner = resolve_by_scope(conflicts[term_zh])
                compiled[term_zh] = build_compiled_entry(winner)
        else:
            # No conflict, use as-is (first wins if duplicate)
            if term_zh not in compiled:
                compiled[term_zh] = build_compiled_entry(e)
    
    return list(compiled.values()), conflicts_report


def compute_hash(entries: List[Dict[str, Any]]) -> str:
    """Compute SHA256 hash of entries for versioning."""
    # Sort for deterministic hash
    sorted_entries = sorted(entries, key=lambda e: e.get("term_zh", ""))
    content = json.dumps(sorted_entries, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(content.encode('utf-8')).hexdigest()[:16]


def get_next_version(lock_path: str) -> str:
    """Get next version number (YYYY.MM.DD.N format)."""
    today = datetime.now().strftime("%Y.%m.%d")
    
    if not Path(lock_path).exists():
        return f"{today}.1"
    
    try:
        with open(lock_path, 'r', encoding='utf-8') as f:
            lock = json.load(f)
        
        existing_version = lock.get("version", "")
        if existing_version.startswith(today):
            # Increment N
            parts = existing_version.split(".")
            if len(parts) == 4:
                n = int(parts[3]) + 1
                return f"{today}.{n}"
        
        return f"{today}.1"
    except Exception:
        return f"{today}.1"


def save_compiled(path: str, entries: List[Dict[str, Any]]) -> None:
    """Save compiled entries to YAML."""
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    
    data = {
        "meta": {
            "type": "compiled",
            "entry_count": len(entries),
            "note": "Runtime read-only. Do not edit directly."
        },
        "entries": entries
    }
    
    with open(path, 'w', encoding='utf-8') as f:
        yaml.dump(data, f, allow_unicode=True, default_flow_style=False, sort_keys=False)


def save_lock(path: str, version: str, hash_val: str, entry_count: int,
              language_pair: str, genre: str, franchise: str, 
              source: str, tag: Optional[str] = None) -> None:
    """Save lock file with version info."""
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    
    lock = {
        "version": version,
        "hash": f"sha256:{hash_val}",
        "compiled_at": datetime.now().isoformat(),
        "entry_count": entry_count,
        "language_pair": language_pair,
        "genre": genre,
        "franchise": franchise,
        "source": source
    }
    
    if tag:
        lock["tag"] = tag
    
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(lock, f, ensure_ascii=False, indent=2)


def save_conflicts_report(path: str, report: Dict) -> None:
    """Save conflicts report to JSON."""
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)


def main():
    configure_standard_streams()
    ap = argparse.ArgumentParser(
        description="Compile approved glossary into runtime artifact"
    )
    ap.add_argument(
        "--approved",
        action="append",
        default=None,
        help="Input approved YAML. Repeat to merge multiple sources (default: glossary/approved.yaml)",
    )
    ap.add_argument("--out_compiled", default="glossary/compiled.yaml",
                    help="Output compiled YAML (default: glossary/compiled.yaml)")
    ap.add_argument("--language_pair", default="zh-CN->ru-RU",
                    help="Language pair identifier")
    ap.add_argument("--genre", default="",
                    help="Genre (e.g., anime, rpg)")
    ap.add_argument("--franchise", default="",
                    help="Franchise/IP (e.g., naruto, pokemon)")
    ap.add_argument("--resolve_by_scope", action="store_true",
                    help="Auto-resolve conflicts by scope priority (default: fail fast)")
    ap.add_argument("--tag", default=None,
                    help="Optional version tag")
    ap.add_argument("--dry-run", action="store_true",
                    help="Validate without writing output")
    args = ap.parse_args()

    approved_paths = args.approved or ["glossary/approved.yaml"]

    print("🔧 Glossary Compile")
    print(f"   Input: {', '.join(approved_paths)}")
    print(f"   Output: {args.out_compiled}")
    print(f"   Language pair: {args.language_pair}")
    if args.genre:
        print(f"   Genre: {args.genre}")
    if args.franchise:
        print(f"   Franchise: {args.franchise}")
    print(f"   Conflict resolution: {'scope priority' if args.resolve_by_scope else 'fail fast'}")
    print()
    
    # Load approved
    missing_paths = [path for path in approved_paths if not Path(path).exists()]
    if missing_paths:
        print(f"❌ Approved file not found: {missing_paths[0]}")
        return 1

    entries = load_approved_sources(approved_paths)
    print(f"✅ Loaded {len(entries)} approved entries")
    
    if not entries:
        print("⚠️  No entries to compile")
        return 0
    
    # Compile
    compiled, conflicts_report = compile_entries(entries, args.resolve_by_scope)
    
    # Check for unresolved conflicts
    if conflicts_report["has_conflicts"] and not args.resolve_by_scope:
        print()
        print("❌ CONFLICTS DETECTED - Compilation failed")
        print()
        print(f"   {len(conflicts_report['conflicts'])} term(s) have conflicting translations:")
        
        for c in conflicts_report["conflicts"][:5]:  # Show first 5
            print(f"   - {c['term_zh']}:")
            for cand in c["candidates"]:
                print(f"       • {cand['term_ru']} (scope: {cand['scope']})")
        
        if len(conflicts_report["conflicts"]) > 5:
            print(f"   ... and {len(conflicts_report['conflicts']) - 5} more")
        
        # Save conflicts report
        conflicts_path = str(Path(args.out_compiled).parent / "conflicts_report.json")
        
        if not args.dry_run:
            save_conflicts_report(conflicts_path, conflicts_report)
            print()
            print(f"📋 Conflicts report saved to: {conflicts_path}")
        
        print()
        print("💡 To resolve:")
        print("   1. Edit glossary/approved.yaml to remove duplicate translations")
        print("   2. Or run with --resolve_by_scope to auto-select by priority")
        
        return 1
    
    # Compile success
    print(f"✅ Compiled {len(compiled)} unique entries")
    
    if conflicts_report["has_conflicts"]:
        resolved = len(conflicts_report["conflicts"])
        print(f"✅ Resolved {resolved} conflicts by scope priority")
    
    # Compute version info
    lock_path = str(Path(args.out_compiled).with_suffix('.lock.json'))
    version = get_next_version(lock_path)
    hash_val = compute_hash(compiled)
    
    print(f"✅ Version: {version}")
    print(f"✅ Hash: sha256:{hash_val}")
    
    if args.dry_run:
        print()
        print("=" * 60)
        print("DRY-RUN MODE - Validation Summary")
        print("=" * 60)
        print(f"[OK] Would write {len(compiled)} entries to {args.out_compiled}")
        print(f"[OK] Would write lock to {lock_path}")
        print("[OK] Dry-run validation PASSED")
        print("=" * 60)
        return 0
    
    # Save outputs
    save_compiled(args.out_compiled, compiled)
    save_lock(
        lock_path, version, hash_val, len(compiled),
        args.language_pair, args.genre, args.franchise,
        ",".join(approved_paths), args.tag
    )
    
    print()
    print(f"✅ Saved compiled glossary to: {args.out_compiled}")
    print(f"✅ Saved lock file to: {lock_path}")
    
    return 0


if __name__ == "__main__":
    sys.exit(main() or 0)
