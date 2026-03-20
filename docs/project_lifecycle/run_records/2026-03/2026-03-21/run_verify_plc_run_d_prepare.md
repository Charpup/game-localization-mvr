# run_verify_plc_run_d_prepare

- run_id: plc_run_d_prepare
- do_now:
  - 完成 D 里程碑目标拆解与验收框架预置
  - 建立 checksum 与 drift 对账执行路径草案（含命名/输出目录规范）
  - 输出 D 计划级 `run_issue` 与输入清单
- acceptance_criteria:
  - 里程碑 D 有独立 `run_manifest` / `run_issue` / `run_verify`
  - `milestone_D_prepare` 与 `roadmap_index` 的 `next_scope` 保持 `milestone_D_execute`
  - baseline 对账脚本和 `script_checksums` 输入输出规范已形成最小契约
- evidence_ready: false
- block_on:
  - script_checksums.py
  - 首轮 3 条漂移样本（风格/术语/长度）
- result: warn
- verification_cmds:
  - 语义对账与样本脚本执行清单已形成（待首次落盘）
  - `python scripts/style_sync_check.py workflow/style_guide.md workflow/style_guide.generated.md --style-profile data/style_profile.yaml`