import os
import subprocess
from pathlib import Path

def get_env():
    path = Path("data/attachment/api_key.txt")
    if not path.exists():
        raise FileNotFoundError("api_key.txt not found")
    
    lines = path.read_text().splitlines()
    env = os.environ.copy()
    for line in lines:
        if "base url:" in line:
            env["LLM_BASE_URL"] = line.split("base url:")[1].strip()
        if "api key:" in line:
            env["LLM_API_KEY"] = line.split("api key:")[1].strip()
            
    env["LLM_TRACE_PATH"] = "data/alpha_test/trace_20.jsonl"
    env["LLM_RUN_ID"] = "alpha_test_20"
    # User requested to use default router model
    if "LLM_MODEL" in env: del env["LLM_MODEL"]
    return env

def main():
    env = get_env()
    cmd = [
        "python", "scripts/translate_llm.py",
        "--input", "data/alpha_test/input_20.csv",
        "--output", "data/alpha_test/output_20.csv",
        "--style", "data/test06_outputs/style_guide_generated.md",
        "--glossary", "data/test06_outputs/compiled_r1.yaml",
        "--checkpoint", "data/alpha_test/checkpoint_20.json",
        "--batch_size", 10,
        "--escalate_csv", "data/alpha_test/escalate_20.csv"
    ]
    # Reset checkpoint for fresh run
    ckpt_path = Path("data/alpha_test/checkpoint_20.json")
    if ckpt_path.exists(): ckpt_path.unlink()
    
    subprocess.run([str(c) for c in cmd], env=env)

if __name__ == "__main__":
    main()
