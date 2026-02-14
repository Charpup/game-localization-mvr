# Performance Baseline Report

**Project:** game-localization-mvr  
**Report Generated:** 2026-02-14  
**Baseline Version:** 2.1  

---

## Executive Summary

This report documents the performance characteristics of the game localization MVR pipeline, establishing baselines for each module and identifying optimization opportunities.

### Current Performance Overview

| Module | 1k Rows | 10k Rows | 30k Rows | Status |
|--------|---------|----------|----------|--------|
| normalize_guard | TBD | TBD | TBD | ⏳ Pending |
| translate_llm | TBD | TBD | N/A | ⏳ Pending |
| qa_hard | TBD | TBD | TBD | ⏳ Pending |
| rehydrate_export | TBD | TBD | TBD | ⏳ Pending |

*Note: Run `python tests/performance/benchmark.py --all` to generate actual metrics.*

---

## Test Environment

| Component | Specification |
|-----------|---------------|
| Python Version | 3.11+ |
| OS | Linux (OpenCloudOS) |
| CPU | VM Instance |
| Memory | Available per VM |
| Test Framework | pytest with custom timer |
| Measurement Method | wall-clock time + psutil memory |

---

## Module Performance Characteristics

### 1. normalize_guard (Placeholder Freezing)

**Purpose:** Freeze placeholders and tags into tokens, generate draft.csv and placeholder_map.json

**Key Operations:**
- CSV parsing and validation
- Regex-based placeholder detection
- Chinese text segmentation (jieba)
- Token generation and mapping
- Balance validation

**Expected Performance:**
- 1k rows: < 5 seconds
- 10k rows: < 30 seconds  
- 30k rows: < 90 seconds

**Bottlenecks Identified:**
1. **Chinese Segmentation (jieba)** - First call loads dictionary (one-time cost)
2. **Regex Compilation** - Patterns compiled per-row (opportunity: pre-compile)
3. **CSV I/O** - Large files cause memory pressure

**Optimization Opportunities:**
- [ ] Pre-compile regex patterns at class initialization
- [ ] Implement streaming CSV processing for very large files
- [ ] Cache jieba dictionary load
- [ ] Use `re.finditer()` instead of `re.sub()` with callback for better performance

---

### 2. translate_llm (LLM Translation)

**Purpose:** Translate tokenized Chinese strings using LLM with caching support

**Key Operations:**
- Cache lookup/insertion (SQLite)
- Batch preparation and API calls
- Token validation
- Checkpoint management

**Expected Performance (with Mock LLM):**
- 1k rows: < 10 seconds
- 10k rows: < 60 seconds

**Important Notes:**
- **Actual LLM performance depends on API latency and rate limits**
- With real LLM (Claude/Kimi): expect 100-1000x slower
- Cache hit rate significantly impacts performance

**Bottlenecks Identified:**
1. **API Latency** - Network round-trip dominates
2. **Rate Limiting** - Concurrent request throttling
3. **JSON Parsing** - Response parsing overhead

**Optimization Opportunities:**
- [x] Response caching (already implemented in v6.1)
- [ ] Parallel batch processing
- [ ] Connection pooling
- [ ] Compression for large prompts

---

### 3. qa_hard (Hard Rule Validation)

**Purpose:** Validate translated text with hard rules (token matching, tag balance, forbidden patterns)

**Key Operations:**
- Token extraction (regex)
- Tag balance validation
- Forbidden pattern matching
- Length overflow detection

**Expected Performance:**
- 1k rows: < 2 seconds
- 10k rows: < 10 seconds
- 30k rows: < 30 seconds

**Bottlenecks Identified:**
1. **Regex Matching** - Multiple patterns per row
2. **Error Collection** - List append overhead (limited to 2000 errors)

**Optimization Opportunities:**
- [ ] Compile all forbidden patterns once
- [ ] Use `re.finditer()` for lazy evaluation
- [ ] Consider Cython for hot regex paths

---

### 4. rehydrate_export (Token Restoration)

**Purpose:** Restore tokens back to original placeholders, apply punctuation normalization

**Key Operations:**
- Token extraction and replacement
- Punctuation mapping
- CSV writing

