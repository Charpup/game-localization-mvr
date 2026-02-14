#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
apiyi_usage_client.py

Conditional API易 usage client.
Only initializes when base_url matches "https://api.apiyi.com/v1".
Pulls usage data for cost reconciliation.
"""

import os
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional

import requests


class ApiYiUsageClient:
    """
    Client for API易 usage endpoint using balance query API.
    
    Only creates when base_url matches exactly.
    """
    
    MATCH_URL = "https://api.apiyi.com/v1"
    BALANCE_URL = "https://api.apiyi.com/api/user/self"
    
    def __init__(self, base_url: str, api_key: Optional[str] = None):
        """
        Initialize client.
        
        Args:
            base_url: Must match MATCH_URL exactly
            api_key: API key (optional)
        """
        if base_url.rstrip("/") != self.MATCH_URL:
            raise ValueError(f"ApiYiUsageClient only for {self.MATCH_URL}, got: {base_url}")
        
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key or self._load_api_key()
        
        if not self.api_key:
            raise ValueError("API key required for ApiYiUsageClient")
    
    def _load_api_key(self) -> str:
        """Load API key from environment variable or attachment file."""
        # 1. Priority: Environment variable (configured in Docker)
        token_env = os.getenv("LLM_ACCESS_TOKEN_FILE")
        if token_env and os.path.exists(token_env):
            try:
                return Path(token_env).read_text(encoding="utf-8").strip()
            except Exception:
                pass

        # 2. Check local relative path (standardized name)
        token_file = Path("data/attachment/api_access_token.txt")
        if token_file.exists():
            try:
                return token_file.read_text(encoding="utf-8").strip()
            except Exception:
                pass

        # 3. Fallback to general LLM_API_KEY env var
        return os.getenv("LLM_API_KEY", "")
    
    def pull_usage(
        self,
        start_ts: Optional[str] = None,
        end_ts: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Pull account usage data from API易 balance API.
        
        Note: This is account-level, not run-specific. 
        Higher-level logic should calculate deltas between snapshots.
        """
        try:
            # According to docs: https://docs.apiyi.com/api-capabilities/balance-query
            # Header is Authorization: {token} (Bearer is often optional or not used for this specific one)
            headers = {
                "Accept": "application/json",
                "Authorization": f"{self.api_key}",
                "Content-Type": "application/json"
            }
            
            resp = requests.get(
                self.BALANCE_URL,
                headers=headers,
                timeout=15
            )
            
            if resp.status_code == 200:
                data = resp.json()
                if data.get("success"):
                    return self._parse_balance_response(data.get("data", {}))
                else:
                    return {
                        "enabled": True,
                        "error": f"API Error: {data.get('message')}",
                        "total_cost_usd_reported": 0,
                        "by_model": {}
                    }
            else:
                return {
                    "enabled": True,
                    "error": f"HTTP {resp.status_code}: {resp.text[:200]}",
                    "total_cost_usd_reported": 0,
                    "by_model": {}
                }
                
        except Exception as e:
            return {
                "enabled": True,
                "error": str(e),
                "total_cost_usd_reported": 0,
                "by_model": {}
            }
    
    def _parse_balance_response(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse API易 balance response into a metrics-compatible format.
        
        data.quota: Remaining balance
        data.used_quota: Total used balance
        1 USD = 500,000 units
        """
        used_quota = data.get("used_quota", 0)
        remaining_quota = data.get("quota", 0)
        request_count = data.get("request_count", 0)
        
        total_cost_usd_reported = used_quota / 500000.0
        remaining_usd = remaining_quota / 500000.0
        
        return {
            "enabled": True,
            "total_cost_usd_reported": round(total_cost_usd_reported, 6),
            "remaining_usd": round(remaining_usd, 6),
            "request_count": request_count,
            "account_info": {
                "username": data.get("username"),
                "display_name": data.get("display_name"),
                "group": data.get("group")
            },
            "by_model": {} # Balance API doesn't provide per-model breakdown
        }


def create_if_match(base_url: str) -> Optional[ApiYiUsageClient]:
    """
    Factory: create client only if base_url matches.
    """
    try:
        # Normalize trailing slashes and version
        url = base_url.rstrip("/")
        if url == ApiYiUsageClient.MATCH_URL:
            return ApiYiUsageClient(url)
    except Exception:
        pass
    return None

