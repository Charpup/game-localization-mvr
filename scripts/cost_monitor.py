#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
cost_monitor.py

Cost monitoring coordinator.
- Loads config from cost_monitoring.yaml
- Tracks LLM calls for periodic snapshots
- Conditionally enables API易 usage reconciliation
- Generates reports on demand or signal (Ctrl+C)
"""

import json
import os
import signal
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional

try:
    import yaml
except ImportError:
    yaml = None


class CostMonitor:
    """
    Side-channel cost monitoring for LLM pipeline.
    
    Thread-safe singleton for per-run tracking.
    """
    
    _instance: Optional['CostMonitor'] = None
    
    def __init__(
        self,
        config_path: str = "config/cost_monitoring.yaml",
        run_id: Optional[str] = None,
        base_url: Optional[str] = None,
        trace_path: str = "data/llm_trace.jsonl"
    ):
        """
        Initialize cost monitor.
        
        Args:
            config_path: Path to cost_monitoring.yaml
            run_id: Run identifier (from LLM_RUN_ID env if not provided)
            base_url: LLM base URL (for conditional API易 enabling)
            trace_path: Path to LLM trace file
        """
        self.config = self._load_config(config_path)
        self.run_id = run_id or os.getenv("LLM_RUN_ID", "default")
        self.base_url = base_url or os.getenv("LLM_BASE_URL", "")
        self.trace_path = trace_path
        
        self.call_count = 0
        self.last_pull_time = time.time()
        self.start_ts = datetime.now().isoformat()
        
        # Conditional API易 client
        self.apiyi_client = None
        if self._should_enable_apiyi():
            try:
                from apiyi_usage_client import create_if_match
                self.apiyi_client = create_if_match(self.base_url.rstrip("/"))
                if self.apiyi_client:
                    print(f"📊 API易 usage monitoring enabled for {self.run_id}")
            except Exception as e:
                print(f"⚠️ API易 client init warning: {e}")
        
        # Register signal handler for snapshot on exit
        if self.config.get("outputs", {}).get("snapshot_on_signal", True):
            self._register_signal_handlers()
    
    def _load_config(self, path: str) -> Dict[str, Any]:
        """Load cost monitoring config."""
        if yaml is None:
            return {"enable": True}
        
        try:
            if Path(path).exists():
                with open(path, "r", encoding="utf-8") as f:
                    return yaml.safe_load(f) or {}
        except Exception:
            pass
        return {"enable": True}
    
    def _should_enable_apiyi(self) -> bool:
        """Check if API易 should be enabled based on config and base_url."""
        providers = self.config.get("providers", {})
        apiyi_cfg = providers.get("apiyi", {})
        
        if not apiyi_cfg.get("enable", False):
            return False
        
        match_url = apiyi_cfg.get("base_url_match", "")
        return self.base_url.rstrip("/") == match_url.rstrip("/")
    
    def _register_signal_handlers(self) -> None:
        """Register handlers for graceful shutdown."""
        def handler(signum, frame):
            print("\n📊 Generating final cost snapshot...")
            self.snapshot(reason="signal")
            sys.exit(0)
        
        try:
            signal.signal(signal.SIGINT, handler)
            signal.signal(signal.SIGTERM, handler)
        except Exception:
            pass  # May fail on Windows in some contexts
    
    def on_llm_call(self) -> None:
        """
        Called after each LLM call.
        Checks if periodic reconciliation/snapshot is needed.
        """
        self.call_count += 1
        
        # Check pull_every_n_calls
        providers = self.config.get("providers", {})
        apiyi_cfg = providers.get("apiyi", {})
        pull_every_n = apiyi_cfg.get("pull_every_n_calls", 200)
        
        if self.apiyi_client and self.call_count % pull_every_n == 0:
            self._maybe_reconcile()
        
        # Check pull_interval_seconds
        pull_interval = apiyi_cfg.get("pull_interval_seconds", 300)
        elapsed = time.time() - self.last_pull_time
        
        if self.apiyi_client and elapsed >= pull_interval:
            self._maybe_reconcile()
    
    def _maybe_reconcile(self) -> None:
        """Pull API易 usage if enabled and update last_pull_time."""
        if not self.apiyi_client:
            return
        
        try:
            end_ts = datetime.now().isoformat()
            apiyi_usage = self.apiyi_client.pull_usage(self.start_ts, end_ts)
            self.last_pull_time = time.time()
            
            # Log reconciliation (non-blocking)
            if apiyi_usage.get("error"):
                print(f"⚠️ API易 usage pull warning: {apiyi_usage.get('error')}")
        except Exception as e:
            print(f"⚠️ API易 reconciliation warning: {e}")
    
    def snapshot(self, reason: str = "manual") -> Optional[str]:
        """
        Generate cost snapshot.
        
        Returns path to snapshot JSON file.
        """
        try:
            from cost_snapshot import aggregate_trace, save_snapshot, generate_report_md
            
            end_ts = datetime.now().isoformat()
            
            # Aggregate local trace
            snapshot_data = aggregate_trace(
                self.trace_path,
                run_id=self.run_id,
                start_ts=self.start_ts,
                end_ts=end_ts
            )
            
            # Add API易 data if available
            if self.apiyi_client:
                try:
                    apiyi_usage = self.apiyi_client.pull_usage(self.start_ts, end_ts)
                    snapshot_data["apiyi"] = apiyi_usage
                    
                    # Calculate delta
                    local_cost = snapshot_data.get("local", {}).get("total_cost_usd_est", 0)
                    apiyi_cost = apiyi_usage.get("total_cost_usd_reported", 0)
                    delta = abs(apiyi_cost - local_cost)
                    delta_ratio = delta / max(local_cost, apiyi_cost, 0.01)
                    
                    snapshot_data["reconciliation"] = {
                        "delta_usd": round(delta, 4),
                        "delta_ratio": round(delta_ratio, 4),
                        "status": "ok" if delta_ratio < 0.1 else "warn",
                        "notes": [
                            "apiyi usage aggregated by time window",
                            "local is per-call trace sum"
                        ]
                    }
                except Exception as e:
                    snapshot_data["apiyi"] = {"enabled": True, "error": str(e)}
            else:
                snapshot_data["apiyi"] = {"enabled": False}
            
            # Add metadata
            snapshot_data["generated_at"] = datetime.now().isoformat()
            snapshot_data["reason"] = reason
            snapshot_data["call_count"] = self.call_count
            
            # Save
            output_dir = self.config.get("outputs", {}).get("dir", "reports/cost")
            json_path = save_snapshot(snapshot_data, output_dir)
            
            # Generate MD report
            md_content = generate_report_md(snapshot_data)
            md_path = os.path.join(output_dir, "reconcile_report.md")
            with open(md_path, "w", encoding="utf-8") as f:
                f.write(md_content)
            
            return json_path
            
        except Exception as e:
            print(f"⚠️ Snapshot generation warning: {e}")
            return None
    
    @classmethod
    def get_instance(cls, **kwargs) -> 'CostMonitor':
        """Get or create singleton instance."""
        if cls._instance is None:
            cls._instance = cls(**kwargs)
        return cls._instance


# Module-level convenience functions
def init_cost_monitor(**kwargs) -> CostMonitor:
    """Initialize global cost monitor."""
    return CostMonitor.get_instance(**kwargs)


def on_llm_call() -> None:
    """Called after each LLM call."""
    if CostMonitor._instance:
        CostMonitor._instance.on_llm_call()


def snapshot(reason: str = "manual") -> Optional[str]:
    """Generate cost snapshot."""
    if CostMonitor._instance:
        return CostMonitor._instance.snapshot(reason)
    return None
