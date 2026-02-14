#!/usr/bin/env python3
"""
Progress Reporter - 多层汇报机制统一实现

所有 LLM 模块必须使用此模块进行进度汇报，确保：
- L1: 检查点文件 (checkpoint.json)
- L2: 进度日志 (progress.jsonl)
- L3: 心跳文件 (heartbeat.txt)
- L4: 完成标记 (DONE)
"""

import os
import sys
import json
from datetime import datetime
from typing import Optional, Dict, Any

# 确保 unbuffered 输出
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(line_buffering=True)

class ProgressReporter:
    """多层进度汇报器"""

    def __init__(self, step: str, output_dir: str, total_items: int = 0, max_rounds: int = 1):
        self.step = step
        self.output_dir = output_dir
        self.total_items = total_items
        self.max_rounds = max_rounds
        self.current_round = 0
        self.processed_items = 0
        self.start_time = datetime.now()
        self.last_batch_time = None  # 用于计算批次时间增量

        # 文件路径
        self.checkpoint_path = os.path.join(output_dir, f"{step}_checkpoint.json")
        self.heartbeat_path = os.path.join(output_dir, f"{step}_heartbeat.txt")
        self.done_path = os.path.join(output_dir, f"{step}_DONE")
        self.progress_path = os.path.join(output_dir, f"{step}_progress.jsonl")

        # 确保目录存在
        os.makedirs(output_dir, exist_ok=True)

        # 清理旧标记
        for f in [self.checkpoint_path, self.heartbeat_path, self.done_path]:
            if os.path.exists(f):
                os.remove(f)

    def start(self, metadata: Dict[str, Any] = None):
        """记录开始"""
        self._write_progress("step_start", {
            "total_items": self.total_items,
            **(metadata or {})
        })
        self._write_heartbeat("started")
        self._print(f"🚀 [{self.step}] Starting - {self.total_items} items")

    def batch_start(self, batch_num: int, total_batches: int, batch_size: int):
        """记录批次开始"""
        self.last_batch_time = datetime.now()  # 记录批次开始时间
        
        self._write_progress("batch_start", {
            "batch_num": batch_num,
            "total_batches": total_batches,
            "batch_size": batch_size
        })
        self._write_heartbeat(f"batch_{batch_num}/{total_batches}")
        self._print(f"⏳ [{self.step}] Batch {batch_num}/{total_batches} starting ({batch_size} items)")

    def batch_complete(self, batch_num: int, total_batches: int,
                       success_count: int, failed_count: int = 0,
                       latency_ms: int = 0, metadata: Dict[str, Any] = None):
        """记录批次完成"""
        self.processed_items += success_count + failed_count

        self._write_progress("batch_complete", {
            "batch_num": batch_num,
            "total_batches": total_batches,
            "success_count": success_count,
            "failed_count": failed_count,
            "latency_ms": latency_ms,
            "processed_items": self.processed_items,
            **(metadata or {})
        })

        # 更新检查点
        self._write_checkpoint(batch_num, total_batches)

        # 更新心跳
        self._write_heartbeat(f"batch_{batch_num}/{total_batches}_done")

        # 计算时间增量和总耗时
        total_elapsed = (datetime.now() - self.start_time).total_seconds()
        batch_delta = 0
        if self.last_batch_time:
            batch_delta = (datetime.now() - self.last_batch_time).total_seconds()
        
        # 终端输出 (添加时间信息)
        pct = self.processed_items / self.total_items * 100 if self.total_items > 0 else 0
        self._print(f"✅ [{self.step}] Batch {batch_num}/{total_batches} | "
                   f"Success: {success_count}, Failed: {failed_count} | "
                   f"{self.processed_items}/{self.total_items} items | "
                   f"Delta: {batch_delta:.1f}s, Total: {total_elapsed:.1f}s")

    def round_complete(self, round_num: int, remaining_count: int):
        """记录轮次完成"""
        self._write_progress("round_complete", {
            "round": round_num,
            "remaining_count": remaining_count
        })
        self._print(f"🔄 [{self.step}] Round {round_num}/{self.max_rounds} | "
                   f"Remaining: {remaining_count} tasks")
        self._print("=" * 50)

    def item_complete(self, item_id: str, success: bool, metadata: Dict[str, Any] = None):
        """记录单项完成 (用于非批处理场景)"""
        self.processed_items += 1

        # 每 10 项更新一次心跳
        if self.processed_items % 10 == 0:
            self._write_heartbeat(f"item_{self.processed_items}/{self.total_items}")

            # 每 50 项更新一次检查点和终端输出
            if self.processed_items % 50 == 0:
                self._write_checkpoint(self.processed_items, self.total_items)
                pct = self.processed_items / self.total_items * 100 if self.total_items > 0 else 0
                self._print(f"📊 [{self.step}] Progress: {self.processed_items}/{self.total_items} ({pct:.1f}%)")

    def complete(self, success_count: int, failed_count: int = 0, metadata: Dict[str, Any] = None):
        """记录完成"""
        elapsed = (datetime.now() - self.start_time).total_seconds()

        self._write_progress("step_complete", {
            "success_count": success_count,
            "failed_count": failed_count,
            "elapsed_seconds": elapsed,
            **(metadata or {})
        })

        # 写入完成标记
        self._write_done(success_count, failed_count, elapsed)

        # 终端输出
        self._print(f"{'='*60}")
        self._print(f"✅ [{self.step}] Complete")
        self._print(f"   Success: {success_count}, Failed: {failed_count}")
        self._print(f"   Elapsed: {elapsed:.1f}s")
        self._print(f"{'='*60}")

    def error(self, error_msg: str, fatal: bool = False):
        """记录错误"""
        self._write_progress("error", {
            "error": error_msg,
            "fatal": fatal
        })
        self._write_heartbeat(f"error: {error_msg[:50]}")
        self._print(f"❌ [{self.step}] Error: {error_msg}")

        if fatal:
            self._write_done(0, self.total_items, 0, error=error_msg)

    def _write_progress(self, event: str, data: Dict[str, Any]):
        """写入进度日志 (L2)"""
        record = {
            "timestamp": datetime.now().isoformat(),
            "step": self.step,
            "event": event,
            **data
        }
        with open(self.progress_path, 'a', encoding='utf-8') as f:
            f.write(json.dumps(record, ensure_ascii=False) + '\n')

    def _write_checkpoint(self, current: int, total: int):
        """写入检查点 (L1)"""
        checkpoint = {
            "timestamp": datetime.now().isoformat(),
            "step": self.step,
            "current": current,
            "total": total,
            "processed_items": self.processed_items,
            "total_items": self.total_items,
            "elapsed_seconds": (datetime.now() - self.start_time).total_seconds()
        }
        with open(self.checkpoint_path, 'w', encoding='utf-8') as f:
            json.dump(checkpoint, f, indent=2)

    def _write_heartbeat(self, status: str):
        """写入心跳 (L3)"""
        with open(self.heartbeat_path, 'w') as f:
            f.write(f"{datetime.now().isoformat()} | {status}\n")

    def _write_done(self, success: int, failed: int, elapsed: float, error: str = None):
        """写入完成标记 (L4)"""
        with open(self.done_path, 'w') as f:
            f.write(f"Completed at {datetime.now().isoformat()}\n")
            f.write(f"Success: {success}\n")
            f.write(f"Failed: {failed}\n")
            f.write(f"Elapsed: {elapsed:.1f}s\n")
            if error:
                f.write(f"Error: {error}\n")

    def _print(self, msg: str):
        """终端输出 (强制刷新)"""
        print(msg)
        sys.stdout.flush()

