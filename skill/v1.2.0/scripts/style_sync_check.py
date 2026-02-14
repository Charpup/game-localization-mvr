#!/usr/bin/env python3
import sys
import re
from pathlib import Path

def strip_frontmatter(content: str) -> str:
    """Removes YAML frontmatter (between first and second ---) if exists."""
    if content.startswith("---"):
        parts = re.split(r"^---\s*$", content, maxsplit=2, flags=re.MULTILINE)
        if len(parts) >= 3:
            return parts[2].strip()
    return content.strip()

def check_sync():
    root = Path(__file__).parent.parent
    agent_style_path = root / ".agent" / "workflows" / "style-guide.md"
    workflow_style_path = root / "workflow" / "style_guide.md"

    print(f"🔍 Checking synchronization between style guides...")
    
    if not agent_style_path.exists():
        print(f"❌ Error: Agent style guide missing at {agent_style_path}")
        return False
    if not workflow_style_path.exists():
        print(f"❌ Error: Workflow style guide missing at {workflow_style_path}")
        return False

    agent_content = strip_frontmatter(agent_style_path.read_text(encoding="utf-8"))
    workflow_content = strip_frontmatter(workflow_style_path.read_text(encoding="utf-8"))

    if agent_content == workflow_content:
        print("✅ Success: Style guides are in sync.")
        return True
    else:
        print("⚠️ Warning: Style guides have diverged!")
        print(f"Path A: {agent_style_path}")
        print(f"Path B: {workflow_style_path}")
        
        # Simple diff-like hint
        if len(agent_content) != len(workflow_content):
            print(f"Size mismatch: {len(agent_content)} chars vs {len(workflow_content)} chars.")
        
        # We allow small differences (like "Last Sync" date in comments) but here we want strict consistency
        # for core rules. For now, let's treat any mismatch as a sync failure in this exercise.
        print("Please ensure both files share the same core rules.")
        return False

if __name__ == "__main__":
    if not check_sync():
        sys.exit(1)
    sys.exit(0)
