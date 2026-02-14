import pandas as pd
import json
import os

print("=" * 70)
print("Full Pipeline Smoke Test 验证报告 (14 步全覆盖)")
print("=" * 70)

stages = {
    "Stage 1 - Normalization": [
        "data/smoke_source_raw.csv",
        "data/smoke_normalized.csv",
        "data/smoke_draft.csv",
        "data/smoke_placeholder_map.json"
    ],
    "Stage 2 - Style Guide": [
        "workflow/style_guide.md"
    ],
    "Stage 3 - Glossary": [
        "data/smoke_term_candidates.yaml",
        "workflow/smoke_glossary_approved.yaml",
        "workflow/smoke_glossary_compiled.yaml"
    ],
    "Stage 4 - Translation": [
        "data/smoke_translated.csv"
    ],
    "Stage 5 - Hard QA": [
        "reports/smoke_qa_hard_report.json",
        "data/smoke_repaired_hard.csv"
    ],
    "Stage 6 - Soft QA": [
        "reports/smoke_qa_soft_report.json",
        "data/smoke_repaired_final.csv"
    ],
    "Stage 7 - Export": [
        "data/smoke_final_export.csv"
    ],
    "Stage 8 - Lifecycle": [
        "workflow/smoke_glossary_autopromoted.yaml",
        "workflow/smoke_glossary_new.yaml"
    ],
    "Stage 9 - Metrics": [
        "reports/smoke_metrics_report.md",
        "reports/smoke_metrics_report.json"
    ]
}

all_pass = True
for stage, files in stages.items():
    print(f"\n--- {stage} ---")
    stage_pass = True
    for f in files:
        exists = os.path.exists(f)
        status = "✅" if exists else "❌"
        print(f"  {status} {f}")
        if not exists:
            stage_pass = False
            all_pass = False
    print(f"  → {'PASS' if stage_pass else 'FAIL'}")

# Translation Stats
print("\n--- 翻译统计 ---")
final_file = "data/smoke_final_export.csv"
if os.path.exists(final_file):
    df = pd.read_csv(final_file)
    print(f"最终文件: {final_file}")
    print(f"总行数: {len(df)}")
    ru_cols = [c for c in df.columns if "ru" in c.lower() or "target" in c.lower() or "rehydrated" in c.lower()]
    if ru_cols:
        translated = df[ru_cols[0]].notna().sum()
        print(f"已翻译: {translated} ({translated/len(df)*100:.1f}%)")

# QA Stats
print("\n--- QA 统计 ---")
for qa_file in ["reports/smoke_qa_hard_report.json", "reports/smoke_qa_soft_report.json"]:
    if os.path.exists(qa_file):
        with open(qa_file) as f:
            qa = json.load(f)
        name = "Hard QA" if "hard" in qa_file else "Soft QA"
        summary = qa.get("summary", qa if "has_errors" in qa else {})
        if "summary" not in qa and "has_errors" in qa:
             # Match hard QA report format
             print(f"{name}: has_errors={qa.get('has_errors')}")
        else:
             print(f"{name}: Major={summary.get('major', 0)}, Minor={summary.get('minor', 0)}")

# Metrics
print("\n--- LLM 调用统计 ---")
if os.path.exists("reports/smoke_metrics_report.json"):
    with open("reports/smoke_metrics_report.json") as f:
        metrics = json.load(f)
    print(f"Metrics Report valid: Yes")

print("\n" + "=" * 70)
print(f"Overall Status: {'✅ PASS' if all_pass else '❌ FAIL'}")
print("=" * 70)
