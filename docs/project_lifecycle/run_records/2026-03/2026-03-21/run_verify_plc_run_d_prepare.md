# run_verify_plc_run_d_prepare

- run_id: plc_run_d_prepare
- run_scope: milestone_D_prepare
- do_now:
  - [x] baseline_drift_control 流程执行完成
- acceptance_criteria:
  - baseline_manifest 与 drift 报告产出且可读
  - 关键阈值失败项可追溯到 run_issue/run_manifest
- result: pass
- verification_cmds:
  - `python scripts/baseline_drift_control.py create-baseline --name plc_run_d_prepare --source D:\Dev_Env\GPT_Codex_Workspace\test_30_repaired.csv --rows 10 --seed 42`
  - `python scripts/baseline_drift_control.py compare --baseline-manifest D:\Dev_Env\GPT_Codex_Workspace\data\baselines\plc_run_d_prepare\plc_run_d_prepare\baseline_manifest.json --source D:\Dev_Env\GPT_Codex_Workspace\test_30_repaired.csv --rows 10 --seed 42`
- evidence_ready: true
