---
trigger: always_on
---

【本工作区：游戏本地化 MVR 规则】

1) 中间产物一律落盘为文件：CSV / JSON。禁止把关键结果只写在聊天里。
2) 所有占位符/标签（如 {0}, %s, <color=...>, \n）必须先由 scripts/normalize_guard.py 冻结为 token，再交给模型处理；未经冻结不得翻译。
3) 在导出最终包之前，必须运行 scripts/qa_hard.py；若 qa_hard_report.json 中 has_errors=true，则立刻停止并进入修复流程。
4) 修复（repair）只能修改被 qa_hard_report.json 标记的行；禁止全表重写。
5) 每一步必须产出“可验证证据”：
   - 运行了哪些命令（终端日志）
   - 产生了哪些文件（路径 + 简要摘要）
6) 一旦检测到未知占位符模式或源文本标签不平衡：立刻 Reject（停止），在 qa_hard_report.json 写明原因与样例行。
7) 默认以可复现为先：若脚本/规则版本变化，必须在输出文件头部或 report 中记录版本号/时间戳。
