from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

import scripts.operator_ui_tasks as task_models


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def _write_task_run_fixture(
    base_dir: Path,
    run_id: str,
    *,
    manifest_status: str,
    verify_status: str,
    with_review_ticket: bool,
    with_visible_bundle: bool = True,
    target_lang: str = "en-US",
) -> None:
    run_dir = base_dir / "data" / "operator_ui_runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    verify_log = run_dir / "99_smoke_verify.log"
    verify_log.write_text("returncode: 0\n", encoding="utf-8")
    verify_report = run_dir / f"smoke_verify_{run_id}.json"
    issue_report = run_dir / "smoke_issues.json"
    _write_json(
        verify_report,
        {"run_id": run_id, "status": verify_status, "overall": verify_status, "issue_count": 0, "qa_rows": []},
    )
    _write_json(issue_report, {"run_id": run_id, "issues": []})
    artifacts = {
        "run_manifest": str(run_dir / "run_manifest.json"),
        "smoke_verify_log": str(verify_log),
        "smoke_verify_report": str(verify_report),
        "smoke_issues_report": str(issue_report),
    }
    if with_visible_bundle:
        operator_summary = run_dir / "operator_summary.md"
        operator_summary.write_text("# Delivery summary\nAll checks passed.\n", encoding="utf-8")
        artifacts["operator_summary_md"] = str(operator_summary)
    if with_review_ticket:
        _write_jsonl(
            run_dir / "smoke_review_tickets.jsonl",
            [
                {
                    "ticket_id": f"ticket:manual_review:{run_id}:manual_review",
                    "task_id": f"manual_review:{run_id}",
                    "string_id": run_id,
                    "target_locale": target_lang,
                    "ticket_type": "manual_review",
                    "priority": "P1",
                    "review_owner": "human-linguist",
                    "review_status": "pending",
                    "review_source": "manual_review",
                    "queue_reason": "needs manual review",
                    "current_target": "Hello",
                    "reason_codes": ["STYLE_CONTRACT_CHANGED"],
                    "content_class": "general",
                    "risk_level": "high",
                    "created_at": "2026-04-06T08:00:00+00:00",
                    "source_artifacts": {"review_queue": str(run_dir / "smoke_review_queue.csv")},
                }
            ],
        )
        _write_jsonl(run_dir / "smoke_review_feedback_log.jsonl", [])
        _write_json(
            run_dir / "smoke_language_governance_kpi.json",
            {
                "generated_at": "2026-04-06T08:10:00+00:00",
                "scope": {"run_id": run_id},
                "runtime_summary": {"overall_status": "running", "total_tasks": 1, "updated_count": 1, "review_handoff_count": 1},
                "review_summary": {"total_review_tickets": 1, "pending_review_tickets": 1, "manual_intervention_rate": 1.0},
                "lifecycle_summary": {"registry_path": "workflow/lifecycle_registry.yaml"},
                "metrics_sources": {},
            },
        )
        artifacts["smoke_review_tickets_jsonl"] = str(run_dir / "smoke_review_tickets.jsonl")
        artifacts["smoke_feedback_log_jsonl"] = str(run_dir / "smoke_review_feedback_log.jsonl")
        artifacts["smoke_governance_kpi_json"] = str(run_dir / "smoke_language_governance_kpi.json")

    _write_json(
        run_dir / "run_manifest.json",
        {
            "run_id": run_id,
            "run_dir": str(run_dir),
            "status": manifest_status,
            "overall_status": manifest_status,
            "verify_mode": "full",
            "target_lang": target_lang,
            "started_at": "2026-04-06T08:00:00+00:00",
            "issue_file": str(issue_report),
            "stages": [{"name": "Smoke Verify", "status": manifest_status, "required": True, "files": [{"path": str(verify_log), "required": True}]}],
            "artifacts": artifacts,
        },
    )


