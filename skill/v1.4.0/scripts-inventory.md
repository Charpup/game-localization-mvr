# Scripts Inventory v1.4.0

> Total: 69 scripts migrated to v1.4.0 | 32 remaining in v1.3.0 | Last updated: 2026-02-21

## 📁 Directory Structure

```
scripts/
├── cli.py              # CLI 入口 (NEW)
├── __init__.py         # 包初始化 (NEW)
├── core/               # 核心翻译流程 (13个) ✅
│   ├── __init__.py
│   ├── batch_runtime.py          # 主翻译流程
│   ├── batch_sanity_gate.py      # 前置检查
│   ├── glossary_translate_llm.py # 术语翻译
│   ├── soft_qa_llm.py            # 软质检
│   ├── repair_loop.py            # 修复 v1
│   ├── repair_loop_v2.py         # 修复 v2
│   ├── emergency_translate.py    # 紧急翻译
│   ├── merge_shards.py           # 合并分片
│   ├── preprocess_csv.py         # CSV 预处理
│   ├── fill_missing_rows.py      # 补全行
│   ├── fix_csv_header.py         # 修复表头
│   └── translate_refresh.py      # 刷新翻译
├── utils/              # 工具库 (12个) ✅
│   ├── __init__.py
│   ├── lib_text.py               # 文本处理
│   ├── batch_utils.py            # 批处理工具
│   ├── metrics_aggregator.py     # 指标聚合
│   ├── progress_reporter.py      # 进度报告
│   ├── cost_monitor.py           # 成本监控
│   ├── cost_snapshot.py          # 成本快照
│   ├── llm_ping.py               # LLM 测试
│   ├── consolidate_full_results_v2.py
│   ├── finalize_stress_report.py
│   ├── apiyi_usage_client.py
│   └── glossary_vectorstore.py
├── debug/              # 调试诊断 (11个) ✅
│   ├── __init__.py
│   ├── debug_llm_format.py
│   ├── debug_translation.py
│   ├── debug_auth.py
│   ├── debug_destructive_failures.py
│   ├── debug_v4_traces.py
│   ├── diagnose_direct_api.py
│   ├── diagnose_sequential_batch.py
│   ├── diagnose_single_call.py
│   ├── diagnose_sonnet_retest.py
│   └── trace_diagnostic.py
├── testing/            # 测试相关 (19个) ✅
│   ├── __init__.py
│   ├── alpha_test_runner.py
│   ├── smoke_verify.py
│   ├── test_router_check.py
│   ├── test_step2_embedding.py
│   ├── test_step3_glossary.py
│   ├── test_step4_semantic.py
│   ├── acceptance_p8_helper.py
│   ├── verify_3k_test.py
│   ├── create_part1_checkpoint.py
│   ├── rebuild_checkpoint.py
│   ├── repair_checkpoint_gaps.py
│   ├── test_step1_env.sh
│   ├── acceptance_stress_run.sh
│   ├── acceptance_stress_resume.sh
│   ├── acceptance_stress_resume_fix.sh
│   ├── acceptance_stress_phase3.sh
│   ├── acceptance_stress_final.sh
│   └── stress_test_3k_run.sh
└── deprecated/         # 废弃脚本 (12个) ✅
    ├── __init__.py
    ├── run_destructive_batch_v1.py
    ├── run_destructive_batch_v2.py
    ├── run_destructive_batch_v3.py
    ├── temp_check_lock.py
    ├── temp_ckpt_check.py
    ├── prepare_destructive_assets.py
    ├── prepare_long_text_assets_v1.py
    ├── fix_progress_logs.py
    ├── combine_repair_tasks.py
    ├── merge_repair_outputs.py
    └── dev_prompt_improver.py
```

---

## 🔵 Core (核心) - 12 scripts

核心翻译流程脚本，构成主业务逻辑。

| Script | Purpose | Status |
|--------|---------|--------|
| `batch_runtime.py` | 主翻译流程，批量处理 worker | ✅ Migrate |
| `batch_sanity_gate.py` | 批处理前置检查门 | ✅ Migrate |
| `glossary_translate_llm.py` | 术语表 LLM 翻译 | ✅ Migrate |
| `soft_qa_llm.py` | 软质检 (LLM-based QA) | ✅ Migrate |
| `repair_loop.py` | 修复循环主逻辑 v1 | ✅ Migrate |
| `repair_loop_v2.py` | 修复循环主逻辑 v2 (推荐) | ✅ Migrate |
| `emergency_translate.py` | 紧急单条翻译 | ✅ Migrate |
| `merge_shards.py` | 合并分片输出 | ✅ Migrate |
| `preprocess_csv.py` | CSV 预处理 | ✅ Migrate |
| `fill_missing_rows.py` | 补全缺失行 | ✅ Migrate |
| `fix_csv_header.py` | CSV 表头修复 | ✅ Migrate |
| `translate_refresh.py` | 翻译刷新更新 | ✅ Migrate |

