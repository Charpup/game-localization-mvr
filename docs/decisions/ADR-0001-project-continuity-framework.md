# ADR-0001: 引入跨会话持续化治理框架

- Status: Accepted
- Date: 2026-03-20T00:00:00+08:00
- Owner: Codex

## Context

当前仓库的 `task_plan.md` 已承担历史执行账本职责，但缺少统一的未来路线层与决策/证据层。
在 AI Agent 驱动开发中，单会话上下文窗口与设备切换会导致历史状态丢失，影响交付一致性。

## Decision

采用三层治理文档体系并作为主线：

1. `task_plan.md` 保持历史执行记录；
2. `docs/project_lifecycle/roadmap_index.md` 作为未来路线主干（A→S）；
3. `docs/decisions/` 落地 ADR 实体，`docs/project_lifecycle/run_records/` 落地证据链；
4. 以 `docs/project_lifecycle/continuity_protocol.md` 作为会话级交接与启动/结束强制流程。

## Alternatives Considered

- 仅扩展 `task_plan.md`：缺少里程碑语义与决策可追溯性；
- 外部工具单点化管理：同步成本高、可迁移性低，且与仓库治理文件弱耦合；
- 仅依赖 Git 历史：适合代码追踪，但不足以承载会话状态和跨域交付边界信息。

## Consequences

- 增加文档维护成本，但显著提升跨会话恢复速度；
- 决策与 run 证据可逆向追溯，减少“靠聊天记忆”导致的边界误差；
- 为后续里程碑 E 及更高阶段的治理扩展保留稳定入口。

## Rollback

若实践证明过重，可在后续 review 中回退为最小治理集：

- 合并 `roadmap_index.md` 的关键章节回 `task_plan.md`；
- 保留最小 ADR 与 dated run records；
- 停用额外兼容入口，回到单一 PLC 主干。

## Evidence

- `task_plan.md`
- `docs/project_lifecycle/roadmap_index.md`
- `docs/project_lifecycle/continuity_protocol.md`
- `docs/project_lifecycle/run_records/README.md`
