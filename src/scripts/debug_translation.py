
import json
import csv
import sys
import os
from pathlib import Path

# Add current dir to path to find sibling modules
sys.path.append(os.getcwd())

from translate_llm import load_checkpoint, validate_translation, load_text, load_glossary, build_glossary_summary, build_system_prompt_factory
from runtime_adapter import batch_llm_call

def main():
    # Paths (relative to scripts/ dir => use ../)
    root = Path("..")
    norm_csv = root / "data/Production Batch/01. Omni Production_go/Production_go_normalized.csv"
    checkpoint_path = root / "data/Production Batch/01. Omni Production_go/translate_checkpoint.json"
    glossary_path = root / "glossary/compiled.yaml"
    style_path = root / "workflow/style_guide.md"

    # Load context
    print("Loading context...")
    done_ids = load_checkpoint(str(checkpoint_path))
    print(f"Done IDs count: {len(done_ids)}")
    
    target_row = None
    with open(norm_csv, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row["string_id"] not in done_ids:
                target_row = row
                break
    
    if not target_row:
        print("✅ No pending rows found!")
        return

    print(f"Found pending row: {target_row['string_id']}")
    print(f"Source: {target_row.get('tokenized_zh')}")

    # Prepare batch (mimic translate_llm.py logic)
    batch_rows = [{
        "id": target_row["string_id"],
        "source_text": target_row.get("tokenized_zh") or target_row.get("source_zh") or ""
    }]
    
    # Load glossary/style text
    glossary, _ = load_glossary(glossary_path)
    glossary_summary = build_glossary_summary(glossary)
    style_guide = load_text(style_path)

    # Build prompt
    from translate_llm import build_system_prompt_factory, build_user_prompt
    system_prompt_builder = build_system_prompt_factory(style_guide, glossary_summary)
    final_system_prompt = system_prompt_builder(batch_rows)
    
    # Call LLM
    print(f"Calling LLM (gpt-4.1) for row {target_row['string_id']}...")
    results = batch_llm_call(
        step="translate",
        rows=batch_rows,
        model="gpt-4.1",
        system_prompt=final_system_prompt,
        user_prompt_template=build_user_prompt,
        retry=0, # Fail fast
        allow_fallback=False
    )
    
    print("\n=== Result ===")
    print(json.dumps(results, indent=2, ensure_ascii=False))
    
    if not results:
        print("❌ Result is empty (Batch failed silently?)")
    else:
        # Validate
        res = results[0]
        ok, err = validate_translation(target_row.get("tokenized_zh") or target_row.get("source_zh") or "", res.get("target_text"))
        if ok:
            print("✅ Validation PASSED")
            print(f"Target: {res.get('target_text')}")
        else:
            print(f"❌ Validation FAILED: {err}")
            print(f"Target: {res.get('target_text')}")

if __name__ == "__main__":
    main()