---

## 🟢 Utils (工具) - 10 scripts

通用工具库，被 core 脚本依赖。

| Script | Purpose | Status |
|--------|---------|--------|
| `lib_text.py` | 文本处理库 (标点、格式化) | ✅ Migrate |
| `batch_utils.py` | 批处理工具函数 | ✅ Migrate |
| `metrics_aggregator.py` | 指标聚合分析 | ✅ Migrate |
| `progress_reporter.py` | 进度报告生成 | ✅ Migrate |
| `cost_monitor.py` | 成本监控 | ✅ Migrate |
| `cost_snapshot.py` | 成本快照记录 | ✅ Migrate |
| `llm_ping.py` | LLM 连通性测试 | ✅ Migrate |
| `consolidate_full_results_v2.py` | 结果合并 v2 | ✅ Migrate |
| `finalize_stress_report.py` | 压力测试报告生成 | ✅ Migrate |
| `apiyi_usage_client.py` | API 用量客户端 | ✅ Migrate |

---

## 🟡 Debug (调试) - 10 scripts

调试诊断工具，用于排查问题。

| Script | Purpose | Status |
|--------|---------|--------|
| `debug_llm_format.py` | LLM 输出格式调试 | ✅ Migrate |
| `debug_translation.py` | 翻译过程调试 | ✅ Migrate |
| `debug_auth.py` | 认证调试 | ✅ Migrate |
| `debug_destructive_failures.py` | 破坏性测试失败分析 | ✅ Migrate |
| `debug_v4_traces.py` | V4 追踪调试 | ✅ Migrate |
| `diagnose_direct_api.py` | 直连 API 诊断 | ✅ Migrate |
| `diagnose_sequential_batch.py` | 顺序批处理诊断 | ✅ Migrate |
| `diagnose_single_call.py` | 单调用诊断 | ✅ Migrate |
| `diagnose_sonnet_retest.py` | Sonnet 重测诊断 | ✅ Migrate |
| `trace_diagnostic.py` | 追踪日志诊断 | ✅ Migrate |

---

## 🟠 Testing (测试) - 18 scripts

测试脚本和验收工具。

### Python Tests
| Script | Purpose | Status |
|--------|---------|--------|
| `alpha_test_runner.py` | Alpha 测试运行器 | ✅ Migrate |
| `smoke_verify.py` | 冒烟测试验证 | ✅ Migrate |
| `test_router_check.py` | 路由检查测试 | ✅ Migrate |
| `test_step2_embedding.py` | Step2 嵌入测试 | ✅ Migrate |
| `test_step3_glossary.py` | Step3 术语表测试 | ✅ Migrate |
| `test_step4_semantic.py` | Step4 语义测试 | ✅ Migrate |
| `acceptance_p8_helper.py` | P8 验收辅助 | ✅ Migrate |
| `verify_3k_test.py` | 3K 测试验证 | ✅ Migrate |
| `create_part1_checkpoint.py` | 第一部分检查点创建 | ✅ Migrate |
| `rebuild_checkpoint.py` | 检查点重建 | ✅ Migrate |
| `repair_checkpoint_gaps.py` | 检查点间隙修复 | ✅ Migrate |

### Shell Tests
| Script | Purpose | Status |
|--------|---------|--------|
| `test_step1_env.sh` | Step1 环境测试 | ✅ Migrate |
| `acceptance_stress_run.sh` | 压力测试运行 | ✅ Migrate |
| `acceptance_stress_resume.sh` | 压力测试恢复 | ✅ Migrate |
| `acceptance_stress_resume_fix.sh` | 压力测试恢复修复 | ✅ Migrate |
| `acceptance_stress_phase3.sh` | 压力测试 Phase3 | ✅ Migrate |
| `acceptance_stress_final.sh` | 压力测试最终 | ✅ Migrate |
| `stress_test_3k_run.sh` | 3K 压力测试运行 | ✅ Migrate |

---

## 🔴 Deprecated (废弃/临时) - 10 scripts

废弃版本或临时脚本，保留但不推荐使用。

| Script | Purpose | Status |
|--------|---------|--------|
| `run_destructive_batch_v1.py` | 破坏性批处理 v1 (废弃) | ⚠️ Deprecate |
| `run_destructive_batch_v2.py` | 破坏性批处理 v2 (废弃) | ⚠️ Deprecate |
| `run_destructive_batch_v3.py` | 破坏性批处理 v3 (废弃) | ⚠️ Deprecate |
| `temp_check_lock.py` | 临时锁检查 | ⚠️ Deprecate |
| `temp_ckpt_check.py` | 临时检查点检查 | ⚠️ Deprecate |
| `prepare_destructive_assets.py` | 破坏性资源准备 (旧) | ⚠️ Deprecate |
| `prepare_long_text_assets_v1.py` | 长文本资源准备 v1 | ⚠️ Deprecate |
| `fix_progress_logs.py` | 进度日志修复 (一次性) | ⚠️ Deprecate |
| `combine_repair_tasks.py` | 修复任务合并 (已合并) | ⚠️ Deprecate |
| `merge_repair_outputs.py` | 修复输出合并 (已合并) | ⚠️ Deprecate |

