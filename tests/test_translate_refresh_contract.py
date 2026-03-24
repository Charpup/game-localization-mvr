import csv
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import translate_refresh


def _write_csv(path: Path, rows: list[dict]) -> None:
    fieldnames: list[str] = []
    for row in rows:
        for key in row.keys():
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def _write_glossary(path: Path) -> None:
    path.write_text(
        "\n".join(
            [
                "meta:",
                "  type: compiled",
                "entries:",
                "  - term_zh: 木叶",
                "    targets:",
                "      ru-RU: Коноха",
                "  - term_zh: 忍者",
                "    targets:",
                "      ru-RU: ниндзя",
            ]
        ),
        encoding="utf-8",
    )


def _write_style(path: Path) -> None:
    path.write_text("# style\n- keep concise\n", encoding="utf-8")


def _sample_translated_rows() -> list[dict]:
    return [
        {
            "string_id": "s1",
            "source_zh": "木叶入口",
            "tokenized_zh": "木叶入口",
            "target_text": "Старая Коноха вход",
            "target_locale": "ru-RU",
            "module_tag": "general",
        },
        {
            "string_id": "s2",
            "source_zh": "人工复核文案",
            "tokenized_zh": "人工复核文案",
            "target_text": "Нужна ручная проверка",
            "target_locale": "ru-RU",
            "module_tag": "general",
        },
        {
            "string_id": "s3",
            "source_zh": "未受影响",
            "tokenized_zh": "未受影响",
            "target_text": "Без изменений",
            "target_locale": "ru-RU",
            "module_tag": "general",
        },
        {
            "string_id": "s4",
            "source_zh": "任务阻断",
            "tokenized_zh": "任务阻断",
            "target_text": "Старый блок",
            "target_locale": "ru-RU",
            "module_tag": "general",
        },
    ]


def _sample_delta_rows() -> list[dict]:
    return [
        {
            "string_id": "s1",
            "source_zh": "木叶入口",
            "current_target": "Старая Коноха вход",
            "target_locale": "ru-RU",
            "content_class": "general",
            "risk_level": "low",
            "delta_types": ["term_changed"],
            "reason_codes": ["GLOSSARY_TERM_CHANGED"],
            "reason_text": "source depends on changed glossary term 木叶",
            "rule_refs": ["glossary"],
            "placeholder_locked": False,
            "manual_review_required": False,
            "manual_review_reason": "",
            "recommended_action": "auto_refresh",
        },
        {
            "string_id": "s2",
            "source_zh": "人工复核文案",
            "current_target": "Нужна ручная проверка",
            "target_locale": "ru-RU",
            "content_class": "general",
            "risk_level": "low",
            "delta_types": ["term_removed"],
            "reason_codes": ["GLOSSARY_TERM_REMOVED"],
            "reason_text": "manual review required",
            "rule_refs": ["glossary"],
            "placeholder_locked": False,
            "manual_review_required": True,
            "manual_review_reason": "hard gate reason(s): term_removed",
            "recommended_action": "manual_review",
        },
    ]


def _sample_task(
    task_id: str,
    string_id: str,
    task_type: str,
    current_target: str,
    source_text: str,
    target_locale: str = "ru-RU",
) -> dict:
    return {
        "task_id": task_id,
        "string_id": string_id,
        "task_type": task_type,
        "target_locale": target_locale,
        "reason_codes": ["TEST_REASON"],
        "trigger_change_ids": ["term_changed"],
        "depends_on_rules": ["glossary"],
        "source_artifacts": {"translated_csv": "translated.csv"},
        "target_constraints": {"content_class": "general", "risk_level": "low", "placeholder_locked": False},
        "placeholder_signature": {},
        "current_target": current_target,
        "expected_change_scope": "term_only" if task_type == "refresh" else "manual",
        "human_review_required": task_type in {"manual_review", "skip"},
        "review_owner": "human-linguist" if task_type in {"manual_review", "skip"} else "automation",
        "review_status": "pending" if task_type in {"manual_review", "skip"} else "not_required",
        "source_text": source_text,
        "source_zh": source_text,
        "manual_review_reason": "needs review" if task_type in {"manual_review", "skip"} else "",
    }


