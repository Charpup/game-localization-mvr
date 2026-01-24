# Omni Test — Alpha Test Report (Preliminary)

**生成时间**: 2026-01-20 22:30
**状态**: ❌ FAILED (70% Escalation)

---

## 1. 测试概要

| 项目 | 说明 |
|------|------|
| **测试目标** | 验证 Batch Runtime v5.0 与默认模型 (`gpt-4.1`) 的兼容性 (20 行样本) |
| **输入数据** | Source: `normalized.csv` (18820-18840) |
| **模型配置** | `gpt-4.1` (Router Default) |
| **执行环境** | Local Python Script (`alpha_test_runner.py`) |
| **批处理** | Batch Size: 10 |

---

## 2. 核心指标

| 指标 | 数值 | 评价 |
|------|------|------|
| **总行数** | 20 | |
| **成功行数** | 6 | ❌ 低 |
| **Escalated** | 14 | ⚠️ 高风险 |
| **Escalation Rate** | **70.0%** | ❌ 阻断级失败 |
| **Batch Count** | 2 | |
| **Avg Batch Time** | 9.6s | 正常 |
| **Throughput** | 62.5 rows/min | 理论值尚可，但质量差 |

---

## 3. 失败原因诊断 (Root Cause)

**现象**:

- Prompt 明确要求返回 `JSON ARRAY` (Batch Size = 10)。
- 能够从 Output 中提取到 6 条结果，说明模型**并非完全拒绝**。
- 但是，Trace Log 显示模型输出的是 **单行 JSON 对象** (Single JSON Object)，而非数组。
- 更多时候，模型只返回了 Batch 中的 **其中 1 条** 结果，导致该 Batch 中剩余 9 条被标记为 `missing_after_max_retries`。

**Trace 证据**:

```json
// Batch 计划 10 条，模型只返回了一条:
{"string_id": "304016", "target_ru": "Обновить"}
```

**结论**:
当前默认模型 `gpt-4.1` 在当前 Prompt (v5.0 Structured Output Contract) 下**不支持/不遵循 Batch Instruction**。它倾向于把它当做单行任务处理，忽略了 System Prompt 中 `You MUST return a JSON ARRAY` 的要求，或者因为 Context Window / Attention 问题只处理了第一条。

---

## 4. 后续建议

1. **模型更换**: `gpt-4.1` 可能不适合 Batch Translation。需测试 `claude-3-5-sonnet` 或其他更强指令遵循的模型。
2. **Prompt 降级**: 如果必须使用 `gpt-4.1`，可能需要放弃 Batch Mode，回退到 Single Row Mode (Part 1 模式)，或大幅降低 Batch Size (e.g., 5)。
3. **Prompt 强化**: 尝试 Few-Shot Prompting，给出具体的 Batch 输入输出示例，强制模型理解数组格式。

---

*Report End*
