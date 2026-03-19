# M4 主干识别与 obsolete 候选（基于 1000 行 smoke runs）

## 证据来源
- 全量输入：`D:\Dev_Env\GPT_Codex_Workspace\game-localization-mvr\main_worktree\data\smoke_runs\inputs\test_input_1000_smoke_layered.csv`
- 清洗输入（本轮执行可复用）：`D:\Dev_Env\GPT_Codex_Workspace\game-localization-mvr\main_worktree\data\smoke_runs\inputs\test_input_1000_smoke_layered_run.csv`
- 运行目录：
  - `D:\Dev_Env\GPT_Codex_Workspace\game-localization-mvr\main_worktree\data\smoke_runs\manual_1000_preflight_20260318_121615\`
  - `D:\Dev_Env\GPT_Codex_Workspace\game-localization-mvr\main_worktree\data\smoke_runs\manual_1000_preflight_20260318_121720\`
  - `D:\Dev_Env\GPT_Codex_Workspace\game-localization-mvr\main_worktree\data\smoke_runs\manual_1000_full_20260318_122459\`
- 关键清单文件：
  - `[run manifest](/D:/Dev_Env/GPT_Codex_Workspace/game-localization-mvr/main_worktree/data/smoke_runs/manual_1000_preflight_20260318_121615/run_manifest.json)`
  - `[run manifest](/D:/Dev_Env/GPT_Codex_Workspace/game-localization-mvr/main_worktree/data/smoke_runs/manual_1000_preflight_20260318_121720/run_manifest.json)`
  - `[run manifest](/D:/Dev_Env/GPT_Codex_Workspace/game-localization-mvr/main_worktree/data/smoke_runs/manual_1000_full_20260318_122459/run_manifest.json)`
  - `[smoke verify(full)](/D:/Dev_Env/GPT_Codex_Workspace/game-localization-mvr/main_worktree/reports/smoke_verify_smoke_run_20260318_042459.json)`
  - `[issues(full)](/D:/Dev_Env/GPT_Codex_Workspace/game-localization-mvr/main_worktree/reports/smoke_issues_smoke_run_20260318_042459.json)`

## 一、核心主干判断（本轮可判定）
- 入口与调度：`scripts/run_smoke_pipeline.py`（固定入口）
- 可复用核心链路：`scripts/normalize_guard.py` -> `scripts/translate_llm.py` -> `scripts/qa_hard.py` -> `scripts/rehydrate_export.py` -> `scripts/smoke_verify.py`
- 兼容日志记录：`scripts/smoke_issue_logger.py`
- 这组链路在：
  - `manual_200_full_afterfix_20260318_031031`
  - `manual_305833_single_afterfix_20260318_030929`
  - `manual_1000_full_20260318_122459`（失败节点：到 `QA Hard`）
  三次 recent full 内均可见（前两次全部 pass，第三次阻断于 QA）。

## 二、主干保留判定（保留）
- `run_smoke_pipeline.py`
- `normalize_guard.py`
- `translate_llm.py`
- `qa_hard.py`
- `rehydrate_export.py`
- `smoke_verify.py`
- `smoke_issue_logger.py`

## 三、未触发/非核心候选（依据：未出现在三次 recent full 必要链路）
> 说明：以下分组为“待淘汰候选”，不等于直接删除。需与非 smoke 路径（批处理、回归压测、调试、清洗、语义/修复子系统）联动确认。

1. 1000 行 full 的直接证据下，近期未触发的高可信度“非 smoke 主干”：
- `acceptance_stress_run.sh`
- `acceptance_stress_phase3.sh`
- `acceptance_stress_resume.sh`
- `acceptance_stress_resume_fix.sh`
- `acceptance_stress_final.sh`
- `test_step1_env.sh`
- `stress_test_3k_run.sh`
- `test_3k_test.py`（同 `stress_test_3k_run.sh`）

2. 明确偏调试/诊断类（当前 smokes 主路径未证明必须）：
- `debug_auth.py`
- `debug_destructive_failures.py`
- `debug_llm_format.py`
- `debug_translation.py`
- `debug_v4_traces.py`
- `acceptance_*/debug_*` 关联脚本

3. 明确偏回归/维护/实验脚本（待确认是否仍需服务主线）：
- `fill_missing_rows.py`
- `repair_loop.py`
- `repair_loop_v2.py`
- `repair_checkpoint_gaps.py`
- `rebuild_checkpoint.py`
- `run_destructive_batch_v1.py`
- `run_destructive_batch_v2.py`
- `run_destructive_batch_v3.py`
- `batch_runtime.py`
- `run_dual_gates.py`
- `run_validation.py`
- `build_validation_set.py`

4. 语义/辅助子模块（可能与后续 RU/EN 扩展有关，先保留观察）：
- `normalize_tagger.py`
- `normalize_tag_llm.py`
- `normalize_ingest.py`
- `normalize_guard.py`（已保留主链）
- `runtime_adapter.py`
- `translate_refresh.py`
- `soft_qa_llm.py`
- `qa_soft.py`

## 四、决策规则（建议）
- 保留条件：脚本在最近三次 full 中命中主线 2 次以上且有明确 stage 依赖，或者作为跨层日志/兼容入口被 pipeline 依赖。
- 候选移除条件：7 天内未被触发且在功能目标里找不到明确调用链，且有重复/等效脚本存在。
- 当前冻结区建议：
  - P0 清单先不扩展：优先修复 1000 full 的 hard QA 阻断。
  - 对高可信度 obsolete 候选，仅做“标记 obsolete=true + 保留源码 + 留坑追踪”。
  - 当连续 3 次 full 在主线稳定通过且候选脚本始终未涉及，再开启移除讨论（需备份）。

## 五、下一步（M4）
1. 执行“严格 1000 全链路通关”后再重新计算触达矩阵（需成功到达 Rehydrate 与 Smoke Verify）。
2. 新增脚本触达统计（run manifest 增加 `scripts_invoked` 字段），把“是否触达”作为自动门禁，持续更新 obsolete 候选。
