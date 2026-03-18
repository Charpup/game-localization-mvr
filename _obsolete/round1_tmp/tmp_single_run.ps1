Set-Location "D:\Dev_Env\GPT_Codex_Workspace\game-localization-mvr\main_worktree"
$runRoot = "D:\Dev_Env\GPT_Codex_Workspace\game-localization-mvr\main_worktree\data\smoke_runs\manual_305833_single_20260318_031700"
$runDir = Join-Path $runRoot "run"
$src = "D:\Dev_Env\loc-mvr 测试文档\test_input_200-row.csv"
$inCsv = Join-Path $runRoot "single_305833.csv"

if (Test-Path $runRoot) { Remove-Item -Recurse -Force $runRoot }
New-Item -ItemType Directory -Force -Path $runRoot | Out-Null

Import-Csv $src | Where-Object { $_.string_id -eq '305833' } | Export-Csv $inCsv -NoTypeInformation -Encoding utf8

$env:LLM_BASE_URL = "https://api.apiyi.com/v1"
$env:LLM_API_KEY = "sk-s8sGLqwQxcj8qXHyDf6b3b4bD3964285A02cC94c09323c2e"
$env:LLM_MODEL = "gpt-4.1-nano"

python scripts/run_smoke_pipeline.py --input $inCsv --run-dir $runRoot --target-lang en-US --verify-mode full
