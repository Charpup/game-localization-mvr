#!/bin/bash
# Loc-MVR v1.4.0 原生工具测试 - 自主监控脚本
# 监控间隔: 5分钟检查, 15分钟汇报

cd /root/.openclaw/workspace/projects/game-localization-mvr

LOG_FILE="test_v140/output/monitor_auto.log"
REPORT_FILE="test_v140/output/progress_report.log"
LAST_REPORT_TIME=0
REPORT_INTERVAL=900  # 15分钟
CHECK_INTERVAL=300   # 5分钟

echo "==========================================" | tee -a $LOG_FILE
echo "自主监控启动: $(date)" | tee -a $LOG_FILE
echo "监控间隔: ${CHECK_INTERVAL}秒 (5分钟)" | tee -a $LOG_FILE
echo "汇报间隔: ${REPORT_INTERVAL}秒 (15分钟)" | tee -a $LOG_FILE
echo "==========================================" | tee -a $LOG_FILE

while true; do
    sleep $CHECK_INTERVAL
    
    CURRENT_TIME=$(date +%s)
    TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
    
    # 1. 检查进程状态
    if pgrep -f "run_validation.py" > /dev/null; then
        STATUS="运行中"
    else
        STATUS="已停止"
        echo "[$TIMESTAMP] ⚠️ 警告: 进程已停止!" | tee -a $LOG_FILE
        # 立即汇报异常
        echo "[$TIMESTAMP] 紧急: 测试进程异常停止" >> $REPORT_FILE
    fi
    
    # 2. 检查日志进度
    if [ -f "test_v140/output/native_validation.log" ]; then
        # 获取最新进度
        LATEST_BATCH=$(grep -o "Batch [0-9]*/[0-9]*" test_v140/output/native_validation.log | tail -1)
        if [ -n "$LATEST_BATCH" ]; then
            echo "[$TIMESTAMP] 进度: $LATEST_BATCH | 状态: $STATUS" >> $LOG_FILE
        fi
        
        # 检查错误
        ERROR_COUNT=$(grep -c "Error\|ERROR\|Failed" test_v140/output/native_validation.log 2>/dev/null || echo "0")
        if [ "$ERROR_COUNT" -gt 0 ]; then
            echo "[$TIMESTAMP] ⚠️ 发现 $ERROR_COUNT 个错误" | tee -a $LOG_FILE
        fi
    fi
    
    # 3. 检查输出文件
    if [ -f "test_v140/output/translated.csv" ]; then
        ROWS=$(wc -l < test_v140/output/translated.csv)
        echo "[$TIMESTAMP] 输出文件: $ROWS 行" >> $LOG_FILE
    fi
    
    # 4. 15分钟汇报
    TIME_DIFF=$((CURRENT_TIME - LAST_REPORT_TIME))
    if [ $TIME_DIFF -ge $REPORT_INTERVAL ]; then
        echo "" >> $REPORT_FILE
        echo "========================================" >> $REPORT_FILE
        echo "进度汇报: $TIMESTAMP" >> $REPORT_FILE
        echo "========================================" >> $REPORT_FILE
        
        # 详细统计
        if [ -f "test_v140/output/native_validation.log" ]; then
            TOTAL_BATCHES=$(grep -c "Batch" test_v140/output/native_validation.log 2>/dev/null || echo "0")
            COMPLETED=$(grep -c "✓\|complete\|success" test_v140/output/native_validation.log 2>/dev/null || echo "0")
            echo "已完成批次: $COMPLETED / 50" >> $REPORT_FILE
            echo "完成度: $((COMPLETED * 100 / 50))%" >> $REPORT_FILE
        fi
        
        echo "进程状态: $STATUS" >> $REPORT_FILE
        echo "日志文件: test_v140/output/native_validation.log" >> $REPORT_FILE
        echo "" >> $REPORT_FILE
        
        LAST_REPORT_TIME=$CURRENT_TIME
        echo "[$TIMESTAMP] 📊 已生成15分钟汇报" >> $LOG_FILE
    fi
done
