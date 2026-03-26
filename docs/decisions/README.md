# 决策文档（ADR）规范

> 实施建议优先统一到：
> `docs/project_lifecycle/decisions/index.md`

## 核心规则

- 文件命名：`ADR-####-short-title.md`
- 状态流：`Proposed -> Accepted -> Deprecated/Superseded`
- 必须字段：`Status, Context, Decision, Alternatives, Consequences, Rollback, Evidence, Date, Owner`
- 影响边界：运行链路、quality 门禁、文档治理、skill 化路径
- Phase 4 起新增：operator control plane / operating model ADR 也必须落在本目录

本目录承载 ADR 实体文件；路线快照与 run evidence 统一记录在 `docs/project_lifecycle/*`。
