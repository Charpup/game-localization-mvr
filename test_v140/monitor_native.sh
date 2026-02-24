#!/bin/bash
# 原生工具测试监控脚本

cd /root/.openclaw/workspace/projects/game-localization-mvr

echo "=========================================="
echo "Loc-MVR v1.4.0 原生工具测试监控"
echo "启动时间: $(date)"
echo "=========================================="

# 监控间隔（秒）
INTERVAL=60

while true; do
    sleep $INTERVAL
    
    echo ""
    echo "[$(date '+%H:%M:%S')] 检查任务状态..."
    
    # 检查输出文件
    if [ -f "test_v140/output/translated_native.csv" ]; then
        ROWS=$(wc -l < test_v140/output/translated_native.csv)
        echo "  - 翻译输出: $ROWS 行"
    fi
    
    # 检查 QA 报告
    if [ -f "test_v140/reports/qa_report.json" ]; then
        echo "  - QA 报告: 已生成"
    fi
    
    # 检查进程
    if pgrep -f "batch_runtime" > /dev/null; then
        echo "  - batch_runtime: 运行中"
    fi
    
    if pgrep -f "qa_hard" > /dev/null; then
        echo "  - qa_hard: 运行中"
    fi
    
    if pgrep -f "soft_qa" > /dev/null; then
        echo "  - soft_qa: 运行中"
    fi
    
    # 记录到日志
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] 监控检查完成" >> test_v140/monitor_native.log
done
