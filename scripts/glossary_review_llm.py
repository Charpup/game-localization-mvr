#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
glossary_review_llm.py

LLM-assisted glossary review fallback for users who don't speak target language.

Two modes:
  1. --mode recommend (default):
     - Output review recommendations ONLY
     - Never writes approved.yaml
     - Human reviews LLM suggestions
  
  2. --mode approve_if_confident:
     - Output approved_patch.yaml (or reviewed.csv)
     - Contains approve/reject flags with confidence scores
     - Requires separate merge step to apply
     - All outputs are auditable + reversible

Usage:
    # Recommend mode (default)
    python scripts/glossary_review_llm.py \
        --proposals glossary/proposals.yaml \
        --output glossary/review_recommendations.yaml \
        --mode recommend

    # Approve-if-confident mode (fallback when user cannot review)
    python scripts/glossary_review_llm.py \
        --proposals glossary/proposals.yaml \
        --output glossary/approved_patch.yaml \
        --mode approve_if_confident \
        --confidence_threshold 0.85

Environment:
    LLM_BASE_URL, LLM_API_KEY, (LLM_MODEL optional - uses router)
"""

import argparse
import csv
import json
import os
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple

# Ensure UTF-8 output on Windows
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

try:
    import yaml
except ImportError:
    yaml = None

from runtime_adapter import LLMClient, LLMError


@dataclass
class ReviewResult:
    term_zh: str
    term_ru: str
    recommendation: str  # "approve", "reject", "revise"
    confidence: float  # 0.0 - 1.0
    reason: str
    suggested_term: Optional[str] = None  # For "revise" recommendations


def load_proposals(path: str) -> List[Dict[str, Any]]:
    """Load proposed glossary entries from YAML."""
    if not Path(path).exists():
        return []
    if yaml is None:
        raise RuntimeError("PyYAML required. Install with: pip install pyyaml")
    
    with open(path, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f) or {}
    
    return data.get("entries", data.get("proposals", []))


def load_style_guide(path: str) -> str:
    """Load style guide for context."""
    if not Path(path).exists():
        return ""
    with open(path, 'r', encoding='utf-8') as f:
        return f.read().strip()


def build_review_prompt(entries: List[Dict], style_guide: str, batch_size: int = 10) -> str:
    """Build prompt for reviewing glossary entries."""
    entries_text = ""
    for i, e in enumerate(entries[:batch_size], 1):
        entries_text += f"{i}. {e.get('term_zh', '')} → {e.get('term_ru', '')}\n"
        if e.get('context'):
            entries_text += f"   Context: {e['context'][:100]}\n"
    
    prompt = f"""You are a professional localization reviewer for zh-CN → ru-RU game translation.

Review the following proposed glossary entries for accuracy and appropriateness.

For each entry, provide:
1. recommendation: "approve", "reject", or "revise"
2. confidence: 0.0 to 1.0 (how certain you are)
3. reason: brief explanation
4. suggested_term: (only if "revise") better Russian translation

Style Guide Context:
{style_guide[:500] if style_guide else "(No style guide provided)"}

Proposed Entries:
{entries_text}

Output JSON array:
[
  {{"id": 1, "recommendation": "approve", "confidence": 0.95, "reason": "Correct translation"}},
  {{"id": 2, "recommendation": "revise", "confidence": 0.7, "reason": "Wrong gender", "suggested_term": "..."}}
]

