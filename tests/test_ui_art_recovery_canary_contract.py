import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import build_ui_art_recovery_canary
import build_ui_art_recovery_slice_canary
import run_ui_art_live_batch
import ui_art_canary_compare


def _write_csv(path: Path, rows: list[dict], encoding: str = "utf-8-sig") -> None:
    with path.open("w", encoding=encoding, newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _make_row(index: int, category: str, source_zh: str) -> dict:
    return {
        "batch_row_id": str(index),
        "source_string_id": f"SRC_{index:04d}",
        "working_string_id": f"UIART_{index:06d}",
        "string_id": f"UIART_{index:06d}",
        "source_zh": source_zh,
        "target_text": "",
        "source_len_clean": str(len(source_zh)),
        "placeholder_budget": "0",
        "max_len_target": "8",
        "max_len_review_limit": "10",
        "ui_art_category": category,
        "compact_rule": "compact_preferred",
        "compact_mapping_status": "optional",
        "status": "ready",
    }


def test_build_ui_art_recovery_canary_backfills_badge_shortfall():
    rows = []
    idx = 1
    for source in ["胜", "败", "域"] * 15:
        rows.append(_make_row(idx, "badge_micro_1c", source))
        idx += 1
    for source in ["首充", "福利", "极品", "热销", "推荐", "限定", "新品", "极品", "推荐", "新品", "福利", "热销", "限定"]:
        rows.append(_make_row(idx, "badge_micro_2c", source))
        idx += 1
    for source in ["挑战", "排行", "排行榜", "商店", "支援", "图鉴", "重生", "兑换", "修罗模式"] * 10:
        rows.append(_make_row(idx, "label_generic_short", source))
        idx += 1
    for source in ["巅峰列传", "比赛商城", "忍界远征", "木叶特训", "忍者秘藏"] * 15:
        rows.append(_make_row(idx, "title_name_short", source))
        idx += 1
    for source in ["奖励预览", "充值", "礼包", "直购礼包", "限时折扣"] * 10:
        rows.append(_make_row(idx, "promo_short", source))
        idx += 1
    for source in ["元素之力", "秘卷奥义", "战魂之刃", "修罗模式·极", "套装之印"] * 8:
        rows.append(_make_row(idx, "item_skill_name", source))
        idx += 1
    for source in ["击破气球获得幸运值，累满幸运必得大奖", "当日奖励错过后将无法补领，请及时取签"] * 12:
        rows.append(_make_row(idx, "slogan_long", source))
        idx += 1

    selected, manifest = build_ui_art_recovery_canary.select_rows(rows)

    counts = {}
    for row in selected:
        counts[row["ui_art_category"]] = counts.get(row["ui_art_category"], 0) + 1

    assert len(selected) == 220
    assert counts["badge_micro_2c"] == 13
    assert manifest["category_shortfalls"]["badge_micro_2c"] == 17
    assert manifest["shortage_after_backfill"] == 0
    assert manifest["priority_term_hits"]["挑战"] > 0


def test_run_ui_art_live_batch_detects_prepared_input(tmp_path):
    prepared_csv = tmp_path / "prepared.csv"
    _write_csv(
        prepared_csv,
        [
            {
                "batch_row_id": "1",
                "source_string_id": "A1",
                "working_string_id": "UIART_000001",
                "string_id": "UIART_000001",
                "source_zh": "挑战",
                "ui_art_category": "label_generic_short",
                "max_len_target": "8",
                "max_len_review_limit": "10",
                "status": "ready",
            }
        ],
    )

    assert run_ui_art_live_batch.is_prepared_ui_art_input(prepared_csv) is True
    summary = run_ui_art_live_batch.summarize_prepared_rows(prepared_csv)
    assert summary["ready_rows"] == 1
    assert summary["ui_art_category_counts"]["label_generic_short"] == 1


def test_run_ui_art_live_batch_generic_batch_metadata_and_glossary_inputs(tmp_path):
    manifest = run_ui_art_live_batch.manifest_for(
        run_id="ui_art_live_run01",
        batch_root=tmp_path / "batch",
        run_dir=tmp_path / "batch" / "runs" / "ui_art_live_run01",
        source_fingerprint={"sha256": "abc"},
        batch_type="ui_art_live",
    )

    approved = run_ui_art_live_batch.resolve_approved_glossaries(
        ["glossary/zhCN_ruRU/project_ui_art_short.yaml", "glossary/approved.yaml"]
    )

    assert manifest["batch_type"] == "ui_art_live"
    assert approved == ["glossary/approved.yaml", "glossary/zhCN_ruRU/project_ui_art_short.yaml"]


def test_ui_art_canary_compare_python_falls_back_to_sys_executable(tmp_path):
    python_path = ui_art_canary_compare.ensure_python(tmp_path)
    assert python_path == Path(sys.executable)


def test_run_ui_art_live_batch_defers_compact_review_errors(tmp_path):
    report_path = tmp_path / "qa_report.json"
    actionable_path = tmp_path / "qa_actionable.json"
    repaired_csv = tmp_path / "ui_art_repaired_hard.csv"
    qa_recheck = tmp_path / "ui_art_qa_hard_report_recheck.json"
    repaired_csv.write_text("string_id,target_text\nUIART_000001,Топ\n", encoding="utf-8")
    report_path.write_text(
        json.dumps(
            {
                "has_errors": True,
                "errors": [
                    {"type": "compact_mapping_missing", "string_id": "UIART_000001"},
                    {"type": "length_overflow", "string_id": "UIART_000002"},
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    qa_recheck.write_text(
        json.dumps(
            {
                "has_errors": True,
                "errors": [
                    {"type": "compact_term_miss", "string_id": "UIART_000001"},
                    {"type": "length_overflow", "string_id": "UIART_000002"},
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    stats = run_ui_art_live_batch.build_actionable_hard_tasks(report_path, actionable_path)

    assert stats["actionable_errors"] == 0
    assert stats["deferred_review_errors"] == 2
    assert run_ui_art_live_batch.blocking_errors_remain(qa_recheck) is False
    assert (
        run_ui_art_live_batch.current_translation_path(
            {"qa_recheck_report": qa_recheck, "repair_output": repaired_csv, "translated_csv": tmp_path / "translated.csv"}
        )
        == repaired_csv
    )


def test_ui_art_canary_compare_evaluates_promotion_thresholds():
    baseline_hard = {
        "by_category": {
            "badge_micro_1c": {"denominator": 30, "hard_fail_rows": 20, "hard_fail_rate": 0.6667, "issue_type_counts": {}},
            "badge_micro_2c": {"denominator": 13, "hard_fail_rows": 11, "hard_fail_rate": 0.8462, "issue_type_counts": {}},
            "label_generic_short": {"denominator": 45, "hard_fail_rows": 30, "hard_fail_rate": 0.6667, "issue_type_counts": {}},
            "title_name_short": {"denominator": 45, "hard_fail_rows": 28, "hard_fail_rate": 0.6222, "issue_type_counts": {}},
            "slogan_long": {"denominator": 20, "hard_fail_rows": 15, "hard_fail_rate": 0.75, "issue_type_counts": {"length_overflow": 10, "line_budget_overflow": 5}},
        },
        "invariant_counts": {"forbidden_hit": 1},
    }
    canary_hard = {
        "by_category": {
            "badge_micro_1c": {"denominator": 30, "hard_fail_rows": 10, "hard_fail_rate": 0.3333, "issue_type_counts": {}},
            "badge_micro_2c": {"denominator": 13, "hard_fail_rows": 5, "hard_fail_rate": 0.3846, "issue_type_counts": {}},
            "label_generic_short": {"denominator": 45, "hard_fail_rows": 12, "hard_fail_rate": 0.2667, "issue_type_counts": {}},
            "title_name_short": {"denominator": 45, "hard_fail_rows": 16, "hard_fail_rate": 0.3556, "issue_type_counts": {}},
            "slogan_long": {"denominator": 20, "hard_fail_rows": 4, "hard_fail_rate": 0.2, "issue_type_counts": {"line_budget_overflow": 3, "length_overflow": 1}},
        },
        "invariant_counts": {"forbidden_hit": 1},
    }

    result = ui_art_canary_compare.evaluate_promotion(canary_hard, baseline_hard)

    assert result["thresholds"]["badge_micro_combined"] is True
    assert result["thresholds"]["label_generic_short"] is True
    assert result["thresholds"]["title_name_short"] is True
    assert result["thresholds"]["slogan_long"] is True
    assert result["thresholds"]["hard_invariants"] is True
    assert result["decision"] == "pass_ready_for_full_rerun"


def test_build_ui_art_recovery_slice_canary_selects_98_rows():
    current_rows = []
    prior_rows = []
    idx = 1
    for category, count in {
        "badge_micro_2c": 13,
        "promo_short": 30,
        "item_skill_name": 20,
        "slogan_long": 20,
        "badge_micro_1c": 5,
        "label_generic_short": 5,
        "title_name_short": 5,
    }.items():
        for _ in range(count):
            row = _make_row(idx, category, f"{category}_{idx}")
            current_rows.append(dict(row))
            prior_rows.append(dict(row))
            idx += 1

    selected, manifest = build_ui_art_recovery_slice_canary.select_rows(current_rows, prior_rows)

    assert len(selected) == 98
    assert manifest["target_counts_from_prior_canary"]["promo_short"] == 30
    assert manifest["sentinel_counts"]["label_generic_short"] == 5


def test_recovery_builders_accept_custom_profiles():
    rows = [_make_row(1, "label_generic_short", "挑战"), _make_row(2, "promo_short", "奖励预览"), _make_row(3, "slogan_long", "长文案")]
    selected, manifest = build_ui_art_recovery_canary.select_rows(
        rows,
        target_total=2,
        category_quotas={"label_generic_short": 1, "promo_short": 1},
        priority_terms=["奖励预览"],
        primary_backfill=["label_generic_short"],
        secondary_backfill=["promo_short"],
        seed=7,
    )
    assert len(selected) == 2
    assert manifest["target_total"] == 2
    assert manifest["seed"] == 7

    current_rows = [_make_row(10, "promo_short", "奖励预览"), _make_row(11, "badge_micro_1c", "胜")]
    prior_rows = [dict(current_rows[0]), dict(current_rows[1])]
    slice_selected, slice_manifest = build_ui_art_recovery_slice_canary.select_rows(
        current_rows,
        prior_rows,
        target_categories={"promo_short"},
        sentinel_counts={"badge_micro_1c": 1},
        expected_total=2,
    )
    assert len(slice_selected) == 2
    assert slice_manifest["target_categories"] == ["promo_short"]


def test_ui_art_canary_compare_evaluates_focused_slice_profile():
    baseline_hard = {
        "by_category": {
            "badge_micro_2c": {"denominator": 13, "hard_fail_rows": 11, "hard_fail_rate": 0.8462, "issue_type_counts": {}, "source_fail_counts": {"奖励预览": 0}},
            "promo_short": {"denominator": 30, "hard_fail_rows": 16, "hard_fail_rate": 0.5333, "issue_type_counts": {}, "source_fail_counts": {"奖励预览": 5, "充值返利": 7}},
            "item_skill_name": {"denominator": 20, "hard_fail_rows": 20, "hard_fail_rate": 1.0, "issue_type_counts": {}, "source_fail_counts": {}},
            "slogan_long": {"denominator": 20, "hard_fail_rows": 13, "hard_fail_rate": 0.65, "issue_type_counts": {"length_overflow": 13}, "source_fail_counts": {}},
            "badge_micro_1c": {"denominator": 5, "hard_fail_rows": 1, "hard_fail_rate": 0.2, "issue_type_counts": {}, "source_fail_counts": {}},
            "label_generic_short": {"denominator": 5, "hard_fail_rows": 0, "hard_fail_rate": 0.0, "issue_type_counts": {}, "source_fail_counts": {}},
            "title_name_short": {"denominator": 5, "hard_fail_rows": 0, "hard_fail_rate": 0.0, "issue_type_counts": {}, "source_fail_counts": {}},
        },
        "invariant_counts": {"forbidden_hit": 0},
    }
    canary_hard = {
        "by_category": {
            "badge_micro_2c": {"denominator": 13, "hard_fail_rows": 0, "hard_fail_rate": 0.0, "issue_type_counts": {}, "source_fail_counts": {}},
            "promo_short": {"denominator": 30, "hard_fail_rows": 3, "hard_fail_rate": 0.1, "issue_type_counts": {"promo_expansion_forbidden": 3}, "source_fail_counts": {"奖励预览": 1, "充值返利": 1}},
            "item_skill_name": {"denominator": 20, "hard_fail_rows": 6, "hard_fail_rate": 0.3, "issue_type_counts": {"length_overflow": 6}, "source_fail_counts": {}},
            "slogan_long": {"denominator": 20, "hard_fail_rows": 4, "hard_fail_rate": 0.2, "issue_type_counts": {"headline_budget_overflow": 3, "line_budget_overflow": 1}, "source_fail_counts": {}},
            "badge_micro_1c": {"denominator": 5, "hard_fail_rows": 1, "hard_fail_rate": 0.2, "issue_type_counts": {}, "source_fail_counts": {}},
            "label_generic_short": {"denominator": 5, "hard_fail_rows": 0, "hard_fail_rate": 0.0, "issue_type_counts": {}, "source_fail_counts": {}},
            "title_name_short": {"denominator": 5, "hard_fail_rows": 0, "hard_fail_rate": 0.0, "issue_type_counts": {}, "source_fail_counts": {}},
        },
        "invariant_counts": {"forbidden_hit": 0},
    }

    result = ui_art_canary_compare.evaluate_promotion(canary_hard, baseline_hard, profile="focused_recovery_slice_v2")

    assert result["thresholds"]["badge_micro_2c"] is True
    assert result["thresholds"]["promo_short"] is True
    assert result["thresholds"]["promo_repeated_clusters"] is True
    assert result["thresholds"]["item_skill_name"] is True
    assert result["thresholds"]["slogan_long"] is True
    assert result["decision"] == "ready_for_full_rerun"
