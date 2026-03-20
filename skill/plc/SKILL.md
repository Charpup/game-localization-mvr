# plc

Short trigger alias for Project Lifecycle Governance.

## Overview

使用 `plc` 代替 `project_lifecycle_governance` 调用同一套文档治理流程。
该 skill 复用：

- `docs/project_lifecycle/continuity_protocol.md`
- `docs/project_lifecycle/roadmap_index.md`
- `docs/project_lifecycle/field_schema.md`
- `docs/project_lifecycle/run_records/README.md`
- `docs/project_lifecycle/decisions/index.md`
- `skill/project_lifecycle_governance/SKILL.md`

触发场景：

- 需要会话级接续（session_start / session_end）
- 需要对齐里程碑 A→S 进度
- 需要强制 run 证据收口与 ADR 绑定
- 需要在里程碑 S 期间进行 skill vs non-skill 路径决策记录

## One-line usage

一句话约定：`请按 plc 继续项目生命周期治理。`

