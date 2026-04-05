import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import ui_art_full_rerun_assess


def _write_csv(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _write_jsonl(path: Path, items: list[dict]) -> None:
    path.write_text("\n".join(json.dumps(item, ensure_ascii=False) for item in items) + "\n", encoding="utf-8")


def _prepared_row(string_id: str, source_zh: str, category: str, *, prefill: str = "", compact: str = "", mode: str = "") -> dict:
    return {
        "string_id": string_id,
        "source_zh": source_zh,
        "ui_art_category": category,
        "translation_mode": mode,
        "prefill_target_ru": prefill,
        "ui_art_compact_term": compact,
        "compact_mapping_status": "approved_available" if compact or prefill else "optional",
        "status": "ready",
    }


def test_classify_soft_item_marks_prefill_terminology_as_compact_policy_noise():
    row = _prepared_row("UIART_1", "推荐", "badge_micro_2c", prefill="Топ", compact="Топ", mode="prefill_exact")
    item = {"string_id": "UIART_1", "type": "terminology"}
    assert ui_art_full_rerun_assess.classify_soft_item(item, row) == "compact_policy_noise"


def test_classify_soft_item_marks_length_as_true_residual():
    row = _prepared_row("UIART_2", "九尾之劫", "item_skill_name")
    item = {"string_id": "UIART_2", "type": "length"}
    assert ui_art_full_rerun_assess.classify_soft_item(item, row) == "true_residual"


def test_build_assessment_outputs_family_and_noise_split(tmp_path):
    baseline_dir = tmp_path / "baseline"
    focused_dir = tmp_path / "focused"
    rerun_dir = tmp_path / "rerun"
    for path in (baseline_dir, focused_dir, rerun_dir):
        path.mkdir(parents=True)

    baseline_manifest = {
        "run_id": "ui_art_live_baseline_run01",
        "final_summary": {
            "hard_qa_recheck_errors": 3002,
            "hard_qa_recheck_error_counts": {"length_overflow": 3002},
            "review_queue_total": 3189,
            "soft_qa_major": 2713,
        },
    }
    rerun_manifest = {
        "run_id": "ui_art_full_rerun_run01",
        "final_summary": {
            "hard_qa_recheck_errors": 120,
            "hard_qa_recheck_error_counts": {"length_overflow": 100, "promo_expansion_forbidden": 20},
            "review_queue_total": 140,
            "soft_qa_major": 240,
        },
    }
    focused_manifest = {"run_id": "ui_art_recovery_slice_anchor_run02"}
    focused_compare = {
        "canary": {
            "hard": {
                "by_category": {
                    "badge_micro_2c": {"hard_fail_rate": 0.0},
                    "promo_short": {"hard_fail_rate": 0.0571},
                    "item_skill_name": {"hard_fail_rate": 0.1176},
                    "slogan_long": {"hard_fail_rate": 0.1667},
                }
            }
        }
    }

    (baseline_dir / "run_manifest.json").write_text(json.dumps(baseline_manifest), encoding="utf-8")
    (focused_dir / "run_manifest.json").write_text(json.dumps(focused_manifest), encoding="utf-8")
    (focused_dir / "ui_art_compare.json").write_text(json.dumps(focused_compare), encoding="utf-8")
    (rerun_dir / "run_manifest.json").write_text(json.dumps(rerun_manifest), encoding="utf-8")

    _write_csv(
        baseline_dir / "source_ui_art_prepared.csv",
        [
            _prepared_row("UIART_1", "推荐", "badge_micro_2c"),
            _prepared_row("UIART_2", "充值返利", "promo_short"),
            _prepared_row("UIART_3", "九尾之劫", "item_skill_name"),
            _prepared_row("UIART_4", "为了创造新的世界", "slogan_long"),
        ],
    )
    _write_csv(
        rerun_dir / "source_ui_art_prepared.csv",
        [
            _prepared_row("UIART_1", "推荐", "badge_micro_2c", prefill="Топ", compact="Топ", mode="prefill_exact"),
            _prepared_row("UIART_2", "充值返利", "promo_short", prefill="Донат+", compact="Донат+", mode="prefill_exact"),
            _prepared_row("UIART_3", "九尾之劫", "item_skill_name"),
            _prepared_row("UIART_4", "为了创造新的世界", "slogan_long"),
        ],
    )

    _write_csv(
        baseline_dir / "ui_art_review_queue.csv",
        [
            {"string_id": "UIART_1", "ui_art_category": "badge_micro_2c", "severity": "major"},
            {"string_id": "UIART_2", "ui_art_category": "promo_short", "severity": "critical"},
            {"string_id": "UIART_3", "ui_art_category": "item_skill_name", "severity": "critical"},
            {"string_id": "UIART_4", "ui_art_category": "slogan_long", "severity": "major"},
        ],
    )
    _write_csv(
        rerun_dir / "ui_art_review_queue.csv",
        [
            {"string_id": "UIART_2", "ui_art_category": "promo_short", "severity": "major"},
            {"string_id": "UIART_3", "ui_art_category": "item_skill_name", "severity": "major"},
            {"string_id": "UIART_4", "ui_art_category": "slogan_long", "severity": "warning"},
        ],
    )

    _write_jsonl(
        rerun_dir / "ui_art_soft_tasks.jsonl",
        [
            {"string_id": "UIART_1", "type": "terminology"},
            {"string_id": "UIART_2", "type": "style_contract"},
            {"string_id": "UIART_3", "type": "length"},
            {"string_id": "UIART_4", "type": "headline_budget_overflow"},
        ],
    )
    (rerun_dir / "ui_art_soft_qa_report.json").write_text(
        json.dumps(
            {
                "hard_gate": {
                    "violations": [
                        {"string_id": "UIART_1", "type": "terminology"},
                        {"string_id": "UIART_3", "type": "length"},
                    ]
                }
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    payload = ui_art_full_rerun_assess.build_assessment(baseline_dir, focused_dir, rerun_dir)

    assert payload["full_run_delta"]["baseline_hard_total"] == 3002
    assert payload["family_residuals"]["promo_short"]["rerun_review_rows"] == 1
    assert payload["family_residuals"]["badge_micro_2c"]["focused_anchor_hard_fail_rate"] == 0.0
    assert payload["soft_qa"]["noise_split"]["compact_policy_noise"]["task_count"] == 2
    assert payload["soft_qa"]["noise_split"]["true_residual"]["task_count"] == 2
    assert payload["soft_qa"]["hard_gate"]["violation_count"] == 2