def _read_review_rows(path: Path) -> list[dict]:
    return list(csv.DictReader(path.open("r", encoding="utf-8-sig", newline="")))


def test_generate_only_writes_tasks_and_review_queue(tmp_path):
    translated_csv = tmp_path / "translated.csv"
    delta_rows = tmp_path / "delta_rows.jsonl"
    glossary = tmp_path / "compiled.yaml"
    style = tmp_path / "style.md"
    tasks_out = tmp_path / "tasks.jsonl"
    review_queue = tmp_path / "review.csv"
    manifest = tmp_path / "manifest.json"

    _write_csv(translated_csv, _sample_translated_rows())
    _write_jsonl(delta_rows, _sample_delta_rows())
    _write_glossary(glossary)
    _write_style(style)

    exit_code = translate_refresh.main(
        [
            "--delta-rows",
            str(delta_rows),
            "--translated",
            str(translated_csv),
            "--glossary",
            str(glossary),
            "--style",
            str(style),
            "--tasks-out",
            str(tasks_out),
            "--review-queue",
            str(review_queue),
            "--manifest",
            str(manifest),
            "--generate-only",
        ]
    )

    assert exit_code == 0
    task_rows = translate_refresh.read_jsonl(str(tasks_out))
    assert [task["task_type"] for task in task_rows] == ["refresh", "manual_review"]
    assert task_rows[0]["execution_status"] == "pending"
    assert task_rows[0]["final_status"] == "pending"
    assert task_rows[1]["execution_status"] == "review_handoff"
    assert task_rows[1]["final_status"] == "review_handoff"

    review_rows = _read_review_rows(review_queue)
    assert len(review_rows) == 1
    assert review_rows[0]["string_id"] == "s2"
    assert review_rows[0]["task_type"] == "manual_review"
    assert review_rows[0]["review_source"] == "initial_manual_review"
    assert review_rows[0]["final_status"] == "review_handoff"

    manifest_payload = json.loads(manifest.read_text(encoding="utf-8"))
    assert manifest_payload["mode"] == "generate_only"
    assert manifest_payload["overall_status"] == "review_handoff"
    assert manifest_payload["review_handoff"]["pending_count"] == 1
    assert manifest_payload["review_handoff"]["by_source"] == {"initial_manual_review": 1}
    assert manifest_payload["task_outcomes"]["counts_by_final_status"]["pending"] == 1
    assert manifest_payload["task_outcomes"]["counts_by_final_status"]["review_handoff"] == 1


def test_missing_required_task_field_fails_explicitly(tmp_path):
    translated_csv = tmp_path / "translated.csv"
    glossary = tmp_path / "compiled.yaml"
    style = tmp_path / "style.md"
    tasks_in = tmp_path / "bad_tasks.jsonl"

    _write_csv(translated_csv, _sample_translated_rows())
    _write_glossary(glossary)
    _write_style(style)

    bad_task = _sample_task("refresh:s1", "s1", "refresh", "Старая Коноха вход", "木叶入口")
    del bad_task["review_status"]
    _write_jsonl(tasks_in, [bad_task])

    with pytest.raises(ValueError, match="missing required field"):
        translate_refresh.main(
            [
                "--tasks-in",
                str(tasks_in),
                "--translated",
                str(translated_csv),
                "--glossary",
                str(glossary),
                "--style",
                str(style),
                "--generate-only",
            ]
        )


