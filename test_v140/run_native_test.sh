#!/bin/bash
# 启动原生工具测试

cd /root/.openclaw/workspace/projects/game-localization-mvr

export LLM_BASE_URL=https://api.apiyi.com/v1
export LLM_API_KEY=sk-s8sGLqwQxcj8qXHyDf6e3b4bD3964285A02cC94c09323c2e
export LLM_MODEL=kimi-k2.5

echo "=========================================="
echo "启动原生工具测试"
echo "开始时间: $(date)"
echo "=========================================="

python3 src/scripts/run_validation.py \
  --model kimi-k2.5 \
  --rows 500 \
  --input test_v140/workflow/normalized_input.csv \
  --output-dir test_v140/output \
  --report-dir test_v140/reports \
  2>&1 | tee test_v140/output/native_validation.log