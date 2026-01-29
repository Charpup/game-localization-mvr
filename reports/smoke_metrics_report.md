# LLM 调用统计报告

生成时间: 2026-01-24T09:31:12.091648

## 总体统计

| 指标 | 值 |
|------|-----|
| 步骤数 | 7 |
| 批次数 | 113 |
| 总行数 | 190 |
| 成功 | 190 |
| 失败 | 0 |
| 总延迟 | 33604ms |

## 按步骤统计

| 步骤 | 批次 | 行数 | 成功 | 失败 | 延迟(ms) | 模型 |
|------|------|------|------|------|----------|------|
| unknown | 58 | 0 | 0 | 0 | 0 | N/A |
| dry_run_test | 0 | 0 | 0 | 0 | 0 | unknown |
| glossary_extract | 1 | 0 | 0 | 0 | 0 | unknown |
| glossary_translate | 3 | 40 | 40 | 0 | 15562 | claude-haiku-4-5-20251001, unknown |
| normalize_tag | 5 | 0 | 0 | 0 | 0 | unknown |
| soft_qa | 10 | 100 | 100 | 0 | 7093 | claude-haiku-4-5-20251001, unknown |
| translate | 33 | 50 | 50 | 0 | 10949 | claude-haiku-4-5-20251001, unknown |
| translate_refresh | 3 | 0 | 0 | 0 | 0 | unknown |