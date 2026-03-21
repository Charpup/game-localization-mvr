# run_verify_plc_run_d_full

- run_id: plc_run_d_full
- run_scope: milestone_D_full
- do_now:
  - [x] baseline_drift_control 流程执行完成
- acceptance_criteria:
  - baseline_manifest 与 drift 报告产出且可读
  - 关键阈值失败项可追溯到 run_issue/run_manifest
- result: pass
- verification_cmds:
  - `python scripts/baseline_drift_control.py compare --baseline-manifest D:\Dev_Env\GPT_Codex_Workspace\data\baselines\plc_run_d_prepare\plc_run_d_prepare\baseline_manifest.json --source test_30_repaired.csv --rows 10 --seed 42 --max-row-churn-ratio 0.05 --max-stratum-delta 2`
  - `cat D:\Dev_Env\GPT_Codex_Workspace\data\baselines\plc_run_d_prepare\plc_run_d_prepare\compare\drift_summary.json`
- evidence_ready: true
