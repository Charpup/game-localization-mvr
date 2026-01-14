#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
llm_ping.py

LLM connectivity self-check. Run at pipeline start to fail-fast
if LLM config is missing or invalid.

Usage:
    python scripts/llm_ping.py
    
    # Returns exit code 0 on success, 1 on failure
    
Requirements:
    Environment variables:
    - LLM_BASE_URL: API endpoint
    - LLM_API_KEY: API key (NOT stored in repo)
    
    Model selection:
    - Uses routing.yaml step "llm_ping" for cheapest model
    - Falls back through configured fallback chain

Exit Codes:
    0: Success - LLM connectivity verified
    1: Failure - Missing config or connection error
"""

import os
import sys
import time
from datetime import datetime
from pathlib import Path

# Ensure UTF-8 output on Windows
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')


def check_env_vars() -> tuple[bool, list[str]]:
    """Check required environment variables.
    
    Returns: (all_present, missing_vars)
    """
    required = ['LLM_BASE_URL', 'LLM_API_KEY']
    missing = [var for var in required if not os.environ.get(var)]
    return len(missing) == 0, missing


def ping_llm() -> tuple[bool, str, dict]:
    """Ping LLM with minimal request.
    
    Uses router step "llm_ping" for model selection.
    
    Returns: (success, message, details)
    """
    try:
        from runtime_adapter import LLMClient, LLMError
    except ImportError as e:
        return False, f"Failed to import runtime_adapter: {e}", {}
    
    try:
        # Initialize client - will use router for model selection
        llm = LLMClient()
        
        start_time = time.time()
        
        # Minimal ping request - step "llm_ping" for routing
        result = llm.chat(
            system="You are a connectivity test.",
            user="Reply with exactly: PONG",
            metadata={"step": "llm_ping", "purpose": "connectivity_check"}
        )
        
        elapsed = time.time() - start_time
        
        # Verify response
        response_text = result.text.strip().upper()
        if "PONG" in response_text:
            return True, "Connectivity verified", {
                "model": getattr(result, 'model', 'unknown'),
                "latency_ms": int(elapsed * 1000),
                "response": result.text.strip()[:50]
            }
        else:
            return False, f"Unexpected response: {result.text[:100]}", {
                "model": getattr(result, 'model', 'unknown'),
                "latency_ms": int(elapsed * 1000)
            }
            
    except Exception as e:
        return False, f"LLM error: {str(e)}", {"error_type": type(e).__name__}


def main():
    print("🔌 LLM Connectivity Check")
    print(f"   Timestamp: {datetime.now().isoformat()}")
    print()
    
    # Step 1: Check environment variables
    print("1️⃣ Checking environment variables...")
    env_ok, missing = check_env_vars()
    
    if not env_ok:
        print()
        print("=" * 60)
        print("❌ FAIL: Missing required environment variables")
        print("=" * 60)
        print()
        print("Missing:")
        for var in missing:
            print(f"  - {var}")
        print()
        print("To fix, set these environment variables:")
        print("  export LLM_BASE_URL='https://api.example.com/v1'")
        print("  export LLM_API_KEY='your-api-key'")
        print()
        print("⚠️  SECURITY: Never commit API keys to the repository!")
        return 1
    
    print("   ✅ LLM_BASE_URL: set")
    print("   ✅ LLM_API_KEY: set (hidden)")
    print()
    
    # Step 2: Ping LLM
    print("2️⃣ Pinging LLM (step: llm_ping)...")
    success, message, details = ping_llm()
    
    if not success:
        print()
        print("=" * 60)
        print("❌ FAIL: LLM connectivity check failed")
        print("=" * 60)
        print()
        print(f"Error: {message}")
        if details:
            for k, v in details.items():
                print(f"  {k}: {v}")
        print()
        print("Possible causes:")
        print("  - Invalid API key")
        print("  - Network connectivity issue")
        print("  - API endpoint unreachable")
        print("  - Model not available")
        return 1
    
    print()
    print("=" * 60)
    print("✅ SUCCESS: LLM connectivity verified")
    print("=" * 60)
    print()
    print(f"   Message: {message}")
    if details:
        for k, v in details.items():
            print(f"   {k}: {v}")
    print()
    print("Pipeline can proceed with LLM-dependent steps.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
