# Game Localization MVR (Minimum Viable Rules) v2.1

A robust, automated workflow system for game localization with strict validation, AI translation/repair, glossary management, and multi-format export.

> **Core Principle**: Input rows == Output rows ALWAYS. No silent data loss.

---

## 🤖 For AI Coding Agents

**Quick Commands for Agents:**

```bash
# 1. Verify LLM connectivity (MUST run first)
python scripts/llm_ping.py

# 2. Validate workflow configuration (dry-run)
python scripts/translate_llm.py --input input.csv --output output.csv --style workflow/style_guide.md --glossary glossary/compiled.yaml --style-profile workflow/style_profile.generated.yaml --dry-run

# 3. Run E2E test
python scripts/test_e2e_workflow.py
```

**Environment Variables (REQUIRED):**

```bash
LLM_BASE_URL=https://api.example.com/v1
LLM_API_KEY=sk-your-key
LLM_MODEL=gpt-4.1-mini
LLM_TRACE_PATH=data/llm_trace.jsonl
```

**Key Rules for Agents:**

1. **Never hardcode API keys** - Use environment variables only
2. **Run `llm_ping.py` first** - Fail-fast if LLM unavailable
3. **Check WORKSPACE_RULES.md** - See `docs/WORKSPACE_RULES.md` for hard constraints
4. **Row preservation is P0** - Empty source rows must be preserved with `status=skipped_empty`
5. **Glossary is mandatory** - `glossary/compiled.yaml` must exist before translation

---

## 🔄 Handoff

Use this section when a new machine or a new agent needs to continue the current UI/operator roadmap without local context from the previous workstation.

**Roadmap status**

- Phase 5 `frontend_runtime_shell`: implemented and merged
- Phase 6 `operator_workspace_dashboard`: implemented and merged
- Latest local follow-up scope: dashboard redesign, Chinese UI toggle, manual UAT seed/helper, and migration closeout docs

**Recommended starting point**

```bash
git clone https://github.com/Charpup/game-localization-mvr.git
cd game-localization-mvr
git checkout main
```

- Start from a fresh `main`
- Create a new `codex/*` branch for any follow-up work instead of reviving old merged feature branches
- Treat `task_plan.md`, `progress.md`, and the latest `docs/project_lifecycle/run_records/...` chain as the continuity trail

**UI/operator runtime entrypoints**

```bash
python scripts/seed_phase6_manual_uat.py
python scripts/operator_ui_server.py --host 127.0.0.1 --port 8765
```

- Manual UI entry: `http://127.0.0.1:8765/`
- Seeded manual UAT fixtures create:
  - `phase6_manual_uat_derived`
  - `phase6_manual_uat_persisted`

**Required preflight**

```bash
python scripts/llm_ping.py
```

- Required env:
  - `LLM_BASE_URL`
  - `LLM_API_KEY`
  - `LLM_MODEL`
- Do not start smoke runs or UI live-launch validation until `llm_ping.py` passes

**Current truth sources**

- Runtime truth:
  - `run_manifest.json`
  - `smoke_verify_<run_id>.json`
  - `smoke_issues.json`
- Operator/workspace truth:
  - `data/operator_cards/<run_id>/operator_cards.jsonl`
  - `data/operator_reports/<run_id>/operator_summary.json`
- Governance continuity:
  - `docs/project_lifecycle/run_records/...`
  - `task_plan.md`
  - `progress.md`

**Recommended next step**

- Finish or re-run human UI acceptance on the latest dashboard build
- Address any follow-up UX/runtime defects found in manual UAT
- Then open the next roadmap scope from fresh `main`

---

## 🚀 Pipeline Overview

```
Input CSV → Normalize → Translate → QA_Hard → Repair → Export
                ↓
            Glossary (required)
```

| Step | Script | Purpose | Blocking? |
|------|--------|---------|-----------|
| 0 | `llm_ping.py` | 🔌 LLM connectivity check | YES |
| 1 | `normalize_guard.py` | 🧊 Freeze placeholders → tokens | YES |
| 2-4 | `extract_terms.py` → `glossary_compile.py` | 📖 Build glossary | YES |
| 5 | `translate_llm.py` | 🤖 AI Translation | YES |
| 6 | `qa_hard.py` | 🛡️ Validate tokens/patterns | YES |
| 7 | `repair_loop.py` | 🔧 Auto-repair hard errors | - |
| 8 | `soft_qa_llm.py` | 🧠 Quality review | - |
| 10 | `rehydrate_export.py` | 💧 Restore tokens → placeholders | YES |

---

## 📁 Project Structure

```
loc-mvr/
├── config/
│   ├── llm_routing.yaml    # Model routing per step
│   └── pricing.yaml        # Cost calculation
├── glossary/
│   ├── compiled.yaml       # Active glossary (generated)
│   └── generic_terms_zh.txt # Blacklist for extraction
├── scripts/
│   ├── llm_ping.py         # ★ Run first - connectivity check
│   ├── normalize_guard.py  # Step 1: Placeholder freezing
│   ├── translate_llm.py    # Step 5: Translation
│   ├── qa_hard.py          # Step 6: Hard validation
│   ├── repair_loop.py      # Step 7: Auto-repair
│   └── runtime_adapter.py  # LLM client with routing
├── workflow/
│   ├── style_guide.md      # Translation style rules
│   ├── forbidden_patterns.txt
│   └── placeholder_schema.yaml
└── docs/
    └── WORKSPACE_RULES.md  # ★ Hard constraints for agents
```

---

## 🔧 Quick Start (Human)

### 1. Setup

