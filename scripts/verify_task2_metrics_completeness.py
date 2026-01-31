#!/usr/bin/env python3
"""验证 Task 2: Metrics 完整性"""
import os
import sys
import json
from pathlib import Path


def verify_metrics_completeness():
    print("=== Task 2 验证: Metrics 完整性 ===\n")
    
    # 1. 检查 trace_config.py 是否存在
    print("1. 检查 trace_config.py...")
    trace_config_path = "scripts/trace_config.py"
    
    if not os.path.exists(trace_config_path):
        print(f"❌ {trace_config_path} 不存在")
        return False
    
    print(f"   ✓ {trace_config_path} 存在")
    
    # 2. 测试 trace_config 模块
    print("\n2. 测试 trace_config 模块...")
    try:
        sys.path.insert(0, "scripts")
        from trace_config import setup_trace_path, get_trace_path
        
        # 测试设置 trace 路径
        test_dir = "data/test_metrics"
        Path(test_dir).mkdir(parents=True, exist_ok=True)
        
        trace_path = setup_trace_path(test_dir)
        
        if not trace_path:
            print("❌ setup_trace_path 返回空值")
            return False
        
        print(f"   ✓ setup_trace_path 返回: {trace_path}")
        
        # 验证环境变量
        env_path = os.getenv("LLM_TRACE_PATH")
        if env_path != trace_path:
            print(f"❌ 环境变量不一致: {env_path} != {trace_path}")
            return False
        
        print(f"   ✓ 环境变量 LLM_TRACE_PATH 正确设置")
        
        # 验证 get_trace_path
        retrieved_path = get_trace_path()
        if retrieved_path != trace_path:
            print(f"❌ get_trace_path 返回不一致: {retrieved_path} != {trace_path}")
            return False
        
        print(f"   ✓ get_trace_path 返回正确")
        
    except Exception as e:
        print(f"❌ trace_config 模块测试失败: {e}")
        return False
    
    # 3. 检查 runtime_adapter.py 的 trace 功能
    print("\n3. 检查 runtime_adapter.py trace 功能...")
    
    with open("scripts/runtime_adapter.py", "r", encoding="utf-8") as f:
        adapter_content = f.read()
    
    if "_trace" not in adapter_content:
        print("❌ runtime_adapter.py 缺少 _trace 函数")
        return False
    
    print("   ✓ runtime_adapter.py 包含 _trace 函数")
    
    if "LLM_TRACE_PATH" not in adapter_content:
        print("❌ runtime_adapter.py 未使用 LLM_TRACE_PATH")
        return False
    
    print("   ✓ runtime_adapter.py 使用 LLM_TRACE_PATH")
    
    # 4. 检查 metrics_aggregator.py
    print("\n4. 检查 metrics_aggregator.py...")
    
    if not os.path.exists("scripts/metrics_aggregator.py"):
        print("❌ metrics_aggregator.py 不存在")
        return False
    
    with open("scripts/metrics_aggregator.py", "r", encoding="utf-8") as f:
        aggregator_content = f.read()
    
    if "load_trace_logs" not in aggregator_content:
        print("❌ metrics_aggregator.py 缺少 load_trace_logs 函数")
        return False
    
    print("   ✓ metrics_aggregator.py 包含 load_trace_logs 函数")
    
    # 5. 检查 Docker 脚本的 trace 支持
    print("\n5. 检查 Docker 脚本 trace 支持...")
    
    docker_scripts = ["scripts/docker_run.ps1", "scripts/docker_run.sh"]
    for script in docker_scripts:
        if not os.path.exists(script):
            print(f"❌ {script} 不存在")
            return False
        
        with open(script, "r", encoding="utf-8") as f:
            content = f.read()
        
        if "LLM_TRACE_PATH" not in content:
            print(f"❌ {script} 未支持 LLM_TRACE_PATH")
            return False
        
        print(f"   ✓ {script} 支持 LLM_TRACE_PATH")
    
    # 6. 模拟 trace 写入测试
    print("\n6. 模拟 trace 写入测试...")
    
    test_trace_path = os.path.join(test_dir, "test_trace.jsonl")
    os.environ["LLM_TRACE_PATH"] = test_trace_path
    
    # 导入 runtime_adapter 并测试 _trace
    try:
        from runtime_adapter import _trace
        
        # 写入测试事件
        test_event = {
            "type": "test_event",
            "step": "verify_metrics",
            "message": "Test trace write"
        }
        
        _trace(test_event)
        
        # 验证文件是否创建
        if not os.path.exists(test_trace_path):
            print(f"❌ Trace 文件未创建: {test_trace_path}")
            return False
        
        # 读取并验证内容
        with open(test_trace_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        
        if not lines:
            print("❌ Trace 文件为空")
            return False
        
        # 解析第一行
        event = json.loads(lines[0])
        
        if event.get("type") != "test_event":
            print(f"❌ Trace 事件类型不匹配: {event.get('type')}")
            return False
        
        if "timestamp" not in event:
            print("❌ Trace 事件缺少 timestamp")
            return False
        
        print(f"   ✓ Trace 写入测试通过")
        print(f"   ✓ Trace 文件: {test_trace_path}")
        
    except Exception as e:
        print(f"❌ Trace 写入测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    print("\n✅ Task 2 验证通过: Metrics 完整性已实现")
    print("\n修复说明:")
    print("  - 创建 trace_config.py 统一管理 trace 路径")
    print("  - runtime_adapter.py 支持 LLM_TRACE_PATH 环境变量")
    print("  - Docker 脚本支持 trace 路径传递")
    print("  - metrics_aggregator.py 可聚合 trace 数据")
    print("  - 所有 LLM 调用将写入统一的 trace 文件")
    
    return True


if __name__ == '__main__':
    sys.exit(0 if verify_metrics_completeness() else 1)