def check_progress(output_dir: str, step: str) -> Dict[str, Any]:
    """
    检查步骤进度 (供 Agent 轮询使用)

    Returns:
        dict: {
            "status": "running" | "completed" | "error" | "unknown",
            "progress": float (0-100),
            "checkpoint": dict | None,
            "heartbeat_age_seconds": float | None
        }
    """
    result = {
        "status": "unknown",
        "progress": 0,
        "checkpoint": None,
        "heartbeat_age_seconds": None
    }

    done_path = os.path.join(output_dir, f"{step}_DONE")
    checkpoint_path = os.path.join(output_dir, f"{step}_checkpoint.json")
    heartbeat_path = os.path.join(output_dir, f"{step}_heartbeat.txt")

    # 检查完成标记
    if os.path.exists(done_path):
        result["status"] = "completed"
        result["progress"] = 100
        return result

    # 检查检查点
    if os.path.exists(checkpoint_path):
        with open(checkpoint_path) as f:
            checkpoint = json.load(f)
        result["checkpoint"] = checkpoint

        total = checkpoint.get("total_items", 0)
        processed = checkpoint.get("processed_items", 0)
        if total > 0:
            result["progress"] = processed / total * 100

    # 检查心跳
    if os.path.exists(heartbeat_path):
        mtime = os.path.getmtime(heartbeat_path)
        age = (datetime.now().timestamp() - mtime)
        result["heartbeat_age_seconds"] = age

        if age > 300:  # 5 分钟无心跳
            result["status"] = "stalled"
        else:
            result["status"] = "running"

    return result

if __name__ == "__main__":
    # 测试
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", help="Check progress for step")
    parser.add_argument("--output-dir", default=".")
    args = parser.parse_args()

    if args.check:
        result = check_progress(args.output_dir, args.check)
        print(json.dumps(result, indent=2))
