# Reproducible Baseline Runbook

This document describes how to run the established baseline workflows for the localization pipeline. These workflows are the "source of truth" for quality and stability.

## 1. Dual Gate (Hard + Soft)

Runs both Hard Gate (syntax/placeholders) and Soft Gate (LLM-based quality check).

**Command:**

```bash
python scripts/run_dual_gates.py \
  --input data/test_input.csv \
  --output data/dual_gate_output \
  --api-key-path data/attachment/api_key.txt
```

**Note:** Point `--api-key-path` at your local secret file. The retained default path is
`data/attachment/api_key.txt`, which stays gitignored.

## 2. Empty Gate V3 (Mixed Mode)

Runs the "Empty Gate" test which verifies system behavior on empty or minimal inputs, preserving the "short-circuit" check logic.

**Command:**

```bash
python scripts/run_empty_gate_v3_mixed.py \
  --rows 50 \
  --model gpt-4.1-mini \
  --input data/input_large.csv
```

**Key Behavior:**

- Forces LLM calls even if inputs seem empty (to test robustness).
- Disables short-circuit optimization for this specific test run.

## 3. Validation Runner (N-Row)

Runs the retained validation baseline used for deterministic regression checks.

### Step 1: Build the validation set

```bash
python scripts/build_validation_set.py \
  --source data/draft.csv \
  --rows 100 \
  --seed 42 \
  --output-dir data
```

### Step 2: Run validation

Use explicit paths in the runbook even though the script still has convenience defaults.

```bash
# Run 100-row validation
python scripts/run_validation.py \
  --model gpt-5.2 \
  --rows 100 \
  --input data/validation_100_v1.csv \
  --output-dir reports \
  --report-dir reports \
  --api-key-path data/attachment/api_key.txt

# Run 1000-row validation
python scripts/run_validation.py \
  --model gpt-5.2 \
  --rows 1000 \
  --input data/validation_1000_v1.csv \
  --output-dir reports \
  --report-dir reports \
  --api-key-path data/attachment/api_key.txt
```

### Validation I/O Contract

- `build_validation_set.py` input must contain `string_id` and at least one of `source_zh` or `tokenized_zh`.
- `build_validation_set.py` writes `data/validation_<rows>_v1.csv` plus `data/validation_<rows>_v1.meta.json`.
- The metadata file records `source_sha256`, `input_columns`, `output_columns`, `required_columns`, `source_text_columns`, and `stratum_distribution`.
- `run_validation.py` expects the validation CSV row count to exactly match `--rows`; missing or mismatched row counts are treated as contract failures.
- `run_validation.py` writes `reports/validation_<rows>_output_<model>.csv` with columns `string_id,source_zh,target_ru,status`.
- `run_validation.py` writes `reports/validation_<rows>_<model>_<timestamp>.json` with the report version, input/output hashes, column lists, and metrics payload.
- `run_validation.py` accepts explicit `--input`, `--output-dir`, `--report-dir`, and `--api-key-path`; the runbook should prefer those explicit flags over implicit defaults.

**Artifacts:**

- Validation outputs are saved to `reports/validation_*`.
- These outputs are **gitignored** to keep the repo clean.
