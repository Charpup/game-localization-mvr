# A → S 小时制里程碑排程（项目主干）

> 版本：2026-03-20
> 时间单位：**1 小时**（AI 协作可交付时间单位）
> 起点锚点：`2026-03-20T10:00:00+08:00`（UTC+8，简称 `T0`）

## 文档作用

本文件是 `task_plan.md` 之外的主线执行规划主干。  
`task_plan.md` 继续承担「执行账本」；本文件承担「战略方向 + 里程碑承诺 + 交接可恢复证据」。

默认策略：

- 每个里程碑默认 `WIP=1`，闭环验证后再开启下一里程碑。
- 默认每 2 个里程碑进行一次 `mini review`。
- 默认每 4 个里程碑进行一次 `governance brake`。
- 1 小时为最小可下发任务单元，不再以“人/日”估算。

## 里程碑排程（A → S）

| 里程碑 | 估算小时 | 依赖 | 窗口（T+小时） | 关键交付 |
|---|---:|---|---|---|
| A | 12 | 无 | 0-12 | 交付门禁快照、`task_plan` 与 `HANDOFF_MAINLINE_GUARDRAILS.md` 一致性签字 |
| B | 24 | A | 12-36 | normalize 用例矩阵、错误归类字典、fixture 报表 |
| C | 20 | B | 36-56 | term_candidates 工具链、人工审批模板 |
| D | 16 | C | 56-72 | checksum 对账、翻译漂移复测脚本 |
| E | 18 | D | 72-90 | delta 工具、增量重译任务脚本 |
| F | 24 | B | 90-114 | `qa_hard→repair_loop` E2E 报告、幂等边界 |
| G | 24 | B | 114-138 | soft 规则分类、修复与回退路径 |
| H | 20 | F,G | 138-158 | pass/fail/warn/block 状态机与统一报告 |
| I | 16 | H | 158-174 | Style Guide v0 版本头、入口审计 |
| J | 14 | I | 174-188 | 人工确认任务单、模型反馈日志入库 |
| K | 12 | J | 188-200 | 生命周期与 deprecate 机制 |
| L | 16 | H | 200-216 | 指标定义、月报与趋势图 |
| M | 10 | A | 216-226 | `run_manifest/schema` + 指定字段清单 |
| N | 8 | M | 226-234 | `session_start`/`session_end` 模板、`Next owner` 强制字段 |
| O | 10 | N | 234-244 | 三点校验清单（文件/证据/ADR） |
| P | 14 | O | 244-258 | milestone/status/evidence_ready/owner/ETA 字段模型 |
| Q | 40 | P,L | 258-298 | 看板卡片、任务流转、与 `task_plan`/ADR 链接 |
| R | 48 | Q | 298-346 | 交互式质检入口、报表面板 |
| S | 12 + 16/18 | A,N,O,P,Q,R | 346-358 + 分支 | ADR-000x；`skill` 与 `no-skill` 双路径行动清单 |

## 里程碑 A（12h）细化计划（可直接执行）

### A0 预检与基线（0.5h）
- 校验当前工作树：无未提交治理文件冲突；`docs/project_lifecycle` 主干存在。
- 快速记录：`session_start` 时间戳、`run_id`、本次 owner。

### A1 文档一致性扫描（2h）
- 对齐 `HANDOFF_MAINLINE_GUARDRAILS.md` 与 `task_plan.md` 的“最近状态锚点”：
  - 目录存在性检查：`docs/`（continuity/decisions/run_records/project_lifecycle）
  - ADR 与里程碑快照引用的一致性检查
- 生成 `docs/project_lifecycle/run_records/2026-03/2026-03-21/session_start_<ts>.md`。

### A2 合规门禁快照（2h）
- 复核 `docs/WORKSPACE_RULES.md` 与 `docs/localization_pipeline_workflow.md` 的关键约束（必须读链路、metadata.step、keep-chain）。
- 形成“快照草案”：
  - 门禁项清单（不低于 8 项）
  - 每项状态（pass/warn/block）
  - 阻塞项（如有）及恢复动作

### A3 `task_plan`↔里程碑对齐（2h）
- 将里程碑 A 的状态落到 `task_plan.md` 与 `milestone_state_A` 的同一页签：
  - A `status= in_progress`
  - `progress_pct` 初始 `8~20`（按实际进展）
  - `evidence_ready` 先为 `false`
- 在 `docs/project_lifecycle/run_records/<date>/milestone_state_A.md` 记录字段快照。

### A4 证据模板与追踪约束（2h）
- 生成 `run_manifest` / `run_issue` / `run_verify` 预留路径（当前路径占位，待完成回填）。
- 统一记录 `decision_ref`：如涉及 ADR 变更，先引用 `ADR-0002`。
- 补齐交接模板校验表（session_start ↔ session_end 对齐字段）。

### A5 结果签名与开工冻结（3.5h）
- 更新 `session_start` 的 1h mini plan（最小 1-3 个子单元）。
- 输出 `governance brake` 自检：
  - `3`个文件入口（handoff/task_plan/roadmap）读取已完成
  - `milestone_state_A` 可被 `session_end` 验证
  - 无未登记阻塞项
- 标注里程碑 A 的“开工签字”（当前 owner + 下一责任人 + 下一步 scope）。

### A6 入门复盘（0.5h）
- 输出 `plc` 启动摘要（3~5 条可执行行动）
- 若 A1~A5 未满足，立即将状态回退 `blocked`，触发 mini review。

## 里程碑 A 交付模板（建议）

- `run_id`: `plc_run_a_20260321_1000`
- `scope`: `project_lifecycle_milestone_A`
- `issue_report`: `docs/project_lifecycle/run_records/2026-03/2026-03-21/run_issue_plc_run_a_20260321_1000.md`
- `verify_report`: `docs/project_lifecycle/run_records/2026-03/2026-03-21/run_verify_plc_run_a_20260321_1000.md`
- `evidence_ready`: `true` 后才能推进 B

## 里程碑状态记录规范

所有里程碑必须至少包含以下字段：

- `id`：里程碑编号（如 `A`）
- `status`：`todo|in_progress|blocked|done|shelved`
- `owner`：当前责任人
- `next_owner`：下一责任人
- `progress_pct`：0-100
- `evidence_ready`：`true|false`
- `blockers`：待清单（JSON 数组）
- `dependencies`：依赖里程碑列表
- `decision_ref`：关联 ADR 引用（可空）

记录建议落点：

- `docs/project_lifecycle/run_records/<YYYY-MM>/milestone_state_<id>.md`
- `docs/continuity` 的会话交接文件中同步镜像关键状态

## 里程碑收官必须落盘（验收底线）

每个里程碑结束前必须补齐：

- `run_id`
- `run_manifest`（含 scope 与时间戳）
- `issue_report`
- `verify_report`
- `blocker list`（含恢复动作与 owner）
- 对应 `ADR` 引用（如有）

任意里程碑若未满足上述条目，不能标记 `done`，必须回退为 `blocked` 并触发 `governance brake`。

## 验收场景（跨上下文稳定性）

1. 新设备执行 `session_start`，仅读取 3 个锚点文件即可恢复语境。
2. 两次连续会话交接后，`session_end.next_owner/scope` 与下次 `session_start` 一致。
3. 每个里程碑 completion 至少有一套 `run_manifest/run_issue/run_verify` 与对应 ADR。
4. 阻塞项在 `task_plan.md` 与本文件状态均有映射，无冲突。
5. S 决策后 24 小时内给出退路清单（含执行者）。
