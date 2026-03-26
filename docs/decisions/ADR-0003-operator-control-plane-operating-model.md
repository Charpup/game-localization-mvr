# ADR-0003: Operator Control Plane 与长期运营模型

- Status: Accepted
- Date: 2026-03-26T14:30:00+08:00
- Owner: Codex

## Context

项目已经完成 `Phase 1` 的运行时质量闭环、`Phase 2` 的 PLC/TriadDev 治理底座，以及 `Phase 3` 的语言治理与人工回路。当前运行链可以产出 `run_manifest`、`smoke_verify`、`review_ticket`、`feedback_log`、`KPI` 和 `lifecycle` 等 artifact，但操作者仍然需要手工穿读多个文件才能做出下一步判断。

如果 Phase 4 继续直接做重型 GUI，既会引入额外前端负担，也会把当前 artifact-first 的可复现链路打散。项目需要一个 operator-first 的控制面，把已有 artifact 收束为统一任务对象与检查入口，再用 ADR 固定长期 operating model。

## Decision

项目采用 `agent-first operator control plane` 作为 Phase 4 的默认 operating model。

- `Q`：统一 operator card 模型，把 review、runtime、governance、KPI、decision 变成同一种任务对象。
- `R`：优先提供 `CLI + JSON/Markdown` 的 inspection/report surface，不把 polished GUI 作为当前前置条件。
- `S`：正式固定两条运营路径：
  - `skill path`：使用 PLC + TriadDev + operator control plane 作为推荐主路径；
  - `no-skill path`：保留 artifact-first、最小依赖的 fallback 操作方式。

同时固定以下治理规则：

- Phase 以 `one big phase / one main PR` 为默认交付窗口。
- merge/review 发生在 phase 边界，不重新退回 micro-milestone PR。
- runtime 改动若触及 smoke 编排或状态汇总，必须补一条 representative smoke。
- `blocked` / `failed` / open review backlog / governance drift 任一存在时，必须显式生成人工 decision surface，而不是静默继续。

## Alternatives

- 直接做完整 GUI：更接近产品壳层，但会把当前阶段的主要价值从“统一 artifact 决策面”偏移到“界面建设”。
- 继续只保留 artifact，不建立 operator layer：实现成本最低，但操作者仍需手工拼接运行证据，无法形成稳定 operating model。

## Consequences

- 现有 Phase 1-3 artifact 成为 Phase 4 的输入真相源，而不是被新系统绕开。
- 项目能先建立 operator-first 控制面，再决定是否在后续阶段加更重的前端交互层。
- `skill` 与 `no-skill` 路径都保留，但推荐路径变得明确，不再停留在 `ADR-0002` 的 Proposed 状态。

## Rollback

- 若 operator control plane 复杂度过高，可保留现有 artifact contract，回退到 `no-skill` 路径，仅使用 CLI 和 run records。
- 若后续需要前端产品化，可在不改变底层 artifact contract 的前提下，把 Phase 4 CLI/report surface 替换为更重的 UI 壳层。

## Evidence

- `docs/project_lifecycle/roadmap_index.md`
- `task_plan.md`
- `progress.md`
- `.triadev/state.json`
- `.triadev/workflow.json`
- `workflow/operator_card_contract.yaml`
- `scripts/operator_control_plane.py`
- `data/operator_cards/`
- `data/operator_reports/`
