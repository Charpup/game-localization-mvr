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
    Client for API易 usage endpoint.
    
    Only creates when base_url matches exactly.
    """
    
    MATCH_URL = "https://api.apiyi.com/v1"
    
    def __init__(self, base_url: str, api_key: Optional[str] = None):
        """
        Initialize client.
        
        Args:
            base_url: Must match MATCH_URL exactly
            api_key: API key (optional, can also read from LLM_API_KEY env)
        
        Raises:
            ValueError: If base_url doesn't match
        """
        if base_url.rstrip("/") != self.MATCH_URL:
            raise ValueError(f"ApiYiUsageClient only for {self.MATCH_URL}, got: {base_url}")
        
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key or self._load_api_key()
        
        if not self.api_key:
            raise ValueError("API key required for ApiYiUsageClient")
    
    def _load_api_key(self) -> str:
        """Load API key from file or environment."""
        # Try file first
        key_file = Path("secrets/APIYI_KEY.txt")
        if key_file.exists():
            return key_file.read_text().strip()
        
        # Try LLM_API_KEY_FILE
        key_file_env = os.getenv("LLM_API_KEY_FILE")
        if key_file_env and Path(key_file_env).exists():
            return Path(key_file_env).read_text().strip()
        
        # Fall back to env var
        return os.getenv("LLM_API_KEY", "")
    
    def pull_usage(
        self,
        start_ts: Optional[str] = None,
        end_ts: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Pull usage data from API易.
        
        Args:
            start_ts: Start timestamp (ISO format)
            end_ts: End timestamp (ISO format)
        
        Returns:
            Usage summary dict with by_model breakdown
        """
        # Note: API易 usage endpoint format may vary
        # This is a placeholder implementation that should be
        # adapted to the actual API易 usage API
        
        try:
            # Example endpoint - adjust based on actual API易 docs
            usage_url = f"{self.base_url}/dashboard/billing/usage"
            
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            params = {}
            if start_ts:
                params["start_date"] = start_ts[:10]  # YYYY-MM-DD
            if end_ts:
                params["end_date"] = end_ts[:10]
            
            resp = requests.get(
                usage_url,
                headers=headers,
                params=params,
                timeout=30
            )
            
            if resp.status_code == 200:
                data = resp.json()
                return self._parse_usage_response(data)
            else:
                return {
                    "enabled": True,
                    "error": f"HTTP {resp.status_code}",
                    "total_cost_usd_reported": 0,
                    "by_model": {}
                }
                
        except Exception as e:
            # Return error but don't crash
            return {
                "enabled": True,
                "error": str(e),
                "total_cost_usd_reported": 0,
                "by_model": {}
            }
    
    def _parse_usage_response(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Parse API易 usage response into standard format."""
        # This should be adapted to actual API易 response format
        # Example structure:
        #   {"data": {"usage": [...], "total_cost": 123.45}}
        
        by_model = {}
        total_cost = 0
        
        usage_list = data.get("data", {}).get("usage", [])
        if isinstance(usage_list, list):
            for item in usage_list:
                model = item.get("model", "unknown")
                if model not in by_model:
                    by_model[model] = {
                        "prompt_tokens": 0,
                        "completion_tokens": 0,
                        "cost_usd": 0
                    }
                by_model[model]["prompt_tokens"] += item.get("prompt_tokens", 0)
                by_model[model]["completion_tokens"] += item.get("completion_tokens", 0)
                by_model[model]["cost_usd"] += item.get("cost", 0)
                total_cost += item.get("cost", 0)
        
        # Or try direct total
        if not total_cost:
            total_cost = data.get("data", {}).get("total_cost", 0)
        
        return {
            "enabled": True,
            "total_cost_usd_reported": round(total_cost, 4),
            "by_model": by_model
        }


def create_if_match(base_url: str) -> Optional[ApiYiUsageClient]:
    """
    Factory: create client only if base_url matches.
    
    Returns None if not matching (no exception).
    """
    try:
        if base_url.rstrip("/") == ApiYiUsageClient.MATCH_URL:
            return ApiYiUsageClient(base_url)
    except Exception:
        pass
    return None
