# A → S 小时制里程碑排程（项目主干）

> 版本：2026-03-24
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

> 自 `milestone E` 起，`F → S` 保留原字母映射，但执行视图改写为「4 个阶段」。
> 上表保留为索引表；后续实际规划以下文四阶段定义为准。

## 里程碑 B（实时状态）

- `run_id`：`plc_run_b_202603211300`
- `status`：`done`
- `evidence_ready`：`true`
- `blocker`：`无`
- `next_owner`：`Codex`
- `next_scope`：`milestone_C_execute`

## 里程碑 C（实时状态）

- `run_id`：`plc_run_c_202603212000`
- `status`：`done`
- `evidence_ready`：`true`
- `blocker`：`无`
- `next_owner`：`Codex`
- `next_scope`：`milestone_D_prepare`

## 里程碑 D（实时状态）

- `run_id`：`plc_run_d_verify`
- `status`：`done`
- `evidence_ready`：`true`
- `blocker`：`无`
- `next_owner`：`Codex`
- `next_scope`：`milestone_E_prepare`

## E 后续接点（2026-03-25）

- `current_scope`：`milestone_M_prepare`
- `branch_state`：`milestone E + phase 1 merged into main`
- `evidence_ready`：`true`
- `next_owner`：`Codex`
- `recommended_next_scope`：`milestone_M_prepare`
- `parallel_planning_sidecar`：`milestone_F_execute_followup`

## E 后四阶段重写（保留 F → S 映射）

### 阶段总览

| 阶段 | 保留里程碑映射 | 核心目标 | 应达效果 |
|---|---|---|---|
| Phase 1: 质量闭环与路由 | F + G + H | 打通 `delta → qa_hard / soft rules → repair / review → unified status` | 系统能稳定判断“哪些自动修、哪些人工复核、哪些阻断”，并输出统一状态机与报告 |
| Phase 2: 治理底座与可追溯运营 | M + N + O + P | 先把 `run/session/evidence/milestone` schema 与交接协议固定下来 | 后续所有 delta/task/review/run artifact 都有稳定字段模型和跨会话恢复锚点 |
| Phase 3: 语言治理与人工回路 | I + J + K + L | 把 style/feedback/term lifecycle 变成长期可运营的治理层 | 风格版本、人工确认、反馈入库、废弃流程、指标月报形成闭环 |
| Phase 4: 操作台与产品化决策 | Q + R + S | 把 PLC/TriadDev 证据链提升为 agent-first operator control plane | 任务流转、质检入口、报表与 ADR 决策从脚本系统升级为操作系统 |

### 推荐执行顺序

- `Phase 1` 与 `Phase 2` 在 `milestone E` 之后优先启动，其中 `Phase 2` 作为治理底座与 `Phase 1` 并行规划。
- `Phase 3` 在 `H` 完成、治理字段模型稳定后进入主实现。
- `Phase 4` 明确以 `agent-first` 为先，不把传统 GUI 作为 `Q/R` 的前置硬依赖。

### Phase 1：质量闭环与路由（F / G / H）

#### F
- 目标：把 `qa_hard → repair_loop` 做成可复跑、可回归、可证明幂等边界的 E2E 闭环。
- 效果：修复链不再只是脚本串联，而是带 report/manifest/gate 的受控执行链。

#### G
- 目标：把 soft 规则从“非结构化建议”升级成可分类、可修复、可回退、可人工接管的路由层。
- 效果：soft 问题不再和 hard blocking 混杂，manual review / soft QA / bounded repair 的边界清晰。

#### H
- 目标：统一 `pass/fail/warn/block` 状态机与报告合同，覆盖 delta、qa、repair、review 几类产物。
- 效果：E/F/G 的各类结果能汇总成单一 run status 语言，PLC 与运行时报告彻底对齐。

### Phase 2：治理底座与可追溯运营（M / N / O / P）

#### M
- 目标：固定 `run_manifest/schema` 与指定字段清单，覆盖 delta/task/run/review 产物。
- 效果：后续自动化和报表能依赖稳定 schema，而不是隐式字段约定。

#### N
- 目标：固定 `session_start` / `session_end` 模板，强制 `Next owner` / `Next scope`。
- 效果：跨设备、跨会话、跨 agent 的 handoff 可以稳定恢复。

#### O
- 目标：固定文件/证据/ADR 三点校验清单。
- 效果：每次交付都能说明“改了哪些文件、证据在哪、决策引用是什么”。

#### P
- 目标：固定 `milestone/status/evidence_ready/owner/ETA` 字段模型。
- 效果：roadmap、task plan、run record、看板卡片共享同一种里程碑状态语言。

### Phase 3：语言治理与人工回路（I / J / K / L）

#### I
- 目标：把 Style Guide / style profile 升级成有版本头、入口校验、可追溯引用的治理对象。
- 效果：风格规则成为“版本化 contract”，不再只是 prompt 附件。

#### J
- 目标：建立人工确认任务单、审校动作记录和模型反馈日志入库。
- 效果：human-in-the-loop 从临时介入升级成可沉淀、可统计、可回放的运营资产。

#### K
- 目标：建立 terminology / style / policy 的 lifecycle 与 deprecate 机制。
- 效果：旧规则、旧术语、旧执行路径能正式退役，不会无限堆积。

#### L
- 目标：建立质量、成本、人工介入率、多市场差异的指标定义与月报。
- 效果：项目从“脚本能不能跑”升级为“运营质量是否持续改善”的管理视角。

### Phase 4：操作台与产品化决策（Q / R / S）

#### Q
- 目标：建立 agent-first 的看板卡片、任务流转、与 `task_plan` / ADR / evidence 的深链接。
- 效果：操作者可以按任务对象而不是按脚本文件来管理项目。

#### R
- 目标：建立交互式质检入口和报表面板，但默认先支持 agent/CLI 驱动的操作壳层。
- 效果：产品开始具备操作者界面，但不牺牲当前 artifact-first 的可复现性。

#### S
- 目标：形成 ADR-000x 级别的长期运营决策，并明确 `skill` / `no-skill` 双路径行动清单。
- 效果：项目从 milestone 链条收束为长期 operating model，而不是一次性工程堆栈。

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
