#!/usr/bin/env python3
import json
import os
import argparse
from typing import List, Dict

def main():
    parser = argparse.ArgumentParser(description="Generate prompt optimization proposals (Static).")
    parser.add_argument("--inventory", default="artifacts/llm_prompt_inventory.json", help="Path to inventory")
    parser.add_argument("--output", default="artifacts/prompt_proposals.json", help="Path to output proposals")
    args = parser.parse_args()

    if not os.path.exists(args.inventory):
        print(f"❌ Inventory not found: {args.inventory}. Run llm_prompt_inventory.py first.")
        return

    with open(args.inventory, 'r', encoding='utf-8') as f:
        inventory = json.load(f)

    proposals = []
    print(f"🔍 Analyzing {len(inventory)} usage sites...")

    for item in inventory:
        script = item.get('script_path', '')
        # Use full source if available, fallback to snippet
        source_content = item.get('prompt_source') or item.get('prompt_snippet', '')
        
        suggestion = None
        
        # Heuristic 1: Check for explicit constraints
        if "forbidden" not in source_content.lower() and "constraint" not in source_content.lower() and "禁止" not in source_content:
             suggestion = "Add explicit 'Constraints' section (e.g. Forbidden tokens matching)."
             
        # Heuristic 2: Check for JSON enforcement
        if "json" in source_content.lower() and "schema" not in source_content.lower():
             suggestion = "Mention 'JSON Schema' or provide example JSON structure."

        if suggestion:
            proposals.append({
                "script": script,
                "function": item.get('function_name'),
                "current_snippet_preview": source_content[:100] + "...",
                "proposal_type": "clarity_improvement",
                "suggestion": suggestion
            })

    # Write proposals
    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    with open(args.output, 'w', encoding='utf-8') as f:
        json.dump(proposals, f, indent=2, ensure_ascii=False)

    print(f"✅ Generated {len(proposals)} proposals in {args.output}")
    print("ℹ️  Review these proposals and apply changes manually via PR.")

if __name__ == "__main__":
    main()
