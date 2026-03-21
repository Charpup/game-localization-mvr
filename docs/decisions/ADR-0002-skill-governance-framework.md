# ADR-0002: Skill 与非 Skill 两条路径的治理框架

- Status: Proposed
- Date: 2026-03-20T10:00:00+08:00
- Owner: Codex

## Context

随着 PLC 治理链路落地，项目需要在两条治理路径之间保持可切换：

- Path A（skill）：将生命周期治理流程封装为 repo skill；
- Path B（no-skill）：保留纯文档流程，仅维护模板、run records 与 ADR。

当前分支需要先把 C/D 里程碑证据链整合进主线，因此先保留该决策为 `Proposed`，避免在整合修复阶段混入新的路线承诺。

## Decision

本 ADR 暂不做最终通过决定，先作为 PLC 里程碑 A-D 的 `decision_ref` 锚点保留。
后续在里程碑 S 再基于 24h 回退链路演练、维护成本与跨会话稳定性做 Go / No-Go 决策。

## Alternatives

- 立即封装为 skill：复用性高，但会把当前整合步骤扩大成新的实现项目；
- 完全坚持 no-skill：实施成本低，但后续多会话治理的重复建模成本更高。

## Consequences

- 当前阶段可以用统一 `decision_ref` 维持 PLC 证据链闭环；
- skill 化是否推进被显式推迟到后续里程碑，而不是在 C/D 收口阶段隐式决定；
- 后续若选择 skill 路线，需要同步保持 `task_plan.md`、`roadmap_index.md`、ADR 与 run records 一致。

## Rollback

两条路径均可在后续 review 中切换：

- 从 skill 切回 no-skill：保留所有 dated run files 与 ADR，仅移除 skill 入口依赖；
- 从 no-skill 切到 skill：新增 skill 文档入口并补一次完整 handoff 演练。

## Evidence

- `docs/project_lifecycle/continuity_protocol.md`
- `docs/project_lifecycle/roadmap_index.md`
- `docs/project_lifecycle/run_records/2026-03/2026-03-21/`
- `task_plan.md`
