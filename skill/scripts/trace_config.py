#!/usr/bin/env python3
"""
Trace Configuration Helper - 确保所有阶段使用统一的 trace 路径

用法:
    from trace_config import setup_trace_path
    
    # 在脚本开始时调用
    setup_trace_path(output_dir="data/test_outputs")
    
    # 之后所有 LLMClient 调用都会写入统一的 trace 文件
"""

import os
from pathlib import Path


def setup_trace_path(output_dir: str = ".", trace_filename: str = "llm_trace.jsonl") -> str:
    """
    设置统一的 LLM trace 路径
    
    Args:
        output_dir: 输出目录（默认当前目录）
        trace_filename: Trace 文件名（默认 llm_trace.jsonl）
    
    Returns:
        设置的 trace 路径（绝对路径）
    
    Side Effects:
        设置环境变量 LLM_TRACE_PATH
    """
    # 确保输出目录存在
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    # 构建 trace 路径（绝对路径）
    trace_path = os.path.abspath(os.path.join(output_dir, trace_filename))
    
    # 设置环境变量
    os.environ["LLM_TRACE_PATH"] = trace_path
    
    print(f"📊 LLM Trace Path: {trace_path}")
    
    return trace_path


def get_trace_path() -> str:
    """
    获取当前的 trace 路径
    
    Returns:
        当前设置的 trace 路径，如果未设置则返回默认值
    """
    return os.getenv("LLM_TRACE_PATH", "data/llm_trace.jsonl")


def clear_trace_file(output_dir: str = ".", trace_filename: str = "llm_trace.jsonl") -> None:
    """
    清空 trace 文件（用于新的测试运行）
    
    Args:
        output_dir: 输出目录
        trace_filename: Trace 文件名
    """
    trace_path = os.path.join(output_dir, trace_filename)
    
    if os.path.exists(trace_path):
        os.remove(trace_path)
        print(f"🗑️  Cleared trace file: {trace_path}")
    else:
        print(f"ℹ️  Trace file does not exist: {trace_path}")


if __name__ == "__main__":
    # 测试
    import sys
    
    if len(sys.argv) > 1:
        output_dir = sys.argv[1]
    else:
        output_dir = "data"
    
    trace_path = setup_trace_path(output_dir)
    print(f"✅ Trace path configured: {trace_path}")
    print(f"   Environment variable LLM_TRACE_PATH = {os.getenv('LLM_TRACE_PATH')}")
