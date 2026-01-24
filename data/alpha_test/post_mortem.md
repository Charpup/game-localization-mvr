# Post-Mortem: Omni Test Part 3 Failure

**Date**: 2026-01-20
**Incident**: High Escalation Rate (80% -> 70%) in Batch Translation
**Component**: `translate_llm.py` (Batch Runtime v5.0)

---

## 1. Timeline

- **Start**: Resumed Part 3 from row 18,821.
- **T+5m**: Validated Checkpoint logic (OK), Docker Env (OK).
- **T+15m**: Observed high throughput but extremely high escalation rate (~80%) in `translated_r1_part3.csv`.
- **T+30m**: Paused execution. Diagnosed potential "Thinking" model parser incompatibility.
- **T+1h**: Implemented Parser fix (robust JSON extraction) and Observability fix (Trace output logging).
- **T+1.5h**: Conducted Alpha Test (20 rows) with Default Model (`gpt-4.1`) and fixed Parser.
- **Result**: Escalation Rate 70%. Failure persisted.

---

## 2. Root Cause Analysis (RCA)

### Hypotheses & Validation

| Hypothesis | Status | Evidence |
|------------|--------|----------|
| **H1: Parser Incompatibility** | ❌ Rejected | Updated parser handles lenient JSON/Markdown/Thinking tags. Alpha Test trace shows clean JSON objects being returned, yet missing items persist. |
| **H2: Model "Thinking" Output** | ❌ Rejected | Alpha Test switched back to standard `gpt-4.1` (non-thinking), failure metrics identical. |
| **H3: Model Batch Compliance** | ✅ CONFIRMED | Trace logs show `gpt-4.1` consistently returning a **single JSON object** for a request containing 10 items. e.g., Input has IDs 1-10, Output has only ID 1. |

### Technical Detail

The core failure is **Model Alignment with Batch Instructions**.
Despite System Prompt explicitly demanding:
> "You MUST return a JSON ARRAY... If input has 10 items, output MUST have 10 items."

The model `gpt-4.1`:

1. Ignores the array requirement often (returning a bare object).
2. **Severely hallucinates completion**: It processes the first item and stops, ignoring the rest of the user prompt array.

This behaves like a model with low context adherence or aggressive "lazy" optimization.

---

## 3. Impact Assessment

- **Data Safety**: No data loss. Source guarded by `normalized.csv`. Part 1 results locked.
- **Timeline**: Part 3 delivery delayed by ~1 day.
- **Tech Stack**: The current "Batch Mode" architecture is proven viable **only if** the underlying model supports it. `gpt-4.1` on this provider endpoint is **unfit** for Batch Size 10.

---

## 4. Action Items & Lessons

1. **Immediate Fix**:
    - **Disable Batching** for `gpt-4.1` (Set Batch Size = 1).
    - **OR Change Model**: Switch to `claude-3-5-sonnet` or `gpt-4-turbo` for Batching.
2. **Process Improvement**:
    - **Small Scale First**: Future "Omni Tests" must pass a 50-row "Sanity Check" before running full 12k rows.
    - **Observability First**: Never run a large batch without `output` logging enabled in traces. The "Blind Flight" listed in Part 3 Plan was a critical oversight.

---

*End of Post-Mortem*
