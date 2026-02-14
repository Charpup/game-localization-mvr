#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_apiyi_metrics.py
Verify APIyi balance query and cost calculation.
"""
import sys
import os
from pathlib import Path

# Add scripts to path
sys.path.append(str(Path(__file__).parent.parent / "scripts"))

try:
    from apiyi_usage_client import ApiYiUsageClient, create_if_match
    import json
except ImportError as e:
    print(f"Error: {e}")
    sys.exit(1)

def test_balance_query():
    base_url = "https://api.apiyi.com/v1"
    print(f"🔍 Testing APIyi balance query for: {base_url}")
    
    client = create_if_match(base_url)
    if not client:
        print("❌ Failed to create ApiYiUsageClient (URL mismatch?)")
        return
    
    print(f"✅ Client created. Token: {client.api_key[:4]}...{client.api_key[-4:]}")
    
    try:
        usage = client.pull_usage()
        print("\n📊 API Response:")
        print(json.dumps(usage, indent=2, ensure_ascii=False))
        
        if not usage.get("error"):
            print("\n✅ Verification Successful!")
            print(f"   Reported Cost: ${usage.get('total_cost_usd_reported')} (Cumulative)")
            print(f"   Remaining: ${usage.get('remaining_usd')}")
        else:
            print(f"\n❌ API Error: {usage.get('error')}")
            
    except Exception as e:
        print(f"\n❌ Execution Error: {e}")

if __name__ == "__main__":
    test_balance_query()
