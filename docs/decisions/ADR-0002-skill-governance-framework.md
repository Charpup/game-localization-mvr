# ADR-0002: Skill 与非 Skill 两条路径的治理框架

- Status: Proposed
- Date: 2026-03-20T10:00:00+08:00
- Owner: Codex

## Context

`src/scripts` 已经确认保留为兼容镜像，`main_worktree/scripts` 为运行权威。随着项目体量增长，当前项目治理与执行节奏变复杂，是否将生命周期治理机制封装为 repo skill 存在两条路径：

- **Path A（skill）**：将 `project_lifecycle` 治理流程（启动、交接、里程碑收口）封装为 repo skill。
- **Path B（no-skill）**：保留现有纯文档流程，仅优化文档结构与执行一致性。

## Decision

本 ADR 先不作最终通过决定（保持 `Proposed`），用于在里程碑 S 阶段触发对比评审。  
S 阶段将基于 24h 内的回退链路演练与协作可维护性对上述两路径做 No-Go / Go 决定。

## Alternatives

- 立即封装为 skill：可复用高、可调用高，但实施与迁移成本偏高。
- 直接坚持文档流程：实施成本低，但后续在多会话上下文中重复建模成本更高。

## Consequences

- 如果择优为 skill：需要新增并维护 `skill/project_lifecycle_governance/`，并保证与既有 `task_plan`、`ROADMAP_A_TO_S`、ADR、run records 一致。
- 如果择优 no-skill：将仅维护文档标准和模板，保持执行入口最小化。

## Rollback

S 决策任何一条路径可在 24 小时内切换：

- 从 skill 切回 no-skill：保留当前所有 run 文件与 ADR，移除 skill 路径依赖，保留文档模板。
- 从 no-skill 切到 skill：补齐 skill 文档入口并做一次全量交接演练。

## Evidence

- 受影响流程：`docs/project_lifecycle/*`、`task_plan.md`、`docs/continuity/CONTINUITY_OPERATING_PROCEDURE.md`