**Expected Performance:**
- 1k rows: < 1 second
- 10k rows: < 5 seconds
- 30k rows: < 15 seconds

**Bottlenecks Identified:**
1. **String Replacement** - Multiple `.replace()` calls
2. **Punctuation Processing** - Character-by-character mapping

**Optimization Opportunities:**
- [ ] Use `str.translate()` for punctuation mapping
- [ ] Batch token replacement using regex
- [ ] Streaming write for large outputs

---

## Performance Regression Thresholds

### Critical Thresholds (Must Not Exceed)

| Module | 1k | 10k | 30k | Action if Exceeded |
|--------|-----|------|------|-------------------|
| normalize_guard | 10s | 60s | 180s | **BLOCK RELEASE** |
| qa_hard | 5s | 20s | 60s | **BLOCK RELEASE** |
| rehydrate_export | 2s | 10s | 30s | **BLOCK RELEASE** |

### Warning Thresholds (Review Required)

| Module | 1k | 10k | 30k | Action if Exceeded |
|--------|-----|------|------|-------------------|
| normalize_guard | 5s | 30s | 90s | Create ticket |
| qa_hard | 2s | 10s | 30s | Create ticket |
| rehydrate_export | 1s | 5s | 15s | Create ticket |

---

## Benchmark Results (Sample)

### Running Benchmarks

```bash
# Run all benchmarks
python tests/performance/benchmark.py --all

# Run specific module
python tests/performance/benchmark.py --module normalize_guard

# Save results
python tests/performance/benchmark.py --all --output results.json

# Compare with previous
python tests/performance/benchmark.py --all --compare previous.json
```

### Interpreting Results

Example output:

```
NORMALIZE_GUARD:
----------------------------------------------------------------------------------
      Size   Time (s)    Memory (MB)     Throughput     Errors
----------------------------------------------------------------------------------
     1,000        2.5          45.20       400.00x          0
    10,000       18.3         120.50       546.45x          0
    30,000       65.2         280.30       460.12x          0
```

**Key Metrics:**
- **Throughput (rows/sec):** Higher is better. Should remain relatively constant across sizes.
- **Memory Growth:** Should be sub-linear. Linear growth indicates streaming issues.
- **Error Count:** Should be 0 for valid test data.

---

## Optimization Roadmap

### Phase 1: Quick Wins (Current Sprint)
1. Pre-compile regex patterns in normalize_guard
2. Use `str.translate()` for punctuation in rehydrate_export
3. Add progress bars for long-running operations

### Phase 2: Architecture Improvements (Next Sprint)
1. Implement streaming CSV processing
2. Add parallel batch processing for translate_llm
3. Optimize jieba dictionary loading

### Phase 3: Advanced Optimizations (Future)
1. Consider Rust/Cython for hot paths
2. Implement connection pooling for LLM API
3. Add memory-mapped file I/O

---

## CI/CD Integration

### Automated Performance Gates

Add to `.github/workflows/ci.yml`:

```yaml
- name: Performance Baseline Tests
  run: |
    python tests/performance/benchmark.py --all --output baseline.json
    
- name: Check Performance Regressions
  run: |
    python tests/performance/check_regressions.py baseline.json expected.json
```

### Pre-commit Hooks

```yaml
# .pre-commit-config.yaml
repos:
  - repo: local
    hooks:
      - id: performance-check
        name: Quick Performance Check
        entry: python tests/performance/benchmark.py --module qa_hard --sizes 1000
        language: python
        pass_filenames: false
```

---

## Appendix: Test Data Characteristics

The benchmark test data includes:

- **Simple strings:** "医术秘传", "健壮秘传"
- **With placeholders:** "获得{0}金币", "等级提升\\n新等级: {level}"
- **With tags:** "<color=#FF0000>{name}</color>"
- **Mixed content:** "使用<size=14>{skill_name}</size>造成%d点伤害"

This mix ensures benchmarks represent real-world workload characteristics.

---

## Revision History

| Version | Date | Changes |
|---------|------|---------|
| 2.1 | 2026-02-14 | Initial baseline documentation |

---

*For questions or issues with performance benchmarks, contact the development team.*
