#!/usr/bin/env python3
import sys
import os
import json
import re
import argparse
import glob
from typing import List, Dict, Any

try:
    from runtime_adapter import LLMClient
except ImportError:
    LLMClient = None

# ----------------------------------------------------------------------
# 1. Structural Gating (FIX 2)
# ----------------------------------------------------------------------

REQUIRED_HEADERS = [
    r'##\s+Tone\s*&\s*Voice',
    r'##\s+Terminology\s+Policy',
    r'##\s+UI\s+Length\s*(&|and)\s*Brevity',
    r'##\s+Forbidden\s+Patterns',
    r'##\s+Placeholder\s+Handling'
]

def check_structure(content: str) -> Dict[str, Any]:
    """
    Validates if the style guide candidate contains all mandatory sections.
    Returns: {"valid": bool, "missing": List[str]}
    """
    missing = []
    for pattern in REQUIRED_HEADERS:
        if not re.search(pattern, content, re.IGNORECASE):
            # Clean up regex for display
            display_name = pattern.replace(r'##\s+', '').replace(r'\s*', ' ').replace(r'\s+', ' ').replace(r'\\', '')
            missing.append(display_name)
            
    return {
        "valid": len(missing) == 0,
        "missing": missing
    }

# ----------------------------------------------------------------------
# 2. Scoring Logic
# ----------------------------------------------------------------------

def score_candidate(client: Any, filepath: str, content: str, dry_run: bool) -> Dict[str, Any]:
    if dry_run:
        return {"total_score": 85, "reasoning": "Dry run mock score"}

    system_prompt = """You are a QA Specialist for Game Localization Style Guides.
Score the provided Style Guide candidate (0-100) based on the rubric.
Rubric:
- Coverage (30pts): Are all sections detailed?
- Enforceability (30pts): Are rules specific and clear (not vague)?
- Naturalness (20pts): Does the target RU sound native?
- IP Fit (20pts): Does it match the IP context provided?

Output JSON ONLY:
{
    "total_score": int,
    "reasoning": "string"
}"""

    try:
        result = client.chat(
            system=system_prompt,
            user=f"Candidate Content:\n{content}",
            metadata={"step": "style_guide_score", "file": os.path.basename(filepath)}
        )
        
        # Parse JSON from response
        text = result.text.strip()
        # Remove markdown code blocks if present
        if text.startswith("```"):
            text = text.split("\n", 1)[1].rsplit("\n", 1)[0]
            
        return json.loads(text)
    except Exception as e:
        print(f"[Error] Scoring failed for {filepath}: {e}")
        return {"total_score": 0, "reasoning": f"Scoring error: {str(e)}"}

# ----------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Score Style Guide candidates")
    parser.add_argument("--candidates", required=True, help="Directory containing candidate_*.md files")
    parser.add_argument("--output-json", default="artifacts/style_guide_candidates/scorecard.json", help="Path to scorecard output")
    parser.add_argument("--output-selected", default="artifacts/style_guide_candidates/selected_best.md", help="Path to save best candidate")
    parser.add_argument("--dry-run", action="store_true", help="Skip LLM calls")
    
    args = parser.parse_args()
    
    client = LLMClient() if not args.dry_run and LLMClient else None
    
    candidates = glob.glob(os.path.join(args.candidates, "candidate_*.md"))
    if not candidates:
        print(f"[Score] No candidates found in {args.candidates}")
        sys.exit(1)
        
    scorecard = {
        "timestamp": 0,
        "results": []
    }
    
    best_score = -1
    best_candidate_path = None
    
    print(f"[Score] Evaluating {len(candidates)} candidates...")
    
    for cand_path in candidates:
        with open(cand_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        # 1. Structural Gating
        struct_check = check_structure(content)
        result = {
            "file": os.path.basename(cand_path),
            "disqualified": not struct_check["valid"],
            "disqualified_reason": struct_check["missing"] if not struct_check["valid"] else [],
            "score_details": {}
        }
        
        if result["disqualified"]:
            print(f"[Score] REFUSED {result['file']}: Missing sections {result['disqualified_reason']}")
            result["score_details"] = {"total_score": 0, "reasoning": "Structurally invalid"}
        else:
            # 2. LLM Scoring
            print(f"[Score] Scoring {result['file']}...")
            score_res = score_candidate(client, cand_path, content, args.dry_run)
            result["score_details"] = score_res
            print(f"       -> Score: {score_res.get('total_score', 0)}")
            
            if score_res.get("total_score", 0) > best_score:
                best_score = score_res.get("total_score", 0)
                best_candidate_path = cand_path
                
        scorecard["results"].append(result)
        
    # Write scorecard
    os.makedirs(os.path.dirname(args.output_json), exist_ok=True)
    with open(args.output_json, 'w', encoding='utf-8') as f:
        json.dump(scorecard, f, indent=2, ensure_ascii=False)
        
    print(f"[Score] Scorecard saved to {args.output_json}")
    
    # Save best
    if best_candidate_path:
        print(f"[Score] Best candidate: {best_candidate_path} ({best_score} pts)")
        with open(best_candidate_path, 'r', encoding='utf-8') as src:
            content = src.read()
        with open(args.output_selected, 'w', encoding='utf-8') as dst:
            dst.write(content)
        print(f"[Score] Saved best candidate to {args.output_selected}")
    else:
        print("[Score] No valid candidates found!")
        sys.exit(1)

if __name__ == "__main__":
    main()