---

## 📦 Uncategorized (需手动分类) - 31 scripts

需要进一步审查分类的脚本。

### Glossary 相关 (10个) - 可能部分进 core
| Script | Purpose | Suggested |
|--------|---------|-----------|
| `glossary_apply_patch.py` | 应用术语表补丁 | utils |
| `glossary_apply_review.py` | 应用术语表评审 | utils |
| `glossary_auto_approve.py` | 术语表自动批准 | utils |
| `glossary_autopromote.py` | 术语表自动提升 | utils |
| `glossary_compile.py` | 术语表编译 | utils |
| `glossary_delta.py` | 术语表差异 | utils |
| `glossary_make_review_queue.py` | 术语表评审队列 | utils |
| `glossary_review_llm.py` | 术语表 LLM 评审 | core |
| `glossary_vectorstore.py` | 术语表向量存储 | utils |

### Gate 相关 (10个) - 可能部分进 core
| Script | Purpose | Suggested |
|--------|---------|-----------|
| `build_gate_v4_data.py` | 构建 V4 Gate 数据 | utils |
| `build_mixed_gate.py` | 构建混合 Gate | utils |
| `build_reality_gate.py` | 构建真实 Gate | utils |
| `build_validation_set.py` | 构建验证集 | utils |
| `run_dual_gates.py` | 运行双 Gate | core |
| `run_empty_gate.py` | 运行 Empty Gate | core |
| `run_empty_gate_v3_mixed.py` | 运行 V3 Mixed Gate | core |
| `run_empty_gate_v4.py` | 运行 V4 Gate | core |
| `run_long_text_gate_v1.py` | 运行长文本 Gate | core |
| `run_validation.py` | 运行验证 | core |

### Style Guide 相关 (4个)
| Script | Purpose | Suggested |
|--------|---------|-----------|
| `style_guide_apply.py` | 应用风格指南 | core |
| `style_guide_generate.py` | 生成风格指南 | core |
| `style_guide_score.py` | 风格评分 | utils |
| `style_sync_check.py` | 风格同步检查 | testing |

### 分析/报告 (5个)
| Script | Purpose | Suggested |
|--------|---------|-----------|
| `analyze_lengths.py` | 长度分析 | utils |
| `analyze_part1_metrics.py` | Part1 指标分析 | utils |
| `extract_claude_failures.py` | 提取失败案例 | debug |
| `extract_terms.py` | 术语提取 | utils |
| `diff_translation.py` | 翻译差异对比 | debug |

### 其他 (2个)
| Script | Purpose | Suggested |
|--------|---------|-----------|
| `dev_prompt_improver.py` | 开发提示优化 | deprecated |
| `llm_prompt_inventory.py` | LLM 提示清单 | utils |

---

## 🚀 Migration Summary

| Category | Migrated | Files |
|----------|----------|-------|
| core | 12 + 1 init | 13 files |
| utils | 11 + 1 init | 12 files |
| debug | 10 + 1 init | 11 files |
| testing | 18 + 1 init | 19 files |
| deprecated | 11 + 1 init | 12 files |
| root | cli + init | 2 files |
| **Total v1.4.0** | - | **69 files** |
| **Remaining v1.3.0** | - | **32 files** |

### ✅ Completed
1. Analyzed 101 scripts from `v1.3.0/scripts/`
2. Created `v1.4.0/scripts/` with organized structure
3. Migrated 67 scripts to appropriate categories
4. Created `cli.py` as unified CLI entry
5. Created `__init__.py` for package structure
6. Generated `scripts-inventory.md` documentation

### 📋 Usage
```bash
# CLI usage
cd /root/.openclaw/workspace/projects/game-localization-mvr/skill/v1.4.0
python -m scripts.cli translate -i data/input.csv -o data/output.csv
python -m scripts.cli qa -i data/translated.csv -r qa_report.json
python -m scripts.cli repair -i data/input.csv --tasks tasks.jsonl -o data/output.csv
python -m scripts.cli glossary -i data/terms.csv -o data/glossary.yaml
```

### 📝 Notes
1. **v1.3.0** scripts remain untouched (backward compatibility)
2. **v1.4.0** is the new organized structure
3. 32 scripts remain in v1.3.0 for manual review (gate, style, glossary ops)
4. CLI provides unified interface to core functions