Only output the JSON array, no explanation."""
    
    return prompt


def parse_review_response(text: str, entries: List[Dict]) -> List[ReviewResult]:
    """Parse LLM review response into ReviewResult objects."""
    results = []
    
    # Extract JSON from response
    try:
        # Try direct parse
        data = json.loads(text.strip())
    except json.JSONDecodeError:
        # Try extracting JSON block
        start = text.find('[')
        end = text.rfind(']')
        if start != -1 and end > start:
            try:
                data = json.loads(text[start:end+1])
            except:
                return []
        else:
            return []
    
    if not isinstance(data, list):
        return []
    
    for item in data:
        idx = item.get("id", 0) - 1
        if 0 <= idx < len(entries):
            entry = entries[idx]
            results.append(ReviewResult(
                term_zh=entry.get("term_zh", ""),
                term_ru=entry.get("term_ru", ""),
                recommendation=item.get("recommendation", "reject"),
                confidence=float(item.get("confidence", 0.0)),
                reason=item.get("reason", ""),
                suggested_term=item.get("suggested_term")
            ))
    
    return results


def write_recommendations_yaml(path: str, results: List[ReviewResult], mode: str) -> None:
    """Write review recommendations to YAML file."""
    if yaml is None:
        raise RuntimeError("PyYAML required")
    
    output = {
        "meta": {
            "generated_at": datetime.now().isoformat(),
            "mode": mode,
            "total_reviewed": len(results),
            "approved": sum(1 for r in results if r.recommendation == "approve"),
            "rejected": sum(1 for r in results if r.recommendation == "reject"),
            "revised": sum(1 for r in results if r.recommendation == "revise"),
        },
        "reviews": []
    }
    
    for r in results:
        review_entry = {
            "term_zh": r.term_zh,
            "term_ru": r.term_ru,
            "recommendation": r.recommendation,
            "confidence": round(r.confidence, 2),
            "reason": r.reason,
        }
        if r.suggested_term:
            review_entry["suggested_term"] = r.suggested_term
        output["reviews"].append(review_entry)
    
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        yaml.dump(output, f, allow_unicode=True, default_flow_style=False, sort_keys=False)


def write_approved_patch_yaml(path: str, results: List[ReviewResult], threshold: float) -> None:
    """Write approved patch YAML (for approve_if_confident mode)."""
    if yaml is None:
        raise RuntimeError("PyYAML required")
    
    approved = [r for r in results if r.recommendation == "approve" and r.confidence >= threshold]
    revised = [r for r in results if r.recommendation == "revise" and r.confidence >= threshold]
    rejected = [r for r in results if r.recommendation == "reject" or r.confidence < threshold]
    
    output = {
        "meta": {
            "generated_at": datetime.now().isoformat(),
            "mode": "approve_if_confident",
            "confidence_threshold": threshold,
            "total_reviewed": len(results),
            "auto_approved": len(approved),
            "auto_revised": len(revised),
            "rejected_or_low_confidence": len(rejected),
            "warning": "This patch was auto-generated by LLM. Human review recommended before merge.",
        },
        "approved_entries": [],
        "revised_entries": [],
        "rejected_entries": [],
    }
    
    for r in approved:
        output["approved_entries"].append({
            "term_zh": r.term_zh,
            "term_ru": r.term_ru,
            "confidence": round(r.confidence, 2),
            "reason": r.reason,
        })
    
    for r in revised:
        output["revised_entries"].append({
            "term_zh": r.term_zh,
            "original_term_ru": r.term_ru,
            "suggested_term_ru": r.suggested_term,
            "confidence": round(r.confidence, 2),
            "reason": r.reason,
        })
    
    for r in rejected:
        output["rejected_entries"].append({
            "term_zh": r.term_zh,
            "term_ru": r.term_ru,
            "recommendation": r.recommendation,
            "confidence": round(r.confidence, 2),
            "reason": r.reason,
        })
    
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        yaml.dump(output, f, allow_unicode=True, default_flow_style=False, sort_keys=False)


def main():
    ap = argparse.ArgumentParser(
        description="LLM-assisted glossary review for users who don't speak target language"
    )
    ap.add_argument("--proposals", required=True,
                    help="Input proposals YAML (from extract_terms or autopromote)")
    ap.add_argument("--output", required=True,
                    help="Output review file (YAML)")
    ap.add_argument("--style", default="workflow/style_guide.md",
                    help="Style guide for context")
    ap.add_argument("--mode", choices=["recommend", "approve_if_confident"],
                    default="recommend",
                    help="Review mode: recommend (default) or approve_if_confident")
    ap.add_argument("--confidence_threshold", type=float, default=0.85,
                    help="Confidence threshold for auto-approve (approve_if_confident mode)")
    ap.add_argument("--batch_size", type=int, default=10,
                    help="Batch size for LLM review")
    ap.add_argument("--dry-run", action="store_true",
                    help="Validate without making LLM calls")
    args = ap.parse_args()
    
    print("🔍 Glossary Review LLM")
    print(f"   Proposals: {args.proposals}")
    print(f"   Output: {args.output}")
    print(f"   Mode: {args.mode}")
    print()
    
    # Load proposals
    if not Path(args.proposals).exists():
        print(f"❌ Proposals file not found: {args.proposals}")
        return 1
    
    entries = load_proposals(args.proposals)
    if not entries:
        print("ℹ️  No proposals to review")
        return 0
    
    print(f"✅ Loaded {len(entries)} proposals")
    
    # Load style guide
    style_guide = load_style_guide(args.style)
    
    if args.dry_run:
        print()
        print("=" * 60)
        print("DRY-RUN MODE - Validation Summary")
        print("=" * 60)
        print(f"[OK] Would review {len(entries)} proposals")
        print(f"[OK] Mode: {args.mode}")
        if args.mode == "approve_if_confident":
            print(f"[OK] Confidence threshold: {args.confidence_threshold}")
        print(f"[OK] Would write to: {args.output}")
        print("[OK] Dry-run validation PASSED")
        print("=" * 60)
        return 0
    
    # Initialize LLM
    try:
        llm = LLMClient()
        print(f"✅ LLM client initialized")
    except LLMError as e:
        print(f"❌ LLM initialization failed: {e}")
        return 1
    
    # Review in batches
    all_results: List[ReviewResult] = []
    
    for i in range(0, len(entries), args.batch_size):
        batch = entries[i:i + args.batch_size]
        batch_num = i // args.batch_size + 1
        total_batches = (len(entries) + args.batch_size - 1) // args.batch_size
        
        print(f"  [{batch_num}/{total_batches}] Reviewing {len(batch)} entries...")
        
        prompt = build_review_prompt(batch, style_guide, args.batch_size)
        
        try:
            result = llm.chat(
                system="You are a professional game localization reviewer for zh-CN → ru-RU translation.",
                user=prompt,
                metadata={"step": "glossary_review", "batch": batch_num}
            )
            
            reviews = parse_review_response(result.text, batch)
            all_results.extend(reviews)
            
            approved = sum(1 for r in reviews if r.recommendation == "approve")
            print(f"    ✅ Reviewed: {len(reviews)} ({approved} approved)")
            
        except LLMError as e:
            print(f"    ⚠️  LLM error: {e}")
    
    print()
    
    # Write output based on mode
    if args.mode == "recommend":
        write_recommendations_yaml(args.output, all_results, args.mode)
        print(f"📋 Recommendations written to: {args.output}")
        print(f"   Total: {len(all_results)}")
        print(f"   Approved: {sum(1 for r in all_results if r.recommendation == 'approve')}")
        print(f"   Rejected: {sum(1 for r in all_results if r.recommendation == 'reject')}")
        print(f"   Revise: {sum(1 for r in all_results if r.recommendation == 'revise')}")
        print()
        print("📝 Next steps:")
        print("   1. Review the recommendations file")
        print("   2. Manually approve/reject entries based on recommendations")
        print("   3. Run glossary_apply_patch.py to merge approved entries")
        
    else:  # approve_if_confident
        write_approved_patch_yaml(args.output, all_results, args.confidence_threshold)
        auto_approved = sum(1 for r in all_results 
                           if r.recommendation == "approve" and r.confidence >= args.confidence_threshold)
        print(f"📋 Approved patch written to: {args.output}")
        print(f"   Auto-approved: {auto_approved} (confidence ≥ {args.confidence_threshold})")
        print()
        print("⚠️  WARNING: This patch was auto-generated by LLM.")
        print("    Human review is recommended before merging.")
        print()
        print("📝 Next steps:")
        print("   1. Review the approved_patch.yaml for accuracy")
        print("   2. Run glossary_apply_patch.py to merge into glossary")
    
    print()
    print("✅ Glossary review complete!")
    return 0


if __name__ == "__main__":
    sys.exit(main() or 0)
