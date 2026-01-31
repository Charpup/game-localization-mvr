#!/bin/bash
# Docker 运行模板 - 正确注入 API Keys (Linux/Mac)
# 用法: ./docker_run.sh <command> [args...]
# 示例: ./docker_run.sh python scripts/translate_llm.py --input data/input.csv --output data/output.csv

# 检查必需的环境变量
if [ -z "$LLM_API_KEY" ]; then
    echo "❌ Error: LLM_API_KEY environment variable is not set"
    echo "   Please set it first:"
    echo '   export LLM_API_KEY="your_api_key_here"'
    exit 1
fi

# 设置默认值
if [ -z "$LLM_BASE_URL" ]; then
    export LLM_BASE_URL="https://api.apiyi.com/v1"
    echo "ℹ️  Using default LLM_BASE_URL: $LLM_BASE_URL"
fi

# 构建 Docker 命令
DOCKER_CMD="docker run --rm \
  -v \${PWD}:/workspace \
  -w /workspace \
  -e LLM_API_KEY=\"\${LLM_API_KEY}\" \
  -e LLM_BASE_URL=\"\${LLM_BASE_URL}\""

# 添加可选的环境变量
if [ -n "$LLM_TRACE_PATH" ]; then
    DOCKER_CMD="$DOCKER_CMD -e LLM_TRACE_PATH=\"\${LLM_TRACE_PATH}\""
fi

# 添加镜像名和命令
DOCKER_CMD="$DOCKER_CMD loc-mvr $@"

# 显示执行的命令
echo "🐳 Running Docker command:"
echo "   $DOCKER_CMD"
echo ""

# 执行 Docker 命令
eval $DOCKER_CMD
