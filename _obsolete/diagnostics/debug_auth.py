import os
import requests
import json

api_key = os.getenv("LLM_API_KEY")
base_url = os.getenv("LLM_BASE_URL", "").rstrip("/")

print(f"API Key: {api_key[:5]}...{api_key[-4:] if api_key else ''} (len={len(api_key) if api_key else 0})")
print(f"Base URL: {base_url}")

if not api_key or not base_url:
    print("Missing config")
    exit(1)

url = f"{base_url}/chat/completions"
headers = {
    "Authorization": f"Bearer {api_key}",
    "Content-Type": "application/json"
}
# Try a very standard model that should exist
payload = {
    "model": "gpt-3.5-turbo", 
    "messages": [{"role": "user", "content": "hi"}]
}

try:
    print(f"Sending request to {url}...")
    resp = requests.post(url, headers=headers, json=payload, timeout=10)
    print(f"Status Code: {resp.status_code}")
    print(f"Response: {resp.text}")
except Exception as e:
    print(f"Error: {e}")
