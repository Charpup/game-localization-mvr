import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import translate_refresh


def _write_csv(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
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
    path.write_text("# style\n- keep UI concise\n", encoding="utf-8")


def test_milestone_e_delta_to_task_execution_flow(tmp_path, monkeypatch):
    translated_csv = tmp_path / "translated.csv"
    delta_rows = tmp_path / "delta_rows.jsonl"
    glossary = tmp_path / "compiled.yaml"
    style = tmp_path / "style.md"
    tasks_out = tmp_path / "tasks.jsonl"
    review_queue = tmp_path / "review.csv"
    manifest = tmp_path / "manifest.json"
    out_csv = tmp_path / "refreshed.csv"

    _write_csv(
        translated_csv,
        [
            {
                "string_id": "s1",
                "source_zh": "木叶入口",
                "tokenized_zh": "木叶入口",
                "target_text": "Старая Коноха вход",
                "target_locale": "ru-RU",
                "module_tag": "ui_button",
            },
            {
                "string_id": "s2",
                "source_zh": "忍者任务",
                "tokenized_zh": "忍者任务",
                "target_text": "Старое задание",
                "target_locale": "ru-RU",
                "module_tag": "general",
            },
            {
                "string_id": "s3",
                "source_zh": "付费入口",
                "tokenized_zh": "付费入口",
                "target_text": "Оплата",
                "target_locale": "ru-RU",
                "module_tag": "payment",
            },
        ],
    )
    _write_jsonl(
        delta_rows,
        [
            {
                "string_id": "s1",
                "source_zh": "木叶入口",
                "current_target": "Старая Коноха вход",
                "target_locale": "ru-RU",
                "content_class": "general",
                "risk_level": "low",
                "delta_types": ["term_changed"],
                "reason_codes": ["GLOSSARY_TERM_CHANGED"],
                "reason_text": "glossary term updated",
                "rule_refs": ["glossary"],
                "placeholder_locked": False,
                "manual_review_required": False,
                "manual_review_reason": "",
                "recommended_action": "auto_refresh",
            },
            {
                "string_id": "s2",
                "source_zh": "忍者任务",
                "current_target": "Старое задание",
                "target_locale": "ru-RU",
                "content_class": "general",
                "risk_level": "medium",
                "delta_types": ["style_contract_changed"],
                "reason_codes": ["STYLE_CONTRACT_CHANGED"],
                "reason_text": "style contract changed",
                "rule_refs": ["style_profile"],
                "placeholder_locked": False,
                "manual_review_required": False,
                "manual_review_reason": "",
                "recommended_action": "retranslate",
            },
            {
                "string_id": "s3",
                "source_zh": "付费入口",
                "current_target": "Оплата",
                "target_locale": "ru-RU",
                "content_class": "payment",
                "risk_level": "high",
                "delta_types": ["banned_term_changed"],
                "reason_codes": ["STYLE_BANNED_TERM_CHANGED"],
                "reason_text": "payment row requires human review",
                "rule_refs": ["style_profile"],
                "placeholder_locked": False,
                "manual_review_required": True,
                "manual_review_reason": "hard gate reason(s): banned_term_changed, high_risk_content_class",
                "recommended_action": "manual_review",
            },
        ],
    )
    _write_glossary(glossary)
    _write_style(style)

    def fake_batch_llm_call(*, step, rows, **_kwargs):
        if step == "translate_refresh_incremental":
            return [{"id": "s1", "updated_target": "Коноха вход"}]
        if step == "translate_refresh_retranslate":
            return [{"id": "s2", "target_ru": "Задание ниндзя"}]
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
            "--out-csv",
            str(out_csv),
        ]
    )

    assert exit_code == 0

    task_rows = translate_refresh.read_jsonl(str(tasks_out))
    assert [task["task_type"] for task in task_rows] == ["refresh", "retranslate", "manual_review"]

    output_rows = {
        row["string_id"]: row
        for row in csv.DictReader(out_csv.open("r", encoding="utf-8-sig", newline=""))
    }
    assert output_rows["s1"]["target_text"] == "Коноха вход"
    assert output_rows["s2"]["target_text"] == "Задание ниндзя"
    assert output_rows["s3"]["target_text"] == "Оплата"
    assert output_rows["s3"]["refresh_status"] == "review_handoff"

    review_rows = list(csv.DictReader(review_queue.open("r", encoding="utf-8-sig", newline="")))
    assert [row["string_id"] for row in review_rows] == ["s3"]
    assert review_rows[0]["task_type"] == "manual_review"

    manifest_payload = json.loads(manifest.read_text(encoding="utf-8"))
    assert manifest_payload["execution"]["updated"] == 2
    assert manifest_payload["execution"]["review_handoff"] == 1
    assert manifest_payload["post_gates"]["row_count_integrity"]["passed"] is True
    assert manifest_payload["post_gates"]["placeholder_signature_integrity"]["passed"] is True
