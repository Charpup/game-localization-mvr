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
# 3. Sample-based Style Guide Generation (New Mode)
# ----------------------------------------------------------------------

def load_glossary(path: str) -> Dict[str, str]:
    """Load glossary YAML as term_zh -> term_ru map."""
    import yaml
    if not os.path.exists(path):
        return {}
    with open(path, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f) or {}
    entries = data.get("entries", [])
    return {e.get("term_zh", ""): e.get("term_ru", "") for e in entries if e.get("term_zh")}

def load_sample_texts(csv_path: str, max_samples: int = 50) -> List[str]:
    """Load sample source texts from CSV."""
    import csv
    samples = []
    with open(csv_path, 'r', encoding='utf-8-sig', newline='') as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader):
            if i >= max_samples:
                break
            text = row.get("tokenized_zh") or row.get("source_zh") or ""
            if text.strip():
                samples.append(text.strip())
    return samples

def generate_from_sample(
    samples: List[str],
    glossary: Dict[str, str],
    output_path: str,
    dry_run: bool = False
):
    """Generate style guide from sample texts and glossary."""
    if dry_run:
        print("[Dry-Run] Would generate style guide from samples")
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write("# Style Guide (Dry Run)\n\n## Tone & Voice\nMock content for dry run.\n")
        return
    
    if LLMClient is None:
        print("[Error] LLMClient not available")
        return
    
    client = LLMClient()
    
    # Build prompt with samples and glossary
    glossary_excerpt = "\n".join([f"- {k}: {v}" for k, v in list(glossary.items())[:30]])
    samples_excerpt = "\n".join([f"• {s[:100]}..." if len(s) > 100 else f"• {s}" for s in samples[:20]])
    
    system_prompt = """你是游戏本地化风格指南专家（zh-CN → ru-RU）。
任务：根据提供的样本文本和术语表，生成一份完整的俄语翻译风格指南。

输出格式：纯 Markdown（无代码块、无额外说明）。

必须包含以下章节：
1. ## 语气与风格 (Tone & Voice) - 定义语气等级、关键词
2. ## 术语策略 (Terminology) - 音译 vs 意译规则
3. ## 语法规范 (Grammar) - 称谓（ты/Вы）、性别处理
4. ## UI 简洁性 (UI Brevity) - 字符限制、缩写规则
5. ## 禁止模式 (Forbidden Patterns) - 禁用词汇和表达
6. ## 占位符处理 (Placeholder Handling) - {0}、<br> 等处理规则
"""

    user_prompt = f"""
样本源文本（zh-CN）：
{samples_excerpt}

术语表摘录（zh-CN → ru-RU）：
{glossary_excerpt}

请基于以上信息生成完整的俄语翻译风格指南。
"""

    print("[Generate] Calling LLM to generate style guide...")
    try:
        result = client.chat(
            system=system_prompt,
            user=user_prompt,
            metadata={"step": "style_guide_generate", "mode": "sample_based"}
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
        
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"[Generate] Saved style guide to {output_path}")
        
    except Exception as e:
        print(f"[Error] Failed to generate style guide: {e}")

# ----------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Generate Style Guide candidates from questionnaire or samples")
    
    # Original mode (questionnaire-based)
    parser.add_argument("--inputs", help="Path to input questionnaire markdown file (legacy mode)")
    parser.add_argument("--template", help="Path to reference template (optional, legacy mode)")
    parser.add_argument("--output-dir", default="artifacts/style_guide_candidates", help="Directory to save candidates (legacy mode)")
    parser.add_argument("--count", type=int, default=3, help="Number of candidates to generate (legacy mode)")
    
    # New mode (sample-based) - matches implementation plan
    parser.add_argument("--input_sample", help="Path to normalized CSV with sample texts")
    parser.add_argument("--glossary", help="Path to compiled glossary YAML")
    parser.add_argument("--output", help="Output path for generated style guide")
    
    parser.add_argument("--dry-run", action="store_true", help="Skip LLM calls")
    
    args = parser.parse_args()
    
    # Determine mode
    if args.input_sample and args.output:
        # New sample-based mode
        print(f"[Generate] Sample-based mode")
        print(f"   Input sample: {args.input_sample}")
        print(f"   Glossary: {args.glossary}")
        print(f"   Output: {args.output}")
        
        samples = load_sample_texts(args.input_sample)
        print(f"[Generate] Loaded {len(samples)} sample texts")
        
        glossary = load_glossary(args.glossary) if args.glossary else {}
        print(f"[Generate] Loaded {len(glossary)} glossary entries")
        
        generate_from_sample(samples, glossary, args.output, args.dry_run)
        
    elif args.inputs:
        # Legacy questionnaire mode
        run_id = int(time.time())
        json_path = os.path.join(args.output_dir, f"questionnaire.{run_id}.json")
        
        print(f"[Generate] Compiling {args.inputs} -> {json_path}")
        q_data = compile_questionnaire(args.inputs, json_path)
        
        tmpl_content = load_template(args.template) if args.template else ""
        if not tmpl_content:
            print("[Generate] No template provided, using generic structure.")
            tmpl_content = "## Tone & Voice\n...\n## Terminology Policy\n..."

        generate_candidates(q_data, tmpl_content, args.output_dir, args.count, args.dry_run)
    else:
        parser.print_help()
        print("\n[Error] Either --inputs (legacy) or --input_sample + --output (new) is required")
        return 1
    
    print("[Generate] Done.")
    return 0

if __name__ == "__main__":
    sys.exit(main() or 0)