def test_retranslate_task_requires_source_text_in_tasks_in_contract(tmp_path):
    translated_csv = tmp_path / "translated.csv"
    glossary = tmp_path / "compiled.yaml"
    style = tmp_path / "style.md"
    tasks_in = tmp_path / "bad_retranslate_tasks.jsonl"

    _write_csv(translated_csv, _sample_translated_rows())
    _write_glossary(glossary)
    _write_style(style)

    bad_task = _sample_task("retranslate:s1", "s1", "retranslate", "Старая Коноха вход", "木叶入口")
    bad_task["expected_change_scope"] = "style_plus_term"
    del bad_task["source_text"]
    _write_jsonl(tasks_in, [bad_task])

    with pytest.raises(ValueError, match="retranslate tasks require source_text"):
        translate_refresh.main(
            [
                "--tasks-in",
                str(tasks_in),
                "--translated",
                str(translated_csv),
                "--glossary",
                str(glossary),
                "--style",
                str(style),
                "--generate-only",
            ]
        )


def test_executor_preserves_row_count_and_manual_review_row_is_not_overwritten(tmp_path, monkeypatch):
    translated_csv = tmp_path / "translated.csv"
    glossary = tmp_path / "compiled.yaml"
    style = tmp_path / "style.md"
    tasks_in = tmp_path / "tasks.jsonl"
    tasks_out = tmp_path / "tasks_out.jsonl"
    review_queue = tmp_path / "review.csv"
    manifest = tmp_path / "manifest.json"
    out_csv = tmp_path / "refreshed.csv"

    rows = _sample_translated_rows()
    _write_csv(translated_csv, rows)
    _write_glossary(glossary)
    _write_style(style)
    _write_jsonl(
        tasks_in,
        [
            _sample_task("refresh:s1", "s1", "refresh", "Старая Коноха вход", "木叶入口"),
            _sample_task("manual_review:s2", "s2", "manual_review", "Нужна ручная проверка", "人工复核文案"),
        ],
    )

    def fake_batch_llm_call(*, step, rows, **_kwargs):
        assert step == "translate_refresh_incremental"
        return [{"id": "s1", "updated_target": "Коноха вход"}]

    monkeypatch.setattr(translate_refresh, "batch_llm_call", fake_batch_llm_call)
    monkeypatch.setattr(
        translate_refresh,
        "run_qa_hard_gate",
        lambda *args, **kwargs: {
            "passed": True,
            "report_path": str(tmp_path / "qa_report.json"),
            "error_total": 0,
            "warning_total": 0,
            "failed_string_ids": [],
        },
    )

    exit_code = translate_refresh.main(
        [
            "--tasks-in",
            str(tasks_in),
            "--translated",
            str(translated_csv),
            "--glossary",
            str(glossary),
            "--style",
            str(style),
            "--tasks-out",
            str(tasks_out),
            "--review-queue",
            str(review_queue),
            "--manifest",
            str(manifest),
            "--out-csv",
            str(out_csv),
        ]
    )

    assert exit_code == 0
    output_rows = list(csv.DictReader(out_csv.open("r", encoding="utf-8-sig", newline="")))
    assert len(output_rows) == len(rows)
    assert {row["string_id"]: row["target_text"] for row in output_rows}["s1"] == "Коноха вход"
    assert {row["string_id"]: row["target_text"] for row in output_rows}["s2"] == "Нужна ручная проверка"

    review_rows = _read_review_rows(review_queue)
    assert [row["string_id"] for row in review_rows] == ["s2"]
    assert review_rows[0]["review_source"] == "initial_manual_review"
    assert review_rows[0]["execution_status"] == "review_handoff"
    assert review_rows[0]["final_status"] == "review_handoff"

    manifest_payload = json.loads(manifest.read_text(encoding="utf-8"))
    assert manifest_payload["post_gates"]["row_count_integrity"]["passed"] is True
    assert manifest_payload["execution"]["skipped_direct_write"] == 1
    assert manifest_payload["overall_status"] == "review_handoff"
    assert manifest_payload["task_outcomes"]["counts_by_execution_status"]["updated"] == 1
    assert manifest_payload["task_outcomes"]["counts_by_execution_status"]["review_handoff"] == 1
    assert manifest_payload["task_outcomes"]["counts_by_final_status"]["updated"] == 1
    assert manifest_payload["task_outcomes"]["counts_by_final_status"]["review_handoff"] == 1
    task_rows = translate_refresh.read_jsonl(str(tasks_out))
    by_task_id = {row["task_id"]: row for row in task_rows}
    assert by_task_id["refresh:s1"]["execution_status"] == "updated"
    assert by_task_id["refresh:s1"]["final_status"] == "updated"
    assert by_task_id["manual_review:s2"]["execution_status"] == "review_handoff"
    assert by_task_id["manual_review:s2"]["final_status"] == "review_handoff"


