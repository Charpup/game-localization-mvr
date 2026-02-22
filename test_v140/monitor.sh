#!/bin/bash
# 自动监控翻译进度

cd /root/.openclaw/workspace/projects/game-localization-mvr/test_v140/output

echo "🔥 开始监控翻译进度 (每 30 秒)"
echo "开始时间: $(date)"
echo "================================"

while true; do
    sleep 30
    
    # Check progress
    python3 << 'EOF' 2>/dev/null
import pandas as pd
import os

try:
    df = pd.read_csv('translated_reliable.csv')
    success = len(df[df['status'] == 'success'])
    pending = len(df[df['status'] == 'pending'])
    total = len(df)
    progress = success / total * 100
    
    print(f"[{success}/{total}] {progress:.1f}% | 剩余: {pending} 行")
    
    if pending == 0:
        print("✅ 翻译完成！")
        exit(0)
except:
    pass
EOF

    # Check if process is still running
    if ! pgrep -f "reliable_batch" > /dev/null; then
        echo "⚠️  翻译进程已停止"
        break
    fi
done

echo "================================"
echo "结束时间: $(date)"
