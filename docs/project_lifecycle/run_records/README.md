# project_lifecycle run_records 说明

> 本目录是 `docs/run_records` 的集中治理层入口。

## 目录组织

```text
docs/project_lifecycle/run_records/
  └── 2026-03/
      └── 2026-03-20/
          ├── run_manifest_<run_id>.json
          ├── run_issue_<run_id>.md
          ├── run_verify_<run_id>.md
          ├── session_start_<YYYYMMDDHHMM>.md
          ├── session_end_<YYYYMMDDHHMM>.md
          └── milestone_state_<A-S>.md
```

## 证据强制映射

关键 run 收口必须形成：

- run_manifest：`run_manifest_<run_id>.json`
- run_issue：`run_issue_<run_id>.md`
- run_verify：`run_verify_<run_id>.md`
- ADR/decision：`decision_refs` 中至少一条

字段定义见 `docs/project_lifecycle/field_schema.md`。

## 跨文件映射规则

- `task_plan.md`：执行账本（事实）
- `docs/project_lifecycle/roadmap_index.md`：里程碑承诺与节奏
- `docs/decisions/`：治理决策（ADR）

## 最低保留策略

- 不允许删除关键 run 记录；如需更正，追加 `run_manifest_v2_<run_id>.json` 并标注 supersedes。
- 按文件系统天然时序排序可重建会话链路。