def test_human_task_views_surface_user_action_review_states_and_bundle_groups(tmp_path):
    _write_task_run_fixture(tmp_path, "ready_run", manifest_status="pass", verify_status="PASS", with_review_ticket=False)
    _write_task_run_fixture(tmp_path, "review_run", manifest_status="warn", verify_status="WARN", with_review_ticket=True)

    task_models.create_human_task_record(
        tmp_path,
        task_id=task_models.task_id_for_run("ready_run"),
        title="Ready bundle",
        source_input="fixtures/input.csv",
        source_input_label="launch_copy.csv",
        target_locale="en-US",
        verify_mode="full",
        linked_run_id="ready_run",
        created_at="2026-04-06T08:00:00+00:00",
    )
    task_models.create_human_task_record(
        tmp_path,
        task_id=task_models.task_id_for_run("review_run"),
        title="Needs review",
        source_input="fixtures/review.csv",
        target_locale="en-US",
        verify_mode="full",
        linked_run_id="review_run",
        created_at="2026-04-06T08:05:00+00:00",
    )

    tasks = {task.task_id: task for task in task_models.load_human_task_summaries(tmp_path, limit=10)}
    ready_task = tasks[task_models.task_id_for_run("ready_run")]
    review_task = tasks[task_models.task_id_for_run("review_run")]
    overview = task_models.load_human_task_overview(tmp_path)
    deliveries = task_models.load_human_task_deliveries(tmp_path, task_models.task_id_for_run("ready_run"))

    assert ready_task.status == "needs_user_action"
    assert ready_task.bucket == "needs_your_action"
    assert ready_task.next_primary_action == "approve_delivery"
    assert review_task.status == "needs_operator_review"
    assert review_task.bucket == "waiting_on_ops"
    assert overview.counts_by_status["needs_user_action"] == 1
    assert overview.counts_by_status["needs_operator_review"] == 1
    assert overview.counts_by_bucket["needs_your_action"] == 1
    assert overview.counts_by_bucket["waiting_on_ops"] == 1
    assert deliveries["bundle_summary"]["groups"]
    assert any(group["group_id"] == "primary_output" for group in deliveries["bundle_summary"]["groups"])
    assert any(item["label"] == "Delivery summary" for item in deliveries["deliveries"])


def test_request_changes_links_new_run_and_records_history(tmp_path):
    _write_task_run_fixture(tmp_path, "ready_run", manifest_status="pass", verify_status="PASS", with_review_ticket=False)
    task_models.create_human_task_record(
        tmp_path,
        task_id="task_custom_record",
        title="April launch copy",
        source_input="fixtures/input.csv",
        source_input_label="April_launch.csv",
        target_locale="ja-JP",
        verify_mode="preflight",
        linked_run_id="ready_run",
        created_at="2026-04-06T08:30:00+00:00",
    )

    task_models.request_human_task_changes(
        tmp_path,
        "task_custom_record",
        note="Please tighten the product names and rerun.",
        new_run_id="pending_run_01",
        at="2026-04-06T09:00:00+00:00",
    )

    detail = task_models.load_human_task_detail(
        tmp_path,
        "task_custom_record",
        pending_runs=[
            {
                "run_id": "pending_run_01",
                "run_dir": str(tmp_path / "data" / "operator_ui_runs" / "pending_run_01"),
                "status": "running",
                "pid": 3456,
                "started_at": "2026-04-06T09:00:00+00:00",
                "command": [".venv\\Scripts\\python.exe", "scripts/run_smoke_pipeline.py"],
                "input_csv": "fixtures/pending.csv",
                "target_lang": "ja-JP",
                "verify_mode": "preflight",
            }
        ],
    )

    assert detail.latest_run_id == "pending_run_01"
    assert detail.status == "running"
    assert detail.latest_feedback_note == "Please tighten the product names and rerun."
    assert detail.metrics["request_changes_at"] == "2026-04-06T09:00:00+00:00"
    assert any(event["type"] == "changes_requested" for event in detail.history)
    assert any(event["type"] == "run_linked" for event in detail.history)


def test_pending_failed_run_surfaces_failed_status(tmp_path):
    _write_task_run_fixture(tmp_path, "ready_run", manifest_status="pass", verify_status="PASS", with_review_ticket=False)
    task_models.create_human_task_record(
        tmp_path,
        task_id="task_custom_record",
        title="April launch copy",
        source_input="fixtures/input.csv",
        source_input_label="April_launch.csv",
        target_locale="ja-JP",
        verify_mode="preflight",
        linked_run_id="ready_run",
        created_at="2026-04-06T08:30:00+00:00",
    )

    task_models.request_human_task_changes(
        tmp_path,
        "task_custom_record",
        note="Please tighten the product names and rerun.",
        new_run_id="pending_run_01",
        at="2026-04-06T09:00:00+00:00",
    )

    detail = task_models.load_human_task_detail(
        tmp_path,
        "task_custom_record",
        pending_runs=[
            {
                "run_id": "pending_run_01",
                "run_dir": str(tmp_path / "data" / "operator_ui_runs" / "pending_run_01"),
                "status": "failed",
                "pid": 3456,
                "started_at": "2026-04-06T09:00:00+00:00",
                "command": [".venv\\Scripts\\python.exe", "scripts/run_smoke_pipeline.py"],
                "input_csv": "fixtures/pending.csv",
                "target_lang": "ja-JP",
                "verify_mode": "preflight",
            }
        ],
    )

    assert detail.latest_run_id == "pending_run_01"
    assert detail.status == "failed"