def test_executor_stages_output_and_keeps_final_path_clean_when_post_gate_fails(tmp_path, monkeypatch):
    translated_csv = tmp_path / "translated.csv"
    glossary = tmp_path / "compiled.yaml"
    style = tmp_path / "style.md"
    tasks_in = tmp_path / "tasks.jsonl"
    tasks_out = tmp_path / "tasks_out.jsonl"
    review_queue = tmp_path / "review.csv"
    manifest = tmp_path / "manifest.json"
    out_csv = tmp_path / "final.csv"

    _write_csv(translated_csv, _sample_translated_rows())
    _write_glossary(glossary)
    _write_style(style)
    _write_jsonl(tasks_in, [_sample_task("refresh:s1", "s1", "refresh", "Старая Коноха вход", "木叶入口")])

    monkeypatch.setattr(
        translate_refresh,
        "batch_llm_call",
        lambda **kwargs: [{"id": "s1", "updated_target": "Коноха вход"}],
    )
    monkeypatch.setattr(
        translate_refresh,
        "run_qa_hard_gate",
        lambda *args, **kwargs: {
            "passed": False,
            "report_path": str(tmp_path / "qa_report.json"),
            "error_total": 1,
            "warning_total": 0,
            "failed_string_ids": ["s1"],
        },
    )

    exit_code = translate_refresh.main(
        [
            "--tasks-in",
            str(tasks_in),
            "--translated",
            str(translated_csv),
            "--glossary",
            str(glossary),
            "--style",
            str(style),
            "--tasks-out",
            str(tasks_out),
            "--review-queue",
            str(review_queue),
            "--manifest",
            str(manifest),
            "--out-csv",
            str(out_csv),
        ]
    )

    assert exit_code == 1
    assert not out_csv.exists()
    staged_candidate = out_csv.with_name("final.candidate.csv")
    assert staged_candidate.exists()

    manifest_payload = json.loads(manifest.read_text(encoding="utf-8"))
    assert manifest_payload["artifacts"]["candidate_output_csv"] == str(staged_candidate)
    assert manifest_payload["artifacts"]["failure_breakdown_json"].endswith("incremental_failure_breakdown.json")
    assert manifest_payload["overall_status"] == "blocked"
    assert manifest_payload["gate_summary"]["status"] == "blocked"
    assert manifest_payload["gate_summary"]["failed_gates"] == ["qa_hard"]
    assert manifest_payload["task_outcomes"]["counts_by_final_status"]["blocked"] == 1
    review_rows = _read_review_rows(review_queue)
    assert review_rows[0]["review_source"] == "post_gate_blocked"
    assert review_rows[0]["execution_status"] == "updated"
    assert review_rows[0]["final_status"] == "blocked"
    assert review_rows[0]["status_reason"] == "qa_hard_failed"


