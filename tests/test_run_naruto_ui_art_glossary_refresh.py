import csv
import json
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import run_naruto_ui_art_glossary_refresh as workflow


def _write_csv(path: Path, rows: list[dict], fieldnames: list[str] | None = None) -> None:
    if fieldnames is None:
        fieldnames = []
        for row in rows:
            for key in row.keys():
                if key not in fieldnames:
                    fieldnames.append(key)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames or ["string_id"])
        writer.writeheader()
        writer.writerows(rows)


def _write_yaml(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, allow_unicode=True, sort_keys=False), encoding="utf-8")


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def test_orchestrator_generate_only_stop_builds_artifacts_without_mutating_base(tmp_path, monkeypatch):
    repo_root = tmp_path
    base_slice_dir = repo_root / "slice"
    out_dir = base_slice_dir / "run01"
    workbook = repo_root / "reviewed.xlsx"
    workbook.touch()
    env_ps1 = repo_root / ".env.ps1"
    env_ps1.write_text(
        "\n".join(
            [
                "$env:LLM_BASE_URL='https://example.test/v1'",
                "$env:LLM_API_KEY_FILE=(Join-Path $PSScriptRoot '.llm_credentials')",
            ]
        ),
        encoding="utf-8",
    )
    (repo_root / ".llm_credentials").write_text("api key: secret", encoding="utf-8")

    base_full_csv = base_slice_dir / "ui_art_delivery_repaired_v2.csv"
    _write_csv(
        base_full_csv,
        [
            {
                "string_id": "1",
                "source_zh": "木叶入口",
                "target_text": "Старая Коноха вход",
                "target_ru": "Старая Коноха вход",
                "target_locale": "ru-RU",
                "max_len_review_limit": "20",
                "module_tag": "general",
            },
            {
                "string_id": "2",
                "source_zh": "普通文本",
                "target_text": "Обычный текст",
                "target_ru": "Обычный текст",
                "target_locale": "ru-RU",
                "max_len_review_limit": "30",
                "module_tag": "general",
            },
        ],
    )
    base_snapshot = base_full_csv.read_text(encoding="utf-8-sig")

    patch_glossary = base_slice_dir / "ui_art_residual_v2_patch_glossary.yaml"
    _write_yaml(patch_glossary, {"entries": [{"term_zh": "旧词", "term_ru": "Старое", "status": "approved"}]})
    old_compiled = base_slice_dir / "glossary_ui_art_residual_v2_compiled.yaml"
    _write_yaml(
        old_compiled,
        {
            "meta": {"type": "compiled"},
            "entries": [
                {"term_zh": "旧词", "term_ru": "Старое"},
                {"term_zh": "兼容词", "term_ru": "Совместимое", "scope": "ip"},
            ],
        },
    )
    approved = repo_root / "glossary" / "approved.yaml"
    _write_yaml(approved, {"entries": [{"term_zh": "木叶", "term_ru": "Коноха", "status": "approved"}]})
    style = repo_root / "workflow" / "style_guide.md"
    style.parent.mkdir(parents=True, exist_ok=True)
    style.write_text("# style\n", encoding="utf-8")
    style_profile = repo_root / "data" / "style_profile.yaml"
    _write_yaml(style_profile, {"project": {"source_language": "zh-CN", "target_language": "ru-RU"}})
    registry = repo_root / "workflow" / "lifecycle_registry.yaml"
    _write_yaml(
        registry,
        {
            "version": "1.0",
            "entries": [
                {
                    "asset_id": "glossary-compiled-naruto-ui-art-refresh-ru",
                    "asset_kind": "glossary",
                    "asset_path": "glossary/compiled_naruto_ui_art_workbook_refresh.yaml",
                    "target_locale": "ru-RU",
                    "status": "approved",
                }
            ],
        },
    )
    merged_approved = repo_root / "glossary" / "zhCN_ruRU" / "project_naruto_ui_art_workbook_refresh_approved.yaml"
    compiled_glossary = repo_root / "glossary" / "compiled_naruto_ui_art_workbook_refresh.yaml"

    def fake_run_checked(command, *, env, cwd=workflow.REPO_ROOT):
        target = Path(command[1]).name
        if target == "llm_ping.py":
            return None
        if target == "build_reviewed_workbook_glossary.py":
            output_dir = Path(command[command.index("--out-dir") + 1])
            _write_yaml(
                output_dir / "full_resolved.yaml",
                {"entries": [{"term_zh": "木叶入口", "term_ru": "Коноха вход", "status": "approved"}]},
            )
            _write_yaml(
                output_dir / "ui_art_focus_resolved.yaml",
                {"entries": [{"term_zh": "木叶入口", "term_ru": "Коноха вход", "status": "approved"}]},
            )
            _write_json(output_dir / "stats.json", {"focus_resolved_count": 1, "compact_conflicts": 0})
            _write_json(output_dir / "conflicts.json", {"conflicts": []})
            _write_csv(output_dir / "conflicts.csv", [], ["source_zh", "target_ru"])
            _write_csv(output_dir / "manual_compact_conflicts.csv", [], ["source_zh", "target_ru"])
            return None
        if target == "glossary_compile.py":
            _write_yaml(compiled_glossary, {"meta": {"type": "compiled"}, "entries": [{"term_zh": "木叶入口", "term_ru": "Коноха вход"}]})
            _write_json(compiled_glossary.with_suffix(".lock.json"), {"hash": "sha256:test"})
            return None
        if target == "glossary_delta.py":
            report_path = Path(command[command.index("--out_impact") + 1])
            rows_path = Path(command[command.index("--out_rows") + 1])
            _write_json(report_path, {"impacted_rows_total": 1, "impact_set": ["1"], "row_impacts_path": str(rows_path)})
            rows_path.write_text(
                json.dumps(
                    {
                        "string_id": "1",
                        "source_zh": "木叶入口",
                        "current_target": "Старая Коноха вход",
                        "target_locale": "ru-RU",
                        "content_class": "general",
                        "risk_level": "low",
                        "delta_types": ["term_changed"],
                        "reason_codes": ["GLOSSARY_TERM_CHANGED"],
                        "reason_text": "changed",
                        "rule_refs": ["glossary"],
                        "placeholder_locked": False,
                        "manual_review_required": False,
                        "manual_review_reason": "",
                        "recommended_action": "auto_refresh",
                    },
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )
            return None
        if target == "translate_refresh.py" and "--generate-only" in command:
            tasks_out = Path(command[command.index("--tasks-out") + 1])
            review_queue = Path(command[command.index("--review-queue") + 1])
            manifest = Path(command[command.index("--manifest") + 1])
            tasks_out.parent.mkdir(parents=True, exist_ok=True)
            tasks_out.write_text(
                json.dumps(
                    {
                        "task_id": "refresh:1",
                        "string_id": "1",
                        "task_type": "refresh",
                        "target_locale": "ru-RU",
                        "reason_codes": ["GLOSSARY_TERM_CHANGED"],
                        "trigger_change_ids": ["term_changed"],
                        "depends_on_rules": ["glossary"],
                        "source_artifacts": {},
                        "target_constraints": {},
                        "placeholder_signature": {},
                        "current_target": "Старая Коноха вход",
                        "expected_change_scope": "term_only",
                        "human_review_required": False,
                        "review_owner": "automation",
                        "review_status": "not_required",
                        "execution_status": "pending",
                        "final_status": "pending",
                        "status_reason": "awaiting_execution",
                    },
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )
            _write_csv(review_queue, [], ["task_id", "string_id", "task_type"])
            manifest.write_text(
                json.dumps(
                    {
                        "review_handoff": {"pending_count": 0, "items": []},
                        "execution": {"blocked": 0, "review_handoff": 0},
                        "task_outcomes": {"counts_by_final_status": {"pending": 1}},
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            return None
        raise AssertionError(f"unexpected command: {command}")

    monkeypatch.setattr(workflow, "REPO_ROOT", repo_root)
    monkeypatch.setattr(workflow, "DEFAULT_BASE_SLICE_DIR", base_slice_dir)
    monkeypatch.setattr(workflow, "run_checked", fake_run_checked)

    exit_code = workflow.main(
        [
            "--python",
            sys.executable,
            "--env-ps1",
            str(env_ps1),
            "--workbook",
            str(workbook),
            "--base-slice-dir",
            str(base_slice_dir),
            "--out-dir",
            str(out_dir),
            "--merged-approved",
            str(merged_approved),
            "--compiled-glossary",
            str(compiled_glossary),
            "--style",
            str(style),
            "--style-profile",
            str(style_profile),
            "--lifecycle-registry",
            str(registry),
            "--stop-after-generate-only",
        ]
    )

    assert exit_code == 0
    assert merged_approved.exists()
    assert compiled_glossary.exists()
    assert (out_dir / "workbook_glossary" / "ui_art_focus_resolved.yaml").exists()
    assert (out_dir / "glossary_delta_report.json").exists()
    assert (out_dir / "translate_refresh_generate_manifest.json").exists()
    assert (out_dir / "run_manifest.json").exists()
    merged_payload = yaml.safe_load(merged_approved.read_text(encoding="utf-8")) or {}
    merged_terms = {entry["term_zh"]: entry["term_ru"] for entry in merged_payload.get("entries", [])}
    assert merged_terms["兼容词"] == "Совместимое"
    assert merged_terms["木叶入口"] == "Коноха вход"
    assert base_full_csv.read_text(encoding="utf-8-sig") == base_snapshot


def test_filter_execute_tasks_by_focus_glossary_keeps_only_exact_focus_hits(tmp_path):
    tasks_path = tmp_path / "tasks.jsonl"
    focus_path = tmp_path / "focus.yaml"
    out_path = tmp_path / "filtered.jsonl"

    tasks = [
        {"task_id": "refresh:1", "string_id": "1", "source_zh": "商店"},
        {"task_id": "refresh:2", "string_id": "2", "source_zh": "商店 礼包"},
        {"task_id": "refresh:3", "string_id": "3", "source_zh": " 680 金币 "},
    ]
    tasks_path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in tasks), encoding="utf-8")
    _write_yaml(
        focus_path,
        {
            "entries": [
                {"term_zh": "商店", "term_ru": "Магазин"},
                {"term_zh": "680金币", "term_ru": "680 золота"},
            ]
        },
    )

    stats = workflow.filter_execute_tasks_by_focus_glossary(
        tasks_path=tasks_path,
        focus_glossary_path=focus_path,
        out_path=out_path,
    )

    kept = [json.loads(line) for line in out_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert stats["filtered_task_count"] == 2
    assert [row["string_id"] for row in kept] == ["1", "3"]


def test_build_merged_approved_preserves_old_compiled_coverage_and_allows_runtime_override(tmp_path):
    base_glossary = tmp_path / "glossary" / "approved.yaml"
    patch_glossary = tmp_path / "slice" / "ui_art_residual_v2_patch_glossary.yaml"
    compat_glossary = tmp_path / "slice" / "glossary_ui_art_residual_v2_compiled.yaml"
    runtime_glossary = tmp_path / "run" / "ui_art_focus_resolved.yaml"
    out_path = tmp_path / "glossary" / "merged.yaml"

    _write_yaml(base_glossary, {"entries": [{"term_zh": "商店", "term_ru": "Шоп", "status": "approved"}]})
    _write_yaml(patch_glossary, {"entries": [{"term_zh": "商店", "term_ru": "Магазин", "status": "approved"}]})
    _write_yaml(
        compat_glossary,
        {
            "meta": {"type": "compiled"},
            "entries": [
                {"term_zh": "商店", "term_ru": "Шоп", "scope": "base"},
                {"term_zh": "新品", "term_ru": "Нов.", "scope": "batch_override"},
            ],
        },
    )
    _write_yaml(runtime_glossary, {"entries": [{"term_zh": "商店", "term_ru": "Лавка", "status": "approved"}]})

    payload = workflow.build_merged_approved(
        base_glossary=base_glossary,
        patch_glossary=patch_glossary,
        compat_glossary=compat_glossary,
        runtime_glossary=runtime_glossary,
        out_path=out_path,
    )

    entries = payload["entries"]
    by_term: dict[str, list[dict]] = {}
    for entry in entries:
        by_term.setdefault(entry["term_zh"], []).append(entry)

    assert any(item["term_ru"] == "Нов." and item["scope"] == "ip" for item in by_term["新品"])
    assert any(item["term_ru"] == "Лавка" and item["scope"] == "project" for item in by_term["商店"])
    assert payload["meta"]["compat_seed_entry_count"] == 1
