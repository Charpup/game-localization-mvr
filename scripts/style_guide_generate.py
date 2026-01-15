#!/usr/bin/env python3
import sys
import os
import json
import re
import argparse
import time
import hashlib
from builtins import Exception
from typing import List, Dict, Any, Optional

try:
    from runtime_adapter import LLMClient, LLMError
except ImportError:
    # Allow running without runtime_adapter for testing compilation only
    LLMClient = None

# ----------------------------------------------------------------------
# 1. Questionnaire Compilation Logic (FIX 1)
# ----------------------------------------------------------------------

def parse_markdown_questionnaire(md_content: str) -> Dict[str, Any]:
    """
    Parses the structured Markdown questionnaire into a flat JSON dictionary.
    
    Structure expected:
    ## 1. Section Title
    **Key**: Value
    - [x] Choice
    """
    data = {}
    current_section = None
    
    # Simple regexes
    header_re = re.compile(r'^##\s+\d+\.\s+(.*)')
    key_val_re = re.compile(r'^\*\*(.*?)\*\*:\s*(.*)')
    choice_re = re.compile(r'^-\s+\[([xX ])\]\s+(.*)')
    
    lines = md_content.split('\n')
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        # Header
        h_match = header_re.match(line)
        if h_match:
            current_section = h_match.group(1).strip()
            continue
            
        # Key-Value
        kv_match = key_val_re.match(line)
        if kv_match:
            k = kv_match.group(1).strip()
            v = kv_match.group(2).strip()
            # Normalize key
            safe_key = f"{current_section}__{k}".replace(' ', '_').lower() if current_section else k.lower()
            data[safe_key] = v
            continue
            
        # Choice
        c_match = choice_re.match(line)
        if c_match:
            is_checked = c_match.group(1).lower() == 'x'
            text = c_match.group(2).strip()
            if is_checked:
                # Add to a list or set specific key
                # For this simple parser, we'll assume the last key needs this choice
                # Or just store "selected_choices"
                if "selected_choices" not in data:
                    data["selected_choices"] = []
                data["selected_choices"].append(f"{current_section}: {text}")
    
    return data

def compile_questionnaire(input_path: str, output_path: str) -> Dict[str, Any]:
    """Reads MD, compiles to JSON, writes to file, returns data."""
    with open(input_path, 'r', encoding='utf-8') as f:
        md_content = f.read()
    
    data = parse_markdown_questionnaire(md_content)
    # Add metadata
    data['_meta'] = {
        'source_file': input_path,
        'timestamp': time.time(),
        'source_hash': hashlib.md5(md_content.encode('utf-8')).hexdigest()
    }
    
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        
    print(f"[Generate] Compiled questionnaire to {output_path}")
    return data

# ----------------------------------------------------------------------
# 2. Generation Logic
# ----------------------------------------------------------------------

def load_template(template_path: str) -> str:
    if not template_path or not os.path.exists(template_path):
        return ""
    with open(template_path, 'r', encoding='utf-8') as f:
        return f.read()

def generate_candidates(
    questionnaire_data: Dict[str, Any],
    template_content: str,
    output_dir: str,
    count: int = 3,
    dry_run: bool = False
):
    if dry_run:
        print("[Dry-Run] Would generate candidates using LLM")
        # Generate dummy files for testing flow
        for i in range(count):
            out_file = os.path.join(output_dir, f"candidate_{i+1}.md")
            with open(out_file, 'w', encoding='utf-8') as f:
                f.write(f"# Style Guide Candidate {i+1} (Dry Run)\n\n## Tone & Voice\nMock Content\n\n## Terminology Policy\nMock Content\n\n## UI Length & Brevity\nMock Content\n\n## Forbidden Patterns\nMock Content\n\n## Placeholder Handling\nMock Content")
        return

    client = LLMClient()
    
    system_prompt = """You are an expert Game Localization Director.
Your task is to generate a comprehensive Style Guide (Markdown) for a game localization project (ZH -> RU).
You will be given a completed questionnaire defining the IP requirements.
You MUST follow the structure of the provided template EXACTLY, but fill it with rules derived from the questionnaire.
    
CRITICAL SECTIONS TO INCLUDE:
1. Tone & Voice (Keywords, Ratio, Examples)
2. Terminology Policy (Transliteration vs Translation rules)
3. Grammar & Mechanics (Register: Ты vs Вы, Gender handling)
4. UI Length & Brevity (Constraints, Abbreviation rules)
5. Forbidden Patterns (Strict negative constraints)
6. Placeholder Handling (Technical rules for {0}, <br>, etc.)

Output ONLY the Markdown content. Do not include prologue."""

    user_prompt = f"""
Input Questionnaire Data:
{json.dumps(questionnaire_data, indent=2, ensure_ascii=False)}

Reference Template Structure:
{template_content}

Generate {count} distinct variations of the Style Guide.
Variation 1: Strict adherence to questionnaire/official tone.
Variation 2: Slightly more creative/localized adaptation (if allowed by questionnaire).
Variation 3: Balanced approach.

But for this API call, just generate ONE variation. I will call you K times.
Current Variation Purpose: Generate a high-quality style guide based on the questionnaire.
"""

    for i in range(count):
        print(f"[Generate] Generating candidate {i+1}/{count}...")
        try:
            # We add a slight variation hint to the prompt for each candidate if needed,
            # but for now rely on temperature=0.7 to give variations, or explicit prompt tweaks.
            # Let's add a robust prompt tweak.
            var_prompt = user_prompt + f"\n\nVariation Focus: Candidate {i+1}"
            
            result = client.chat(
                system=system_prompt,
                user=var_prompt,
                metadata={"step": "style_guide_generate", "variation": str(i+1)}
            )
            
            content = result.text
            
            # Simple validation: Check headers
            if "## Tone & Voice" not in content:
                print(f"[Warning] Candidate {i+1} missing headers, attempting to repair...")
                content = "# Style Guide\n\n" + content
                
            out_file = os.path.join(output_dir, f"candidate_{i+1}.md")
            with open(out_file, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"[Generate] Saved {out_file}")
            
        except Exception as e:
            print(f"[Error] Failed to generate candidate {i+1}: {e}")

# ----------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Generate Style Guide candidates from questionnaire")
    parser.add_argument("--inputs", required=True, help="Path to input questionnaire markdown file")
    parser.add_argument("--template", help="Path to reference template (optional)")
    parser.add_argument("--output-dir", default="artifacts/style_guide_candidates", help="Directory to save candidates")
    parser.add_argument("--count", type=int, default=3, help="Number of candidates to generate")
    parser.add_argument("--dry-run", action="store_true", help="Skip LLM calls")
    
    args = parser.parse_args()
    
    # 1. Compile Questionnaire (Source of Truth)
    run_id = int(time.time())
    json_path = os.path.join(args.output_dir, f"questionnaire.{run_id}.json")
    
    print(f"[Generate] Compiling {args.inputs} -> {json_path}")
    q_data = compile_questionnaire(args.inputs, json_path)
    
    # 2. Load Template
    tmpl_content = load_template(args.template) if args.template else ""
    if not tmpl_content:
        print("[Generate] No template provided, using generic structure.")
        tmpl_content = "## Tone & Voice\n...\n## Terminology Policy\n..."

    # 3. Generate Candidates
    generate_candidates(q_data, tmpl_content, args.output_dir, args.count, args.dry_run)
    
    print("[Generate] Done.")

if __name__ == "__main__":
    main()