def test_executor_handles_mixed_locales_with_locale_specific_target_columns(tmp_path, monkeypatch):
    translated_csv = tmp_path / "translated.csv"
    glossary = tmp_path / "compiled.yaml"
    style = tmp_path / "style.md"
    tasks_in = tmp_path / "tasks.jsonl"
    tasks_out = tmp_path / "tasks_out.jsonl"
    review_queue = tmp_path / "review.csv"
    manifest = tmp_path / "manifest.json"
    out_csv = tmp_path / "refreshed.csv"

    _write_csv(
        translated_csv,
        [
            {
                "string_id": "ru1",
                "source_zh": "木叶入口",
                "tokenized_zh": "木叶入口",
                "target_text": "Старая Коноха вход",
                "target_ru": "Старая Коноха вход",
                "target_locale": "ru-RU",
            },
            {
                "string_id": "en1",
                "source_zh": "忍者任务",
                "tokenized_zh": "忍者任务",
                "target_text": "Old mission",
                "target_en": "Old mission",
                "target_locale": "en-US",
            },
        ],
    )
    _write_glossary(glossary)
    _write_style(style)
    _write_jsonl(
        tasks_in,
        [
            _sample_task("refresh:ru1", "ru1", "refresh", "Старая Коноха вход", "木叶入口", target_locale="ru-RU"),
            _sample_task("retranslate:en1", "en1", "retranslate", "Old mission", "忍者任务", target_locale="en-US"),
        ],
    )

    def fake_batch_llm_call(*, step, rows, **_kwargs):
        if step == "translate_refresh_incremental":
            assert [row["id"] for row in rows] == ["ru1"]
            return [{"id": "ru1", "updated_target": "Коноха вход"}]
        if step == "translate_refresh_retranslate":
            assert [row["id"] for row in rows] == ["en1"]
            return [{"id": "en1", "target_en": "Ninja mission"}]
        raise AssertionError(f"unexpected step: {step}")

    monkeypatch.setattr(translate_refresh, "batch_llm_call", fake_batch_llm_call)
    monkeypatch.setattr(
        translate_refresh,
        "run_qa_hard_gate",
        lambda *args, **kwargs: {
            "passed": True,
            "report_path": str(tmp_path / "qa_report.json"),
            "error_total": 0,
            "warning_total": 0,
            "failed_string_ids": [],
        },
    )

    exit_code = translate_refresh.main(
        [
            "--tasks-in",
            str(tasks_in),
            "--translated",
            str(translated_csv),
            "--glossary",
            str(glossary),
            "--style",
            str(style),
            "--tasks-out",
            str(tasks_out),
            "--review-queue",
            str(review_queue),
            "--manifest",
            str(manifest),
            "--out-csv",
            str(out_csv),
        ]
    )

    assert exit_code == 0
    output_rows = {
        row["string_id"]: row
        for row in csv.DictReader(out_csv.open("r", encoding="utf-8-sig", newline=""))
    }
    assert output_rows["ru1"]["target_ru"] == "Коноха вход"
    assert output_rows["en1"]["target_en"] == "Ninja mission"
    assert output_rows["en1"]["target_text"] == "Ninja mission"


