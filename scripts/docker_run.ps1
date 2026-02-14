#!/usr/bin/env pwsh
# Docker 运行模板 - 正确注入 API Keys
# 用法: .\docker_run.ps1 <command> [args...]
# 示例: .\docker_run.ps1 python scripts/translate_llm.py --input data/input.csv --output data/output.csv

param(
    [Parameter(Mandatory = $true, Position = 0, ValueFromRemainingArguments = $true)]
    [string[]]$Command
)

# 检查必需的环境变量
if (-not $env:LLM_API_KEY) {
    Write-Host "❌ Error: LLM_API_KEY environment variable is not set" -ForegroundColor Red
    Write-Host "   Please set it first:" -ForegroundColor Yellow
    Write-Host '   $env:LLM_API_KEY="your_api_key_here"' -ForegroundColor Yellow
    exit 1
}

# 设置默认值
if (-not $env:LLM_BASE_URL) {
    $env:LLM_BASE_URL = "https://api.apiyi.com/v1"
    Write-Host "ℹ️  Using default LLM_BASE_URL: $env:LLM_BASE_URL" -ForegroundColor Cyan
}

# 构建 Docker 命令
$dockerArgs = @(
    "run",
    "--rm",
    "-v", "${PWD}:/workspace",
    "-w", "/workspace",
    "-e", "LLM_API_KEY=$env:LLM_API_KEY",
    "-e", "LLM_BASE_URL=$env:LLM_BASE_URL",
    "-e", "LLM_API_KEY_FILE="
)

# 添加可选的环境变量
if ($env:LLM_TRACE_PATH) {
    $dockerArgs += "-e", "LLM_TRACE_PATH=$env:LLM_TRACE_PATH"
}

# 添加镜像名和命令
$dockerArgs += "gate_v2"
$dockerArgs += $Command

# 显示执行的命令
Write-Host "🐳 Running Docker command:" -ForegroundColor Green
Write-Host "   docker $($dockerArgs -join ' ')" -ForegroundColor Gray
Write-Host ""

# 执行 Docker 命令
& docker @dockerArgs