def test_build_bundle_summary_prefers_downloadable_non_technical_delivery():
    deliveries = [
        task_models.HumanArtifactView(
            artifact_key="operator_summary_md",
            delivery_id="run_01__operator_summary_md",
            label="Delivery summary",
            description="Human-readable summary",
            kind="markdown",
            primary_use="Primary output",
            group_id="primary_output",
            group_label="Primary output",
            openable=False,
            downloadable=False,
            source_run_id="run_01",
            preview_url="/api/tasks/task_run_01/deliveries/run_01__operator_summary_md",
            download_url="/api/tasks/task_run_01/deliveries/run_01__operator_summary_md/download",
            technical_detail=False,
            path="D:/missing/operator_summary.md",
        ),
        task_models.HumanArtifactView(
            artifact_key="run_manifest",
            delivery_id="run_01__run_manifest",
            label="Execution manifest",
            description="Technical details",
            kind="json",
            primary_use="Technical details",
            group_id="supporting_files",
            group_label="Supporting files",
            openable=True,
            downloadable=True,
            source_run_id="run_01",
            preview_url="/api/tasks/task_run_01/deliveries/run_01__run_manifest",
            download_url="/api/tasks/task_run_01/deliveries/run_01__run_manifest/download",
            technical_detail=True,
            path="D:/artifacts/run_manifest.json",
        ),
        task_models.HumanArtifactView(
            artifact_key="smoke_verify_report",
            delivery_id="run_01__smoke_verify_report",
            label="Verification report",
            description="Quality check summary",
            kind="json",
            primary_use="Quality review",
            group_id="validation_report",
            group_label="Validation report",
            openable=True,
            downloadable=True,
            source_run_id="run_01",
            preview_url="/api/tasks/task_run_01/deliveries/run_01__smoke_verify_report",
            download_url="/api/tasks/task_run_01/deliveries/run_01__smoke_verify_report/download",
            technical_detail=False,
            path="D:/artifacts/smoke_verify_report.json",
        ),
    ]

    summary = task_models.build_bundle_summary(deliveries)

    assert summary["primary_delivery_id"] == "run_01__smoke_verify_report"


def test_approve_archive_and_download_move_task_between_buckets(tmp_path):
    _write_task_run_fixture(tmp_path, "ready_run", manifest_status="pass", verify_status="PASS", with_review_ticket=False)
    task_id = task_models.task_id_for_run("ready_run")
    task_models.create_human_task_record(
        tmp_path,
        task_id=task_id,
        title="Ready bundle",
        source_input="fixtures/input.csv",
        target_locale="en-US",
        verify_mode="full",
        linked_run_id="ready_run",
        created_at="2026-04-06T08:00:00+00:00",
    )

    deliveries = task_models.load_human_task_deliveries(tmp_path, task_id)
    primary_delivery_id = deliveries["bundle_summary"]["primary_delivery_id"]
    task_models.approve_human_task_delivery(tmp_path, task_id, delivery_id=primary_delivery_id, at="2026-04-06T08:20:00+00:00")
    approved = task_models.load_human_task_detail(tmp_path, task_id)
    task_models.mark_task_delivery_downloaded(tmp_path, task_id, delivery_id=primary_delivery_id, at="2026-04-06T08:25:00+00:00")
    task_models.archive_human_task(tmp_path, task_id, at="2026-04-06T08:30:00+00:00")
    archived = task_models.load_human_task_detail(tmp_path, task_id)
    active_overview = task_models.load_human_task_overview(tmp_path)
    archived_tasks = task_models.load_human_task_summaries(tmp_path, bucket="archived", include_archived=True, limit=10)

    assert approved.status == "ready_for_download"
    assert approved.bucket == "ready_to_collect"
    assert approved.metrics["approved_at"] == "2026-04-06T08:20:00+00:00"
    assert archived.bucket == "archived"
    assert archived.metrics["downloaded_at"] == "2026-04-06T08:25:00+00:00"
    assert active_overview.total == 0
    assert active_overview.counts_by_bucket["archived"] == 1
    assert archived_tasks[0].task_id == task_id