def test_executor_emits_unified_status_contract_for_success_manual_failure_and_blocked(tmp_path, monkeypatch):
    translated_csv = tmp_path / "translated.csv"
    glossary = tmp_path / "compiled.yaml"
    style = tmp_path / "style.md"
    tasks_in = tmp_path / "tasks.jsonl"
    tasks_out = tmp_path / "tasks_out.jsonl"
    review_queue = tmp_path / "review.csv"
    manifest = tmp_path / "manifest.json"
    out_csv = tmp_path / "final.csv"

    _write_csv(translated_csv, _sample_translated_rows())
    _write_glossary(glossary)
    _write_style(style)
    _write_jsonl(
        tasks_in,
        [
            _sample_task("refresh:s1", "s1", "refresh", "Старая Коноха вход", "木叶入口"),
            _sample_task("manual_review:s2", "s2", "manual_review", "Нужна ручная проверка", "人工复核文案"),
            _sample_task("refresh:s3", "s3", "refresh", "Без изменений", "未受影响"),
            _sample_task("refresh:s4", "s4", "refresh", "Старый блок", "任务阻断"),
        ],
    )

    def fake_batch_llm_call(*, step, rows, **_kwargs):
        assert step == "translate_refresh_incremental"
        assert [row["id"] for row in rows] == ["s1", "s3", "s4"]
        return [
            {"id": "s1", "updated_target": "Коноха вход"},
            {"id": "s4", "updated_target": "Новый блок"},
        ]

    monkeypatch.setattr(translate_refresh, "batch_llm_call", fake_batch_llm_call)
    monkeypatch.setattr(
        translate_refresh,
        "run_qa_hard_gate",
        lambda *args, **kwargs: {
            "passed": False,
            "report_path": str(tmp_path / "qa_report.json"),
            "error_total": 1,
            "warning_total": 0,
            "failed_string_ids": ["s4"],
        },
    )

    exit_code = translate_refresh.main(
        [
            "--tasks-in",
            str(tasks_in),
            "--translated",
            str(translated_csv),
            "--glossary",
            str(glossary),
            "--style",
            str(style),
            "--tasks-out",
            str(tasks_out),
            "--review-queue",
            str(review_queue),
            "--manifest",
            str(manifest),
            "--out-csv",
            str(out_csv),
        ]
    )

    assert exit_code == 1

    manifest_payload = json.loads(manifest.read_text(encoding="utf-8"))
    assert manifest_payload["overall_status"] == "blocked"
    assert manifest_payload["gate_summary"]["status"] == "blocked"
    assert manifest_payload["gate_summary"]["failed_gates"] == ["qa_hard"]
    assert manifest_payload["review_handoff"]["by_source"] == {
        "initial_manual_review": 1,
        "execution_failure": 1,
        "post_gate_blocked": 1,
    }
    assert manifest_payload["task_outcomes"]["counts_by_execution_status"] == {
        "updated": 2,
        "review_handoff": 1,
        "failed": 1,
    }
    assert manifest_payload["task_outcomes"]["counts_by_final_status"] == {
        "updated": 1,
        "review_handoff": 2,
        "blocked": 1,
    }

    outcome_by_id = {
        item["task_id"]: item
        for item in manifest_payload["task_outcomes"]["items"]
    }
    assert outcome_by_id["refresh:s1"] == {
        "task_id": "refresh:s1",
        "string_id": "s1",
        "task_type": "refresh",
        "execution_status": "updated",
        "final_status": "updated",
        "status_reason": "",
        "review_source": "",
    }
    assert outcome_by_id["manual_review:s2"]["execution_status"] == "review_handoff"
    assert outcome_by_id["manual_review:s2"]["final_status"] == "review_handoff"
    assert outcome_by_id["manual_review:s2"]["review_source"] == "initial_manual_review"
    assert outcome_by_id["refresh:s3"]["execution_status"] == "failed"
    assert outcome_by_id["refresh:s3"]["final_status"] == "review_handoff"
    assert outcome_by_id["refresh:s3"]["status_reason"] == "missing_llm_result"
    assert outcome_by_id["refresh:s3"]["review_source"] == "execution_failure"
    assert outcome_by_id["refresh:s4"]["execution_status"] == "updated"
    assert outcome_by_id["refresh:s4"]["final_status"] == "blocked"
    assert outcome_by_id["refresh:s4"]["status_reason"] == "qa_hard_failed"
    assert outcome_by_id["refresh:s4"]["review_source"] == "post_gate_blocked"

    review_rows = _read_review_rows(review_queue)
    review_by_id = {(row["task_id"], row["review_source"]): row for row in review_rows}
    assert review_by_id[("manual_review:s2", "initial_manual_review")]["final_status"] == "review_handoff"
    assert review_by_id[("refresh:s3", "execution_failure")]["execution_status"] == "failed"
    assert review_by_id[("refresh:s3", "execution_failure")]["final_status"] == "review_handoff"
    assert review_by_id[("refresh:s4", "post_gate_blocked")]["execution_status"] == "updated"
    assert review_by_id[("refresh:s4", "post_gate_blocked")]["final_status"] == "blocked"
    assert review_by_id[("refresh:s4", "post_gate_blocked")]["status_reason"] == "qa_hard_failed"

    task_rows = translate_refresh.read_jsonl(str(tasks_out))
    task_by_id = {row["task_id"]: row for row in task_rows}
    assert task_by_id["refresh:s1"]["execution_status"] == "updated"
    assert task_by_id["refresh:s1"]["final_status"] == "updated"
    assert task_by_id["manual_review:s2"]["execution_status"] == "review_handoff"
    assert task_by_id["manual_review:s2"]["final_status"] == "review_handoff"
    assert task_by_id["refresh:s3"]["execution_status"] == "failed"
    assert task_by_id["refresh:s3"]["final_status"] == "review_handoff"
    assert task_by_id["refresh:s3"]["status_reason"] == "missing_llm_result"
    assert task_by_id["refresh:s4"]["execution_status"] == "updated"
    assert task_by_id["refresh:s4"]["final_status"] == "blocked"
    assert task_by_id["refresh:s4"]["status_reason"] == "qa_hard_failed"


