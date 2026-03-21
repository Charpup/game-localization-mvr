# Localization Pipeline v2.1 - Full Workflow (with Style Contract Bootstrap)

## Prerequisites

- Python 3.7+ with PyYAML
- LLM environment variables: `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL`
- `glossary/compiled.yaml` (or will be created in Step 3)

## Pipeline Steps

### Phase 1: Preparation

0. **Style Guide Bootstrap**（项目启动）

```bash
python scripts/style_guide_bootstrap.py \
  --questionnaire workflow/style_guide_questionnaire.md \
  --guide-output workflow/style_guide.generated.md \
  --profile-output data/style_profile.yaml
```

0.5 **Style Guide Sync Check**（硬门禁）

```bash
python scripts/style_sync_check.py
```

> 门禁失败（退出码非 0）时停止后续翻译链路。未通过前先补齐：
> - `workflow/style_guide.md`
> - `workflow/style_guide.generated.md`
> - `data/style_profile.yaml`
> - `style_sync_check` 输出中的 `suggested_actions`

> Step0 产物：`run_manifest_plc_run_d_prepare.json` 与 `run_issue_plc_run_d_full.md` 中需记录 style_sync_check 的阻断与建议。

1 **Normalize** - 冻结占位符并生成 draft.csv

```bash
python scripts/normalize_ingest.py --input data/input.csv --output data/source_raw.csv
python scripts/normalize_tagger.py --input data/source_raw.csv --output data/normalized.csv
python scripts/normalize_guard.py data/normalized.csv data/draft.csv data/placeholder_map.json workflow/placeholder_schema.yaml
```

1.1 **D Step1 基线/漂移 + 术语风格一致性门禁**

```bash
python scripts/baseline_drift_control.py --run-manifest-dir docs/project_lifecycle/run_records/2026-03/2026-03-21 \
  plc_run_d_full \
  --baseline-manifest data/baselines/plc_run_d_prepare/plc_run_d_prepare \
  --source test_30_repaired.csv \
  --rows 10 \
  --seed 42 \
  --max-row-churn-ratio 0.05
```

```bash
python scripts/soft_qa_llm.py data/translated.csv \
  workflow/style_guide.md \
  data/glossary.yaml \
  workflow/soft_qa_rubric.yaml \
  --style-profile data/style_profile.yaml \
  --dry-run
```

> Step1 任一命令失败时，后续翻译修复与导出阶段不得静默降级，必须先修复漂移、术语冲突、风格冲突、长度超限或占位符问题。

1.2 **Extract Terms with Style Context**

```bash
python scripts/extract_terms.py data/draft.csv data/term_candidates.yaml \
  --mode segmented \
  --seg-backend pkuseg,thulac,lac,jieba,heuristic \
  --style-profile data/style_profile.yaml \
  --domain-hint "ui"
```

2. **Review Term Candidates**

手动审核 `data/term_candidates.yaml` 的 `critical/proposed/low_confidence`，按审批策略转为 glossary。

### Phase 2: Glossary and Translation

1. **Translate Glossary**（if needed）

```bash
python scripts/glossary_compile.py --approved data/glossary.yaml --language_pair zh-CN->ru-RU
```

2. **Translate**（加载 style contract）

```bash
python scripts/translate_llm.py --input data/draft.csv --output data/translated.csv \
  --style workflow/style_guide.md --glossary data/glossary.yaml \
  --style-profile data/style_profile.yaml --target-lang ru-RU
```

3. **QA Hard**

```bash
python scripts/qa_hard.py data/translated.csv data/placeholder_map.json workflow/placeholder_schema.yaml workflow/forbidden_patterns.txt data/qa_hard_report.json
```

4. **Repair Loop Hard**（如需）

```bash
python scripts/repair_loop.py \
  --input data/translated.csv \
  --tasks data/qa_hard_report.json \
  --output data/repaired.csv \
  --output-dir data/repair_reports/hard \
  --qa-type hard
```

### Phase 3: Soft QA and Repair

1. **Soft QA**

```bash
python scripts/soft_qa_llm.py data/translated.csv \
  workflow/style_guide.md \
  data/glossary.yaml \
  workflow/soft_qa_rubric.yaml \
  --style-profile data/style_profile.yaml
```

> 正式 Soft QA 与 Step1 `--dry-run` 使用相同 gate 配置：`rule_id=STEP1_TERM_STYLE_DRIFT`，`severity_threshold=major`，失败类型集合必须保持一致。

2. **Repair Loop Soft**（仅 major）

```bash
python scripts/repair_loop.py \
  --input data/translated.csv \
  --tasks data/repair_tasks.jsonl \
  --output data/repaired.csv \
  --output-dir data/repair_reports/soft \
  --qa-type soft
```

3. **QA Hard Recheck**

```bash
python scripts/qa_hard.py data/repaired.csv data/placeholder_map.json workflow/placeholder_schema.yaml workflow/forbidden_patterns.txt data/qa_recheck_report.json
```

### Phase 4: Export and Glossary Lifecycle

1. **Export** - 还原占位符

```bash
python scripts/rehydrate_export.py data/repaired.csv data/placeholder_map.json data/final.csv
```

2. **Glossary Autopromote**

```bash
python scripts/glossary_autopromote.py \
  --before data/translated.csv \
  --after data/repaired.csv \
  --style workflow/style_guide.md \
  --style-profile data/style_profile.yaml \
  --glossary data/glossary.yaml \
  --language_pair "zh-CN->ru-RU" \
  --scope "project_default"
```

3. **Review proposals & Compile**

- `python scripts/glossary_make_review_queue.py --proposals data/glossary_proposals.yaml --out_csv data/glossary_review_queue.csv`
- 用户编辑 `data/glossary_review_queue.csv`（approve/reject/edit）
- `python scripts/glossary_apply_review.py --review_csv data/glossary_review_queue.csv`
- `python scripts/glossary_compile.py --approved data/glossary.yaml --language_pair zh-CN->ru-RU`

## Loop Thresholds

| Loop | Max Attempts | On Exceed |
|---|---|---|
| Loop A (Hard Gate) | `HARD_LOOP_MAX=3` | Escalation |
| Loop B (Post-Soft) | `POST_SOFT_HARD_LOOP_MAX=2` | Escalation |

## Escalation Output

Failed items go to `data/escalations.csv` for manual handling.
