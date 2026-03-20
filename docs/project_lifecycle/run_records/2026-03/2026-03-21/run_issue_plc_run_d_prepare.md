# run_issue_plc_run_d_prepare

- run_id: plc_run_d_prepare
- run_scope: milestone_D_prepare
- severity_summary: warn
- blockers:
  - D 级复核脚本与基线数据尚未落盘
- completed_checks: []
- pending_checks:
  - ✅ 样本漂移基线定义（文本维度：长度/占位符/术语偏差）
  - ✅ 对账脚本 `script_checksums.py` 设计与参数规范
  - ✅ 里程碑 D 测试手册（fail-safe 与恢复建议）
  - ✅ `milestone_C_verify_artifacts` 的可复用指标模板抽取
- evidence_ready: false
- note: D 里程碑准备阶段已进入执行前状态，等待第一轮 baseline 样本与 checksum 脚本落盘后转入 `milestone_D_execute`。