#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
verify_multi_models_metrics.py
验证 5 个指定模型的 LLM 调用连通性，并触发 Metrics 路径进行费用对账。
"""
import os
import sys
import time
from pathlib import Path
from datetime import datetime

# 确保脚本路径在 Python 路径中
sys.path.append(str(Path(__file__).parent.parent / "scripts"))

try:
    from runtime_adapter import LLMClient
    from cost_monitor import CostMonitor
    import json
except ImportError as e:
    print(f"❌ 导入失败: {e}")
    sys.exit(1)

# 配置路径
API_KEY_FILE = r"C:\Users\bob_c\.gemini\antigravity\auto_Localization\data\attachment\api_key.txt"
ACCESS_TOKEN_FILE = r"C:\Users\bob_c\.gemini\antigravity\auto_Localization\data\attachment\api access token.txt"
BASE_URL = "https://api.apiyi.com/v1"
TRACE_PATH = r"C:\Users\bob_c\.gemini\antigravity\auto_Localization\data\llm_trace.jsonl"

# 待测试模型列表
MODELS = [
    "gpt-5.2",
    "claude-haiku-4-5-20251001-thinking",
    "DeepSeek-V3.2-Exp-thinking",
    "gemini-2.5-flash",
    "glm-4.5-flash"
]

def setup_environment():
    """设置环境变量及 API Key 文件路径"""
    print("🛠️ 正在设置测试环境...")
    os.environ["LLM_BASE_URL"] = BASE_URL
    os.environ["LLM_API_KEY_FILE"] = API_KEY_FILE
    os.environ["LLM_TRACE_PATH"] = TRACE_PATH
    os.environ["LLM_RUN_ID"] = f"verify_run_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    # 检查文件是否存在
    if not Path(API_KEY_FILE).exists():
        print(f"⚠️ 警告: API Key 文件不存在: {API_KEY_FILE}")
    if not Path(ACCESS_TOKEN_FILE).exists():
        print(f"⚠️ 警告: Access Token 文件不存在: {ACCESS_TOKEN_FILE}")
    else:
        print(f"✅ 环境设置完成。运行 ID: {os.environ['LLM_RUN_ID']}")

def run_multi_model_test():
    """执行多模型调用测试"""
    setup_environment()
    
    # 先设置环境变量，再初始化
    monitor = CostMonitor(BASE_URL, os.environ["LLM_RUN_ID"])
    llm = LLMClient()
    
    print(f"\n🚀 开始对 {len(MODELS)} 个模型进行逐一调用测试...")
    
    for model_name in MODELS:
        print(f"\n--- 测试模型: {model_name} ---")
        try:
            start_ts = time.time()
            # 执行极简调用
            response = llm.chat(
                system="You are a helpful assistant.",
                user="Hello! Please reply with exactly one word: Success.",
                metadata={"step": "verify_multi_model", "model_override": model_name}
            )
            elapsed = time.time() - start_ts
            
            print(f"✅ 调用成功 | 耗时: {elapsed:.2f}s | 响应: {response.text.strip()}")
            
            # 手动刷入 monitor 计数
            monitor.on_llm_call()
            
        except Exception as e:
            print(f"❌ 调用失败 ({model_name}): {str(e)}")

    print("\n" + "="*60)
    print("等待日志落地...")
    time.sleep(2)
    
    print("📊 生成最终费用对账快照...")
    snapshot_path = monitor.snapshot(reason="verify_complete")
    
    if snapshot_path:
        print(f"✅ 快照已保存: {snapshot_path}")
        try:
            with open(snapshot_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                apiyi = data.get("apiyi", {})
                recon = data.get("reconciliation", {})
                local = data.get("local", {})
                
                print("\n💰 对账摘要:")
                print(f"   本地总请求记录: {local.get('total_calls', 0)}")
                print(f"   APIyi 总余额报告: ${apiyi.get('cumulative_used_usd', 'n/a')}")
                print(f"   本次会话 APIyi 扣费: ${apiyi.get('total_cost_usd_reported', 0)}")
                print(f"   本地预估总消耗: ${local.get('total_cost_usd_est', 0)}")
                print(f"   费用偏差 (Delta): ${recon.get('delta_usd', 0)} ({recon.get('delta_ratio', 0)*100:.2f}%)")
        except Exception as e:
            print(f"⚠️ 读取快照失败: {e}")

if __name__ == "__main__":
    run_multi_model_test()
