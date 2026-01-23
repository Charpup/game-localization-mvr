---
trigger: always_on
---

【本工作区：游戏本地化 MVR 规则】

## 核心规则 (1-10)

1) 中间产物一律落盘为文件：CSV / JSON。禁止把关键结果只写在聊天里。
2) 所有占位符/标签（如 {0}, %s, <color=...>, \n）必须先由 scripts/normalize_guard.py 冻结为 token，再交给模型处理；未经冻结不得翻译。
3) 在导出最终包之前，必须运行 scripts/qa_hard.py；若 qa_hard_report.json 中 has_errors=true，则立刻停止并进入修复流程。
4) 修复（repair）只能修改被 qa_hard_report.json 标记的行；禁止全表重写。
5) 每一步必须产出"可验证证据"：
   - 运行了哪些命令（终端日志）
   - 产生了哪些文件（路径 + 简要摘要）
6) 一旦检测到未知占位符模式或源文本标签不平衡：立刻 Reject（停止），在 qa_hard_report.json 写明原因与样例行。
7) 默认以可复现为先：若脚本/规则版本变化，必须在输出文件头部或 report 中记录版本号/时间戳。
8) Soft QA 不作为阻断门槛，但必须产出 repair_tasks.jsonl，用于驱动 Repair Loop。
9) Repair Loop 的输出必须是"只改动被标记行"的 repaired.csv；并且必须保存 repair_checkpoint.json 以支持断点续传。
10) Runtime Adapter 是唯一允许的 LLM 调用入口：业务脚本不得直接写 HTTP 调用逻辑，必须通过 scripts/runtime_adapter.py 统一处理与留痕。

## LLM 调用规则 (11-13)

1) 所有 llm.chat() 调用必须传 metadata.step：
    - 有效值：translate / soft_qa / repair_hard / repair_soft_major / glossary_autopromote
    - 否则视为 unknown step，metrics 归类为 unknown 并报警
2) runtime_adapter 必须写 trace 到 llm_trace.jsonl；LLM_TRACE_PATH 环境变量不可设为空。
3) 推荐在 metadata 中传递 batch_id / string_id / scope 等辅助字段，便于 metrics drill-down。

## Metrics 规则 (14-16)

1) 成本计算优先走 usage 精准计费；无 usage 则 fallback 到字符数估算 (chars/4) 并显式标注 estimated_calls。
2) 计费模式由 config/pricing.yaml 的 billing.mode 控制：
    - multiplier：平台倍率公式
    - per_1m：每百万 token 定价
3) unknown step 占比 > 1% 时，metrics_report.md 中显示警告。

## Glossary 规则 (17-20)

1) glossary_autopromote.py 只能产生 status: proposed；禁止自动改 approved。
2) approved 必须经人工审核后，通过 glossary_apply_patch.py 应用。
3) glossary 的分域由 scope 控制，至少区分：
    - language_pair (zh-CN->ru-RU)
    - ip/project (ip_naruto, project_xxx)
4) 若 proposed 与现有 approved 冲突（同 term_zh 不同 term_ru），则不纳入 proposals，需人工处理。

---
Version: 2.0
Last Updated: 2026-01-12