def test_executor_keeps_staged_candidate_and_returns_failure_when_execution_fails_without_gate_failure(tmp_path, monkeypatch):
    translated_csv = tmp_path / "translated.csv"
    glossary = tmp_path / "compiled.yaml"
    style = tmp_path / "style.md"
    tasks_in = tmp_path / "tasks.jsonl"
    tasks_out = tmp_path / "tasks_out.jsonl"
    review_queue = tmp_path / "review.csv"
    manifest = tmp_path / "manifest.json"
    out_csv = tmp_path / "final.csv"

    _write_csv(translated_csv, _sample_translated_rows()[:3])
    _write_glossary(glossary)
    _write_style(style)
    _write_jsonl(
        tasks_in,
        [
            _sample_task("refresh:s1", "s1", "refresh", "Старая Коноха вход", "木叶入口"),
            _sample_task("refresh:s3", "s3", "refresh", "Без изменений", "未受影响"),
        ],
    )

    def fake_batch_llm_call(*, step, rows, **_kwargs):
        assert step == "translate_refresh_incremental"
        assert [row["id"] for row in rows] == ["s1", "s3"]
        return [{"id": "s1", "updated_target": "Коноха вход"}]

    monkeypatch.setattr(translate_refresh, "batch_llm_call", fake_batch_llm_call)
    monkeypatch.setattr(
        translate_refresh,
        "run_qa_hard_gate",
        lambda *args, **kwargs: {
            "passed": True,
            "report_path": str(tmp_path / "qa_report.json"),
            "error_total": 0,
            "warning_total": 0,
            "failed_string_ids": [],
        },
    )

    exit_code = translate_refresh.main(
        [
            "--tasks-in",
            str(tasks_in),
            "--translated",
            str(translated_csv),
            "--glossary",
            str(glossary),
            "--style",
            str(style),
            "--tasks-out",
            str(tasks_out),
            "--review-queue",
            str(review_queue),
            "--manifest",
            str(manifest),
            "--out-csv",
            str(out_csv),
        ]
    )

    assert exit_code == 1
    assert not out_csv.exists()
    staged_candidate = Path(str(out_csv).replace(".csv", ".candidate.csv"))
    assert staged_candidate.exists()

    manifest_payload = json.loads(manifest.read_text(encoding="utf-8"))
    assert manifest_payload["overall_status"] == "failed"
    assert manifest_payload["post_gates"]["qa_hard"]["passed"] is True
    assert manifest_payload["artifacts"]["candidate_output_csv"] == str(staged_candidate)
    assert manifest_payload["execution"]["failed"] == 1
    assert manifest_payload["review_handoff"]["by_source"] == {"execution_failure": 1}

    review_rows = _read_review_rows(review_queue)
    assert len(review_rows) == 1
    assert review_rows[0]["task_id"] == "refresh:s3"
    assert review_rows[0]["review_source"] == "execution_failure"
    assert review_rows[0]["execution_status"] == "failed"
    assert review_rows[0]["final_status"] == "review_handoff"

    task_rows = translate_refresh.read_jsonl(str(tasks_out))
    task_by_id = {row["task_id"]: row for row in task_rows}
    assert task_by_id["refresh:s1"]["execution_status"] == "updated"
    assert task_by_id["refresh:s1"]["final_status"] == "updated"
    assert task_by_id["refresh:s3"]["execution_status"] == "failed"
    assert task_by_id["refresh:s3"]["final_status"] == "review_handoff"
    assert task_by_id["refresh:s3"]["status_reason"] == "missing_llm_result"
