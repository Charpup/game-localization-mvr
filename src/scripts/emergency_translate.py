
import json
import csv
import sys
import os
import time
from pathlib import Path

# Add current dir to path to find sibling modules
sys.path.append(os.getcwd())

from translate_llm import load_checkpoint, save_checkpoint, validate_translation, load_text, load_glossary, build_glossary_summary, build_system_prompt_factory, build_user_prompt
from runtime_adapter import batch_llm_call

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--shard_id", type=int, default=0)
    parser.add_argument("--shard_total", type=int, default=1)
    args = parser.parse_args()

    # Paths (relative to scripts/ dir => use ../)
    root = Path("..")
    norm_csv = root / "data/Production Batch/01. Omni Production_go/Production_go_normalized.csv"
    
    # Sharded output
    suffix = f"_{args.shard_id}" if args.shard_total > 1 else ""
    translated_csv = root / f"data/Production Batch/01. Omni Production_go/Production_go_translated{suffix}.csv"
    checkpoint_path = root / f"data/Production Batch/01. Omni Production_go/translate_checkpoint{suffix}.json"
    
    global_checkpoint = root / "data/Production Batch/01. Omni Production_go/translate_checkpoint.json"
    
    glossary_path = root / "glossary/compiled.yaml"
    style_path = root / "workflow/style_guide.md"

    # Load resources
    print(f"Loading resources (Shard {args.shard_id}/{args.shard_total})...")
    
    # Load global done
    done_ids = load_checkpoint(str(global_checkpoint))
    # Load shard done (if resuming)
    shard_done_ids = load_checkpoint(str(checkpoint_path))
    
    glossary, _ = load_glossary(str(glossary_path))
    glossary_summary = build_glossary_summary(glossary)
    style_guide = load_text(str(style_path))
    
    # Load all rows
    with open(norm_csv, "r", encoding="utf-8-sig") as f:
        all_rows = list(csv.DictReader(f))
    
    headers = list(all_rows[0].keys())
    if "target_text" not in headers: headers.append("target_text")

    # Filter pending (Global)
    # We only care about what is NOT in global done AND NOT in shard done
    pending_global = [r for r in all_rows if r.get("string_id") not in done_ids]
    
    # Shard assignment: simple modulo
    # Filter pending_global for this shard
    my_rows = [r for i, r in enumerate(pending_global) if i % args.shard_total == args.shard_id]
    
    # Filter already done in shard
    my_pending = [r for r in my_rows if r.get("string_id") not in shard_done_ids]

    if not my_pending:
        print("✅ No pending rows for this shard!")
        return

    print(f"🚀 Shard {args.shard_id}: {len(my_pending)} rows to process (of {len(my_rows)} assigned)")
    
    system_prompt_builder = build_system_prompt_factory(style_guide, glossary_summary)

    processed_count = 0
    success_count = 0
    
    for i, target_row in enumerate(my_pending):
        sid = target_row["string_id"]
        print(f"[{i+1}/{len(my_pending)}] Processing {sid}...", end="", flush=True)
        
        # Prepare batch of 1
        batch_rows = [{
            "id": sid,
            "source_text": target_row.get("tokenized_zh") or target_row.get("source_zh") or ""
        }]
        
        final_system_prompt = system_prompt_builder(batch_rows)
        
        try:
            results = batch_llm_call(
                step="translate",
                rows=batch_rows,
                model="gpt-4.1-mini", 
                system_prompt=final_system_prompt,
                user_prompt_template=build_user_prompt,
                retry=2, 
                allow_fallback=True
            )
            
            if not results:
                print(" ❌ Failed (Empty result)")
                continue
                
            res = results[0]
            target_text = res.get("target_ru", "")

            # Validate
            ok, err = validate_translation(target_row.get("tokenized_zh") or target_row.get("source_zh") or "", target_text)
            
            if ok:
                target_row["target_text"] = target_text
                
                # Append to Sharded CSV
                write_mode = "a" if translated_csv.exists() else "w"
                with open(translated_csv, write_mode, encoding="utf-8-sig", newline="") as f:
                    writer = csv.DictWriter(f, fieldnames=headers)
                    if write_mode == "w": writer.writeheader()
                    writer.writerow(target_row)
                
                # Update Sharded Checkpoint
                shard_done_ids.add(sid)
                save_checkpoint(str(checkpoint_path), shard_done_ids)
                
                print(" ✅ Saved")
                success_count += 1
            else:
                print(f" ⚠️ Validation Failed: {err}")
        
        except Exception as e:
            print(f" ❌ Error: {e}")
            time.sleep(1)
        
        processed_count += 1

    print(f"\n🏁 Shard {args.shard_id} Finished. Success: {success_count}/{len(my_pending)}")

if __name__ == "__main__":
    main()
