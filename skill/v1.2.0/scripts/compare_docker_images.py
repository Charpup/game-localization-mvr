import json
import subprocess

def get_inspect_data(image_name):
    try:
        res = subprocess.run(["docker", "inspect", image_name], capture_output=True, text=True)
        if res.returncode == 0:
            return json.loads(res.stdout)[0]
    except Exception as e:
        pass
    return None

images = ["gate_v2:latest", "loc-mvr:gate_v2", "loc-mvr:omni_part3"]
for img in images:
    data = get_inspect_data(img)
    if not data:
        print(f"--- {img} NOT FOUND ---")
        continue
    env = {e.split('=')[0]: e.split('=')[1] for e in data.get("Config", {}).get("Env", []) if '=' in e}
    # Filter out common base env vars to focus on project specific ones
    base_env = {'PATH', 'GPG_KEY', 'PYTHON_VERSION', 'PYTHON_PIP_VERSION', 'PYTHON_GET_PIP_URL', 'PYTHON_GET_PIP_SHA256', 'LANG', 'PYTHONDONTWRITEBYTECODE', 'PYTHONUNBUFFERED'}
    relevant_env = {k: v for k, v in env.items() if k not in base_env}
    cmd = data.get("Config", {}).get("Cmd", [])
    print(f"IMAGE: {img}")
    print(f"  ENV: {relevant_env}")
    print(f"  CMD: {cmd}")
    print("-" * 20)