```bash
git clone https://github.com/Charpup/game-localization-mvr.git
cd game-localization-mvr
pip install pyyaml requests numpy pandas jieba
```

### 2. Configure LLM (推荐持久化)

```powershell
# Windows PowerShell
$env:LLM_BASE_URL="https://api.apiyi.com/v1"
$env:LLM_API_KEY="sk-your-key"
$env:LLM_MODEL="gpt-4.1-mini"
```

也可在本地持久化文件中配置（优先于环境变量自动读取）：
```text
# 在 main_worktree/.llm_credentials 创建
LLM_BASE_URL=https://api.apiyi.com/v1
LLM_API_KEY=sk-your-key
```

当前加载顺序：`LLM_API_KEY_FILE` -> `./.llm_credentials`/`./.llm_env`/`./config/llm_credentials.env`/`~/.game-localization-mvr/.llm_credentials` -> `LLM_API_KEY`

### 4. Dependency + Environment Quick Check (before every smoke run)

```bash
python - <<'PY'
import os
import importlib

for pkg in ["requests", "numpy", "yaml", "pandas"]:
    try:
        importlib.import_module(pkg)
        print(f"[OK] {pkg}")
    except Exception:
        print(f"[MISSING] {pkg}")

for key in ["LLM_BASE_URL", "LLM_API_KEY", "LLM_MODEL"]:
    print(f"{key}={'SET' if os.getenv(key) else 'MISSING'}")
PY
```

If any dependency shows MISSING or env variable shows MISSING, do not start smoke run yet.

PowerShell 快速检查：

```powershell
$missing = @()
foreach ($m in @("requests","numpy","yaml","pandas","jieba")) {
  try {
    python -c "import importlib.util; print(bool(importlib.util.find_spec('$m')))"
    Write-Host "[OK] $m"
  } catch {
    $missing += $m
    Write-Host "[MISSING] $m"
  }
}
Write-Host "LLM_BASE_URL=$([bool]$env:LLM_BASE_URL)"
Write-Host "LLM_API_KEY=$([bool]$env:LLM_API_KEY)"
Write-Host "LLM_MODEL=$([bool]$env:LLM_MODEL)"
```

### 3. Run Pipeline

```bash
# Bootstrap tracked style assets once per clean worktree
python scripts/style_guide_bootstrap.py --dry-run

# Verify LLM
python scripts/llm_ping.py

# Normalize → Translate → QA → Export
python scripts/normalize_guard.py input.csv normalized.csv map.json workflow/placeholder_schema.yaml
python scripts/translate_llm.py --input normalized.csv --output translated.csv --style workflow/style_guide.md --glossary glossary/compiled.yaml --style-profile workflow/style_profile.generated.yaml
python scripts/qa_hard.py translated.csv qa_report.json map.json
python scripts/rehydrate_export.py translated.csv map.json final.csv
```

### 3.1 Smoke Pipeline (Manifest + Issue Record)

```bash
# Full smoke pass with manifest output + issue recording
python scripts/run_smoke_pipeline.py --input "D:\\Dev_Env\\loc-mvr 测试文档\\test_input_200-row.csv" --target-lang en-US
# 可选：仅做预检
python scripts/run_smoke_pipeline.py --input "D:\\Dev_Env\\loc-mvr 测试文档\\test_input_200-row.csv" --target-lang en-US --verify-mode preflight
```

This command:
- auto-bootstraps `workflow/style_profile.generated.yaml` if the clean worktree does not have one yet
- runs `llm_ping -> normalize_guard -> translate_llm -> qa_hard -> rehydrate_export`
- generates a run manifest: `data/smoke_run_<timestamp>/run_manifest.json`
- runs `smoke_verify --manifest ...`
- records issues to `reports/smoke_issues_<run-id>.json` and `.jsonl`
- emits `manifest.stage_artifacts` with:
  - `connectivity_log`
  - `normalize_log`
  - `translate_log`
  - `qa_hard_report`
  - `final_csv`
  - `smoke_verify_log`
- `verify_mode` supports `preflight|full`，默认 `full`（含行数/QA 统计）

建议每次冒烟固定检查以下产物：
- `D:\Dev_Env\GPT_Codex_Workspace\game-localization-mvr\main_worktree\data\smoke_runs\<run>\run_manifest.json`
- `D:\Dev_Env\GPT_Codex_Workspace\game-localization-mvr\main_worktree\reports\smoke_issues_<run_id>.json`
- `D:\Dev_Env\GPT_Codex_Workspace\game-localization-mvr\main_worktree\reports\smoke_verify_<run_id>.json`

---

## ⚡ Key Features

- **Row Preservation**: Empty rows kept with `status=skipped_empty`
- **Drift Guard**: Refresh stage blocks non-placeholder text changes
- **Progress Reporting**: `--progress_every N` for translation progress
- **Router-based Models**: Configure per-step models in `llm_routing.yaml`
- **LLM Tracing**: All calls logged to `LLM_TRACE_PATH` for billing

---

## 📋 Testing

```bash
# Unit tests
python scripts/test_normalize.py
python scripts/test_qa_hard.py
python scripts/test_rehydrate.py

# E2E test (small dataset)
python scripts/test_e2e_workflow.py

# Dry-run validation
python scripts/translate_llm.py --input input.csv --output out.csv --style workflow/style_guide.md --glossary glossary/compiled.yaml --style-profile workflow/style_profile.generated.yaml --dry-run
```

---

## 📄 License

MIT License. Built for game localization automation.

---

## 🔗 Links

- **Workspace Rules**: [docs/WORKSPACE_RULES.md](docs/WORKSPACE_RULES.md)
- **Demo Walkthrough**: [docs/demo.md](docs/demo.md)
