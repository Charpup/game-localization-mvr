#!/usr/bin/env python3
"""Check script authority and drift between main_worktree and repo-level src/scripts."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _main_worktree_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _hash_file(path: Path) -> str:
    digest = hashlib.sha1()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _collect_tree_hashes(root: Path) -> Dict[str, str]:
    if not root.exists():
        return {}
    out: Dict[str, str] = {}
    for path in sorted(root.glob("*.py")):
        out[path.name] = _hash_file(path)
    return out


def _sorted_names(values: Iterable[str]) -> List[str]:
    return sorted({value for value in values if value})


def build_authority_report(manifest: dict) -> dict:
    main_root = _main_worktree_root()
    authority_root = (main_root / manifest["authority_root"]).resolve()
    compat_root = (main_root / manifest["compat_root"]).resolve()
    archive_root = (main_root / manifest["archive_root"]).resolve()

    authority_hashes = _collect_tree_hashes(authority_root)
    compat_hashes = _collect_tree_hashes(compat_root)

    common = set(authority_hashes) & set(compat_hashes)
    same = _sorted_names(name for name in common if authority_hashes[name] == compat_hashes[name])
    diff = _sorted_names(name for name in common if authority_hashes[name] != compat_hashes[name])
    only_main = _sorted_names(set(authority_hashes) - set(compat_hashes))
    only_src = _sorted_names(set(compat_hashes) - set(authority_hashes))

    mirror_required = manifest.get("mirror_required", [])
    alert_only = manifest.get("alert_only_drift", [])
    archived = manifest.get("archived", [])

    mirror_missing = _sorted_names(name for name in mirror_required if name not in compat_hashes)
    mirror_drift = _sorted_names(name for name in mirror_required if name in diff)
    alert_only_drift = _sorted_names(name for name in alert_only if name in diff or name in only_main)
    archived_still_live = _sorted_names(name for name in archived if name in authority_hashes)
    archived_missing_copy = _sorted_names(name for name in archived if not (archive_root / name).exists())

    status = "ok"
    if mirror_missing or mirror_drift or archived_still_live or archived_missing_copy:
        status = "fail"
    elif alert_only_drift:
        status = "warn"

    return {
        "type": "script_authority_report",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "authority_root": str(authority_root),
        "compat_root": str(compat_root),
        "archive_root": str(archive_root),
        "keep_chain": manifest.get("keep_chain", []),
        "protected_exclusions": manifest.get("protected_exclusions", []),
        "summary": {
            "common": len(common),
            "same": len(same),
            "diff": len(diff),
            "only_main": len(only_main),
            "only_src": len(only_src)
        },
        "same": same,
        "diff": diff,
        "only_main": only_main,
        "only_src": only_src,
        "mirror_required_missing": mirror_missing,
        "mirror_required_drift": mirror_drift,
        "alert_only_drift": alert_only_drift,
        "archived_still_live_in_authority": archived_still_live,
        "archived_missing_copy": archived_missing_copy,
        "compat_notes": manifest.get("compat_notes", {})
    }


def _print_report(report: dict) -> None:
    print(f"Authority root: {report['authority_root']}")
    print(f"Compat root:    {report['compat_root']}")
    print(f"Archive root:   {report['archive_root']}")
    print(
        "Summary: "
        f"common={report['summary']['common']} "
        f"same={report['summary']['same']} "
        f"diff={report['summary']['diff']} "
        f"only_main={report['summary']['only_main']} "
        f"only_src={report['summary']['only_src']}"
    )
    if report["mirror_required_missing"]:
        print("Mirror required missing:", ", ".join(report["mirror_required_missing"]))
    if report["mirror_required_drift"]:
        print("Mirror required drift:", ", ".join(report["mirror_required_drift"]))
    if report["alert_only_drift"]:
        print("Alert-only drift:", ", ".join(report["alert_only_drift"]))
    if report["archived_still_live_in_authority"]:
        print("Archived scripts still live in authority:", ", ".join(report["archived_still_live_in_authority"]))
    if report["archived_missing_copy"]:
        print("Archived scripts missing copy:", ", ".join(report["archived_missing_copy"]))
    print("Status:", report["status"].upper())


def main() -> int:
    main_root = _main_worktree_root()
    parser = argparse.ArgumentParser(description="Check script authority and drift.")
    parser.add_argument(
        "--manifest",
        default=str(main_root / "workflow" / "script_authority_manifest.json"),
        help="Path to authority manifest JSON."
    )
    parser.add_argument(
        "--out",
        default="",
        help="Optional output JSON path for the authority report."
    )
    args = parser.parse_args()

    manifest = _load_json(Path(args.manifest))
    report = build_authority_report(manifest)
    _print_report(report)

    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    return 0 if report["status"] in {"ok", "warn"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
