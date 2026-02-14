#!/usr/bin/env python3
"""验证 Task 3: Progress 时间戳"""
import os
import sys
import time
import shutil
from pathlib import Path


def verify_progress_timestamps():
    print("=== Task 3 验证: Progress 时间戳 ===\n")
    
    # 1. 检查 progress_reporter.py 修改
    print("1. 检查 progress_reporter.py 修改...")
    
    with open("scripts/progress_reporter.py", "r", encoding="utf-8") as f:
        content = f.read()
    
    if "last_batch_time" not in content:
        print("❌ progress_reporter.py 缺少 last_batch_time 字段")
        return False
    
    print("   ✓ last_batch_time 字段已添加")
    
    if "Delta:" not in content or "Total:" not in content:
        print("❌ progress_reporter.py 缺少 Delta/Total 时间显示")
        return False
    
    print("   ✓ Delta/Total 时间显示已添加")
    
    # 2. 测试 ProgressReporter 功能
    print("\n2. 测试 ProgressReporter 功能...")
    
    test_dir = "data/test_progress"
    Path(test_dir).mkdir(parents=True, exist_ok=True)
    
    # 清理旧文件
    for f in Path(test_dir).glob("test_*"):
        f.unlink()
    
    try:
        sys.path.insert(0, "scripts")
        from progress_reporter import ProgressReporter
        
        # 创建 reporter
        reporter = ProgressReporter(
            step="test",
            output_dir=test_dir,
            total_items=100
        )
        
        # 验证初始化
        if not hasattr(reporter, 'last_batch_time'):
            print("❌ ProgressReporter 缺少 last_batch_time 属性")
            return False
        
        print("   ✓ ProgressReporter 初始化成功")
        
        # 测试 start
        reporter.start()
        
        # 测试 batch_start 和 batch_complete
        reporter.batch_start(1, 3, 30)
        
        # 等待一小段时间以产生时间增量
        time.sleep(0.5)
        
        reporter.batch_complete(
            batch_num=1,
            total_batches=3,
            success_count=28,
            failed_count=2,
            latency_ms=500
        )
        
        # 验证 progress.jsonl 是否包含时间戳
        progress_path = os.path.join(test_dir, "test_progress.jsonl")
        
        if not os.path.exists(progress_path):
            print(f"❌ Progress 文件未创建: {progress_path}")
            return False
        
        with open(progress_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        
        if not lines:
            print("❌ Progress 文件为空")
            return False
        
        # 验证每行都有 timestamp
        import json
        for line in lines:
            event = json.loads(line)
            if "timestamp" not in event:
                print(f"❌ Progress 事件缺少 timestamp: {event}")
                return False
        
        print(f"   ✓ Progress 日志包含 {len(lines)} 个事件，均有 timestamp")
        
        # 测试第二个批次以验证时间增量
        reporter.batch_start(2, 3, 30)
        time.sleep(0.3)
        reporter.batch_complete(
            batch_num=2,
            total_batches=3,
            success_count=30,
            failed_count=0,
            latency_ms=300
        )
        
        # 完成
        reporter.complete(success_count=58, failed_count=2)
        
        # 验证 DONE 文件
        done_path = os.path.join(test_dir, "test_DONE")
        
        if not os.path.exists(done_path):
            print(f"❌ DONE 文件未创建: {done_path}")
            return False
        
        with open(done_path, "r", encoding="utf-8") as f:
            done_content = f.read()
        
        if "Elapsed:" not in done_content:
            print("❌ DONE 文件缺少 Elapsed 信息")
            return False
        
        print("   ✓ DONE 文件包含 Elapsed 信息")
        
    except Exception as e:
        print(f"❌ ProgressReporter 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    print("\n✅ Task 3 验证通过: Progress 时间戳已实现")
    print("\n修复说明:")
    print("  - 添加 last_batch_time 追踪批次开始时间")
    print("  - batch_complete 显示 Delta (批次耗时) 和 Total (总耗时)")
    print("  - 所有进度事件包含 ISO 8601 时间戳")
    print("  - 提升监控体验，便于性能分析")
    
    return True


if __name__ == '__main__':
    sys.exit(0 if verify_progress_timestamps() else 1)
