#!/usr/bin/env python3
import sys
import os
import subprocess

# Simple wrapper to allow running scripts/qa_soft.py
script_dir = os.path.dirname(os.path.abspath(__file__))
target_script = os.path.join(script_dir, "soft_qa_llm.py")

if __name__ == "__main__":
    cmd = [sys.executable, target_script] + sys.argv[1:]
    sys.exit(subprocess.call(cmd))
