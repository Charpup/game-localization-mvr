#!/bin/bash

# 检查环境变量
if [ -z "$LLM_API_KEY" ]; then
    echo "错误: LLM_API_KEY 环境变量未设置"
    echo "请先执行: export LLM_API_KEY='your_key'"
    exit 1
fi

# 设置默认 base_url(如果未提供)
export LLM_BASE_URL=${LLM_BASE_URL:-https://api.apiyi.com/v1}

echo "使用配置:"
echo "  Base URL: $LLM_BASE_URL"
echo "  API Key: ${LLM_API_KEY:0:10}..."

# 启动容器
docker-compose up --build
