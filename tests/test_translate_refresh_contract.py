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

    review_rows = list(csv.DictReader(review_queue.open("r", encoding="utf-8-sig", newline="")))
    assert len(review_rows) == 1
    assert review_rows[0]["string_id"] == "s2"
    assert review_rows[0]["task_type"] == "manual_review"

    manifest_payload = json.loads(manifest.read_text(encoding="utf-8"))
    assert manifest_payload["mode"] == "generate_only"
    assert manifest_payload["review_handoff"]["pending_count"] == 1


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

    review_rows = list(csv.DictReader(review_queue.open("r", encoding="utf-8-sig", newline="")))
    assert [row["string_id"] for row in review_rows] == ["s2"]

    manifest_payload = json.loads(manifest.read_text(encoding="utf-8"))
    assert manifest_payload["post_gates"]["row_count_integrity"]["passed"] is True
    assert manifest_payload["execution"]["skipped_direct_write"] == 1


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
