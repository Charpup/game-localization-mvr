---
description: Repair Loop - Auto-fix hard and soft QA issues
---

# /loc-repair-loop Workflow

## 目标

自动修复 hard QA 与 soft QA major 问题，且只允许 `scripts/repair_loop.py` 的 flags CLI 作为文档 authority。输出：
- `data/repaired.csv` - 只改动被标记行
- `data/repair_reports/*` - checkpoint snapshot、heartbeat、stats、DONE 标记与 escalation 报告

## 执行命令

```bash
python scripts/repair_loop.py \
  --input data/translated.csv \
  --tasks data/qa_hard_report.json \
  --output data/repaired.csv \
  --output-dir data/repair_reports/hard \
  --qa-type hard
```

```bash
python scripts/repair_loop.py \
  --input data/translated.csv \
  --tasks data/repair_tasks.jsonl \
  --output data/repaired.csv \
  --output-dir data/repair_reports/soft \
  --qa-type soft
```

说明：
- `--tasks` 同时接受 hard QA 的 JSON report 和 soft QA 的 JSONL tasks 文件。
- `--qa-type soft` 是对外 CLI 参数；内部 LLM routing step 会写成 `repair_soft_major`。

## 输入文件

| 文件 | 说明 |
|------|------|
| `data/translated.csv` | 当前待修复的完整 CSV |
| `data/qa_hard_report.json` | Hard QA 报告；可直接通过 `--tasks` 传入 |
| `data/repair_tasks.jsonl` | Soft QA 产出的 major repair tasks |

## 输出文件

| 文件 | 说明 |
|------|------|
| `data/repaired.csv` | 修复后的完整 CSV |
| `data/repair_reports/<qa-type>/repair_checkpoint.json` | 当前轮次快照，用于观测 pending/stats |
| `data/repair_reports/<qa-type>/repair_heartbeat.txt` | 运行心跳 |
| `data/repair_reports/<qa-type>/repair_<qa-type>_stats.json` | 修复统计 |
| `data/repair_reports/<qa-type>/escalated_<qa-type>_qa.csv` | 无法自动修复的条目 |

## 修复策略

1. **Hard fail 优先**：先修 hard QA 标红行（否则出不了包）
2. **Soft major 次之**：只修 major（minor 留人工润色）；对外命令仍使用 `--qa-type soft`
3. **每行验证**：修复后立即验证 token 数量和无中文

## 选项说明

- `--input`：待修复 CSV
- `--tasks`：repair work items，支持 hard report JSON 或 soft tasks JSONL
- `--output`：修复结果 CSV
- `--output-dir`：repair artifacts 目录
- `--qa-type`：`hard` 或 `soft`
- `--config`：repair 配置文件，默认 `config/repair_config.yaml`

## 后续步骤

1. 用 `repaired.csv` 覆盖 `translated.csv`（或让后续步骤读取 `repaired.csv`）：
   ```bash
   copy data\repaired.csv data\translated.csv
   ```

2. 重新运行 `/loc-qa-hard` 验证：
   ```bash
   python scripts/qa_hard.py data/translated.csv data/placeholder_map.json data/qa_hard_report.json workflow/placeholder_schema.yaml
   ```

3. 循环直到：
   - PASS（has_errors=false）
   - 或错误稳定进入 `escalate_list.csv`

## Checkpoint Snapshot Semantics

`repair_checkpoint.json` 目前只记录当前轮次的 pending 计数和统计信息，作为 checkpoint snapshot / 运行证据使用。
当前实现不承诺恢复中断前的 repair 状态；如果中断，请基于最新输入文件和任务文件重新运行完整 repair 命令，而不是依赖自动 resume。
