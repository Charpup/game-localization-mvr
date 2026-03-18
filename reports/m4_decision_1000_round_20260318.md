# M4 决议：1000 行冒烟修复与主干识别（2026-03-18）

## 1) 执行结论（本轮）

### 里程碑状态
- M4-0（基线与连通）：
  - `llm_ping`：通过（`response=PONG`）
  - 输入健康检查：已执行，见 `manual_1000_preflight_20260318_121615` 与 `manual_1000_preflight_20260318_121720`
  - 结论：**阻断（P0）**
- M4-1（Preflight）：
  - 产物路径：`D:\Dev_Env\GPT_Codex_Workspace\game-localization-mvr\main_worktree\data\smoke_runs\manual_1000_preflight_20260318_121615\`
  - 阻断原因：`Normalize` 失败（`NORMALIZE_FAIL`）
- M4-1（清洗后复测）：
  - 产物路径：`D:\Dev_Env\GPT_Codex_Workspace\game-localization-mvr\main_worktree\data\smoke_runs\manual_1000_preflight_20260318_121720\`
  - 结论：`Connectivity/Normalize/Translate` 通过，`QA Hard` 失败（`85` 条）
- M4-2（Full）：
  - 产物路径：`D:\Dev_Env\GPT_Codex_Workspace\game-localization-mvr\main_worktree\data\smoke_runs\manual_1000_full_20260318_122459\`
  - 结论：`Connectivity/Normalize/Translate` 通过，`QA Hard` 失败（`85` 条）

### 关键失败链路
1. `NORMALIZE_FAIL`（P0）
   - 文件：`D:\Dev_Env\GPT_Codex_Workspace\game-localization-mvr\main_worktree\reports\smoke_issues_smoke_run_20260318_041615.json`
   - 根因：原始输入 `test_input_1000_smoke_layered.csv` 存在 `string_id` 重复 `"(自身下一星级提高至:{1}）"`（重复 2 次）
2. `QA_HARD_FAIL`（P0）
  - 文件：
    - `D:\Dev_Env\GPT_Codex_Workspace\game-localization-mvr\main_worktree\reports\smoke_issues_smoke_run_20260318_041720.json`
    - `D:\Dev_Env\GPT_Codex_Workspace\game-localization-mvr\main_worktree\reports\smoke_issues_smoke_run_20260318_042459.json`
   - 分布：`tag_unbalanced` 1、`forbidden_hit` 1、`new_placeholder_found` 83
   - 说明：`new_placeholder_found` 主要为 `%`/`{1}` 参数语义未完全冻结入映射
3. `VERIFY_HARD_QA_FAIL`（P1/P0，按门禁策略建议 P0）
   - 文件：
    - `D:\Dev_Env\GPT_Codex_Workspace\game-localization-mvr\main_worktree\reports\smoke_verify_smoke_run_20260318_041720.json`
    - `D:\Dev_Env\GPT_Codex_Workspace\game-localization-mvr\main_worktree\reports\smoke_verify_smoke_run_20260318_042459.json`
   - 现象：`overall=PASS` 但 `qa_rows` 包含 `Hard QA: has_errors=True`，与阻断语义不一致

### 行数对齐与数据质量
- 清洗输入 `test_input_1000_smoke_layered_run.csv`：1003 行，`string_id` 无重复，`source_zh` 无空值
- Full 结果显示 `smoke_translated.csv` 实际写入 `1002/1003`（缺失 `string_id=7390906`，`token_mismatch`）
- `manual_1000_full_20260318_122459` 路径下当前未见 `smoke_final_export.csv`（因 QA 阻断）

## 2) PASS / Block / Backlog

- PASS
  - 入口链路可执行（`run_smoke_pipeline.py`）
  - 关键清单文件产出（`run_manifest` / `smoke_issue` / `smoke_verify`）
  - 运行健康检测与路径发现逻辑可复现
- Block（阻断）
  - `manual_1000_preflight_20260318_121720`：`QA Hard` 阻断
  - `manual_1000_full_20260318_122459`：`QA Hard` 阻断
  - `smoke_verify` 阶段仍携带 `VERIFY_HARD_QA_FAIL`
- Backlog
  - placeholder 规则扩展（`%` 与 `{}`）
  - `forbidden_patterns` 与标签闭合策略收敛
  - `verify` 和 manifest `row_checks` 的门禁统一化

## 3) M4 下一步执行计划（v1.1）

### M4-3 主干清洗输出
- 保留核心链路已确认（并含 issue 记录）：
  - `run_smoke_pipeline.py`
  - `normalize_guard.py`
  - `translate_llm.py`
  - `qa_hard.py`
  - `rehydrate_export.py`
  - `smoke_verify.py`
  - `smoke_issue_logger.py`
- 详情见：`D:\Dev_Env\GPT_Codex_Workspace\game-localization-mvr\main_worktree\reports\m4_mainsmoke_core_obsolete_20260318.md`

### 4) 清晰关闭条件（到 M4-4）
1. 使用清洗输入重跑：
   - `python scripts/run_smoke_pipeline.py --input data/smoke_runs/inputs/test_input_1000_smoke_layered_run.csv --run-dir data/smoke_runs/manual_1000_preflight_<ts> --target-lang en-US --verify-mode preflight ...`
   - `python scripts/run_smoke_pipeline.py --input data/smoke_runs/inputs/test_input_1000_smoke_layered_run.csv --run-dir data/smoke_runs/manual_1000_full_<ts> --target-lang en-US --verify-mode full ...`
2. 通过标准：
   - P0 全清零：`QA_HARD_FAIL=0`，`VERIFY_HARD_QA_FAIL=0`
   - 行数闭环：`input_rows == translate_rows == final_rows == 1003`
   - `smoke_verify` 无阻断告警
3. 同步补齐 `run_manifest.row_checks` 与 `smoke_verify` `overall` 一致性语义

### 5) 下一步建议命令清单
1. 先处理输入规范与占位符：
   - 统一修正 `%` 与 `{}` 映射、补齐 `%` 白名单/转义策略
   - 修复 `string_id=7390906` 的 `token_mismatch`
2. 单行回归：
   - 针对 `7390906` 与 `%`/`{}` 边界样例复测 `normalize -> qa_hard -> rehydrate_export`
3. 再跑 1000 行 preflight/full，并用同一套文件路径输出：
   - `manual_1000_preflight_<timestamp>/`
   - `manual_1000_full_<timestamp>/`
