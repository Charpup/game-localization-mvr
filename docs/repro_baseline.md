# Reproducible Baseline Runbook

This document describes how to run the established baseline workflows for the localization pipeline. These workflows are the "source of truth" for quality and stability.

## 1. Dual Gate (Hard + Soft)

Runs both Hard Gate (syntax/placeholders) and Soft Gate (LLM-based quality check).

**Command:**

```bash
python scripts/run_dual_gates.py \
  --input data/test_input.csv \
  --output data/dual_gate_output \
  --api-key-path config/api_key.txt
```

**Note:** Ensure `config/api_key.txt` exists (it is gitignored).

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

Runs a configurable N-row validation test to benchmark performance and quality.

**Command:**

```bash
# Run 100-row validation
python scripts/run_validation.py --rows 100 --model gpt-5.2

# Run 1000-row validation
python scripts/run_validation.py --rows 1000 --model gpt-5.2
```

**Artifacts:**

- Validation outputs are saved to `reports/validation_*`.
- These outputs are **gitignored** to keep the repo clean.
