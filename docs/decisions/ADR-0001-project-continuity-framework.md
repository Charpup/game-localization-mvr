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
2. `docs/ROADMAP_A_TO_S.md` 作为未来路线主干（A→S）；
3. `docs/decisions/` 落地 ADR 与 `docs/run_records/` 落地证据链；
4. 以 `docs/continuity/CONTINUITY_OPERATING_PROCEDURE.md` 作为会话级交接与启动/结束强制流程。

## Alternatives Considered

- 仅扩展 `task_plan.md`：缺少里程碑语义与决策可追溯性；
- 外部工具单点化管理：引入同步成本高、可迁移性低，且与本项目治理文件弱耦合；
- 仅依赖 Git 历史：历史 commit 适合代码追踪，但不足以承载会话状态和跨域交付边界信息。

## Consequences

- 增加文档创建/维护工作量，但显著提升上下文恢复速度；
- 决策有标准入口，减少“靠对话记忆”导致的边界误差；
- 便于后续把里程碑映射到看板或前端工作流。

## Rollback

若实践上证明过重，可在 2 周后进行回退：

- 合并 `ROADMAP_A_TO_S.md` 与 `task_plan.md` 关键章节；
- 保留 `task_plan.md` 与最小的 ADR，逐步停用 continuity 手册章节。

## Evidence

- `task_plan.md`
- `docs/ROADMAP_A_TO_S.md`
- `docs/continuity/CONTINUITY_OPERATING_PROCEDURE.md`
- `docs/run_records/README.md`

