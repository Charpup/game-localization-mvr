Set-Location "D:\Dev_Env\GPT_Codex_Workspace\game-localization-mvr\main_worktree"
$env:LLM_BASE_URL = "https://api.apiyi.com/v1"
$env:LLM_API_KEY = ""
$env:LLM_API_KEY = (Get-Content "D:\Dev_Env\GPT_Codex_Workspace\game-localization-mvr\main_worktree\main\temp_noexist" -ErrorAction SilentlyContinue)
if ([string]::IsNullOrWhiteSpace($env:LLM_API_KEY)) {
    Write-Output "WARN: no API key from script. attempting use existing environment."
}

$in = "D:\Dev_Env\loc-mvr 测试文档\test_input_200-row.csv"
$base = "D:\Dev_Env\GPT_Codex_Workspace\game-localization-mvr\main_worktree\data\smoke_runs"
$pre = Join-Path $base "manual_200_preflight_20260318_031700b"
$full = Join-Path $base "manual_200_full_20260318_031700b"

if (Test-Path $pre) { Remove-Item -Recurse -Force $pre }
if (Test-Path $full) { Remove-Item -Recurse -Force $full }

python scripts/run_smoke_pipeline.py --input $in --run-dir $pre --target-lang en-US --verify-mode preflight
python scripts/run_smoke_pipeline.py --input $in --run-dir $full --target-lang en-US --verify-mode full
