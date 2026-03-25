#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from review_governance import append_feedback_entries


def _read_input_rows(path: str) -> List[Dict[str, Any]]:
    file_path = Path(path)
    if file_path.suffix.lower() == ".csv":
        with file_path.open("r", encoding="utf-8-sig", newline="") as fh:
            return list(csv.DictReader(fh))
    rows: List[Dict[str, Any]] = []
    with file_path.open("r", encoding="utf-8") as fh:
        for line_no, line in enumerate(fh, start=1):
            text = line.strip()
            if not text:
                continue
            payload = json.loads(text)
            if not isinstance(payload, dict):
                raise ValueError(f"Expected object at {path}:{line_no}")
            rows.append(payload)
    return rows


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Append human review feedback into the Phase 3 feedback log")
    parser.add_argument("--input", required=True, help="CSV or JSONL feedback input")
    parser.add_argument("--output", default="data/review_feedback_log.jsonl", help="Feedback log JSONL path")
    parser.add_argument("--feedback-source", default="human_review", help="Source artifact label for imported feedback")
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    rows = []
    decision_map = {
        "accepted": "approve",
        "approve": "approve",
        "rejected": "reject",
        "reject": "reject",
        "revised": "request_retranslate",
        "request_retranslate": "request_retranslate",
        "request_refresh": "request_refresh",
        "ignore": "ignore",
        "supersede": "supersede",
    }
    for row in _read_input_rows(args.input):
        payload = dict(row)
        payload.setdefault("reviewer", payload.get("review_owner") or "human-linguist")
        payload.setdefault("source_artifact", args.feedback_source)
        payload["decision"] = decision_map.get(str(payload.get("decision") or "").strip(), str(payload.get("decision") or "ignore"))
        rows.append(payload)
    appended = append_feedback_entries(args.output, rows)
    print(json.dumps({"status": "ok", "appended": len(appended), "output": args.output}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
