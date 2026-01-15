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
# 1. Questionnaire Compilation Logic
# ----------------------------------------------------------------------

def parse_markdown_questionnaire(md_content: str) -> Dict[str, Any]:
    """
    Parses the structured Markdown questionnaire into a flat JSON dictionary.
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
            safe_key = f"{current_section}__{k}".replace(' ', '_').lower() if current_section else k.lower()
            data[safe_key] = v
            continue
            
        # Choice
        c_match = choice_re.match(line)
        if c_match:
            is_checked = c_match.group(1).lower() == 'x'
            text = c_match.group(2).strip()
            if is_checked:
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
        for i in range(count):
            out_file = os.path.join(output_dir, f"candidate_{i+1}.md")
            with open(out_file, 'w', encoding='utf-8') as f:
                f.write(f"# Style Guide Candidate {i+1} (Dry Run)\n\n## Tone & Voice\nMock Content")
        return

    client = LLMClient()
    
    # Strict Markdown Prompt
    system_prompt = """You are an expert Game Localization Director (zh-CN -> ru-RU).
Task: Generate a comprehensive Style Guide (Markdown) for a game localization project based on IP requirements.
Output Format: Strict Markdown (NO prologue, NO epilogue, NO code blocks).
Content Rules:
1. Tone & Voice: Define tone levels and keywords.
2. Terminology: Transliteration vs Translation rules.
3. Grammar: Register (Ты/Вы), Gender handling.
4. UI Brevity: Constraints and abbreviations.
5. Forbidden Patterns: Strict negative constraints.
6. Placeholder Handling: Rules for {0}, <br>, etc.
"""

    user_prompt = f"""
Input Questionnaire Data:
{json.dumps(questionnaire_data, indent=2, ensure_ascii=False)}

Reference Template Structure:
{template_content}

Generate the style guide now.
"""

    for i in range(count):
        print(f"[Generate] Generating candidate {i+1}/{count}...")
        try:
            # Add variation hint
            var_prompt = user_prompt + f"\n\nVariation Focus: Candidate {i+1} (Variation {i+1})"
            
            result = client.chat(
                system=system_prompt,
                user=var_prompt,
                metadata={"step": "style_guide_generate", "variation": str(i+1)}
            )
            
            content = result.text.strip()
            # Remove markdown fence if present
            if content.startswith("```markdown"):
                content = content.replace("```markdown", "", 1)
            if content.startswith("```"):
                content = content.replace("```", "", 1)
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()
            
            # Validation
            if "## Tone & Voice" not in content and "# " not in content:
                print(f"[Warning] Candidate {i+1} seems malformed, attempting to header...")
                content = "# Style Guide (Auto-Generated)\n\n" + content
                
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
    
    run_id = int(time.time())
    json_path = os.path.join(args.output_dir, f"questionnaire.{run_id}.json")
    
    print(f"[Generate] Compiling {args.inputs} -> {json_path}")
    q_data = compile_questionnaire(args.inputs, json_path)
    
    tmpl_content = load_template(args.template) if args.template else ""
    if not tmpl_content:
        print("[Generate] No template provided, using generic structure.")
        tmpl_content = "## Tone & Voice\n...\n## Terminology Policy\n..."

    generate_candidates(q_data, tmpl_content, args.output_dir, args.count, args.dry_run)
    
    print("[Generate] Done.")

if __name__ == "__main__":
    main()
