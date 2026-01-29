# Omni Test Consolidated Report (Part 1 + 2 + 3)

**Date**: 2026-01-20
**Status**: **FAILED** (Blocked at Part 3 / Batch Mode Validation)

---

## 1. Executive Summary

本次 Omni Test 旨在验证全流程自动化本地化翻译（zh-CN -> ru-RU），涵盖 30,453 行文本。测试分为三个阶段执行：

| Phase | Mode | Engine | Status | Key Metric |
|-------|------|--------|--------|------------|
| **Part 1** | Single Row | `gpt-4.1` | ✅ **Success** | **61.8%** done (18,820 rows) |
| **Part 2** | Batch (v4.0) | `gpt-4.1` | ❌ **Failed** | **Token Explosion** (8k context overflow) |
| **Part 3** | Batch (v5.0) | `gpt-4.1-mini`/`sonnet` | ❌ **Failed** | **Escalation Rate 80%** (Batch Compliance) |

**结论**：

- **Single-Row 模式 (Part 1)** 是目前唯一稳定可行方案，但成本较高 ($4.71 / 1k rows)。
- **Batch 模式 (Part 2/3)** 在当前模型 (`gpt-4.1` default) 和 Prompt 策略下**不可用**。模型无法稳定遵循 "Return JSON Array" 指令，导致大量丢包或死循环。

---

## 2. Phase Analysis

### 2.1 Part 1: The Stable Baseline

*2026-01-19 Execution*

成功使用单行模式翻译了前 18,820 行。

- **Throughput**: ~0.8 rows/sec (Serial/Concurrent)
- **Quality**: No critical format failures reported.
- **Cost**:
  - Total Cost: **$88.69**
  - Rows: 18,820
  - **Unit Cost**: **$4.71 per 1,000 rows**

> **Insight**: 这是我们目前的"保底"方案。虽然慢且贵，但它能work。

### 2.2 Part 2: The Token Explosion

*2026-01-19 Execution*

尝试引入 Batch Mode (Batch Size ~20) 以降低成本，但在 resumption 后迅速失败。

- **Failure Mode**: `completion_tokens` Hit Limit (8000+).
- **Diagnose**: 模型在输出 Batch 结果时，陷入了重复循环 (Repetition Loop)，导致输出无限增长直到截断。
- **Result**: 导致 ~2,500 行的翻译尝试无效，产生了数百万无效 tokens 消耗。此次测试被紧急终止。

### 2.3 Part 3: The Batch Compliance Failure

*2026-01-20 Execution*

引入 Structrued Output Contract (v5.0) 和更先进的 Parser，试图解决 Part 2 问题。

- **Attempted**: Resume from row 18,821.
- **Observed**:
  - **Escalation Rate**: **~80%** (极高)
  - **Missing Rows**: Batch 请求 10 行，模型往往只返回 1-2 行。
- **Alpha Verification**:
  - 抽取 20 行样本，使用 standard `gpt-4.1`。
  - 结果 Escalation Rate **70%**。
  - **Trace 证据**: 模型无视 System Prompt 的 array 要求，倾向于把 batch inputs 当作 continuous text 处理，或者只处理第一条就认为任务结束。

---

## 3. Financial Impact & Ops Metrics

### Consolidated Costs

| Phase | Rows Processed | Cost (USD) | Status |
|-------|----------------|------------|--------|
| Part 1 | 18,820 | $88.69 | ✅ Valid |
| Part 2 | ~2,500 (Fail) | ~$15.00 | ❌ Waste |
| Part 3 | ~9,000 (Fail) | ~$10.00 | ❌ Waste |
| **TOTAL**| **30,453** | **~$113.69** | **Incomplete** |

### Efficiency Comparison

- **Single Row**: 1 input -> 1 output. Stable.
- **Batch Mode**: 10 inputs -> 1 output? (Model fails to map N->N).

---

## 4. Recommendations for Next Iteration

### A. Immediate Fix: Downgrade or Switch

我们无法在当前 Prompt 策略下可以让 `gpt-4.1` 稳定输出 Batch JSON。

1. **Option A (保守)**: 回退到 Part 1 的 **Single Row Strategy**。
    - Pros: 100% 成功率保证。
    - Cons: 成本高 ($4.71/k)，速度受限。
    - **Verdict**: Recommended for immediate project completion.

2. **Option B (激进)**: 更换为 **Claude-3.5-Sonnet** 或 **GPT-4-Turbo** 并重写 Batch Prompt。
    - Pros: 可能挽救 Batch 带来的成本优势。
    - Cons: 需要额外的 R&D 时间进行 Prompt Engineering。

### B. Codebase Improments

- **Sanity Check**: 这次教训表明，在大规模跑数 (10k+) 之前，必须先跑 **50-row Alpha Test**。Part 3 没有先跑小样本就全量 Resume，导致了浪费。
- **Observability**: Part 3 初期 trace 中缺少 output 记录（"Blind Flight"），延迟了问题发现。必须强制开启 Debug Output。

---

## 5. Final Status

**Omni Test 暂停**。等待项目组决定是否回退到 Single Row 模式完成剩余 11,633 行的翻译。
