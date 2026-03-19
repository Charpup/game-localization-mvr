# 凭证配置指南(方案 B - PowerShell 自动加载)

## 配置完成 ✅

Agent 已自动完成所有配置,无需手动操作。

---

## 工作原理
```
项目目录/.env.ps1 (真实 API key)
    ↓
PowerShell $PROFILE 配置自动加载逻辑
    ↓
每次 cd 到项目目录 → 自动执行 .env.ps1
    ↓
环境变量加载到 PowerShell 会话
    ↓
docker-compose 继承环境变量
    ↓
Docker 容器内可用
```

---

## 日常使用

### 启动项目
```powershell
# 打开新的 PowerShell 窗口
cd D:\your\project\path  # 自动加载 .env.ps1

# 验证环境变量
echo $env:LLM_API_KEY  # 应显示: sk-2Ks9Tv...

# 启动 Docker
docker-compose up --build

# 或直接运行现有镜像
docker run -e LLM_API_KEY=$env:LLM_API_KEY -e LLM_BASE_URL=$env:LLM_BASE_URL your-image:tag
```

### 验证配置
```powershell
.\verify_setup.ps1
```

---

## 当前配置信息

- **API Key**: `sk-...`（请在本地凭证文件配置，避免落盘敏感值）
- **Base URL**: `https://api.apiyi.com/v1`
- **存储位置**: `.env.ps1` (本地,不进 Git)
- **加载方式**: PowerShell 自动加载
- **生效范围**: 当前 PowerShell 会话

### 文件化凭证加载（优先级）

- `LLM_API_KEY_FILE`（显式优先）
- `.llm_credentials`（推荐）
- `.llm_env`
- `config/llm_credentials.env`
- `~/.game-localization-mvr/.llm_credentials`
- `LLM_API_KEY` 环境变量（兜底）

可选：为避免会话误用，可在 PowerShell 启动时优先读取 `.llm_credentials`，并保留 `.env.ps1` 仅做备份加载。

## 依赖与环境校验（启动前必须执行）

```bash
pip install --upgrade requests numpy pandas pyyaml

python -c "import os; import requests, numpy, yaml; \
print('requests:', bool(requests)); \
print('numpy:', bool(numpy)); \
print('pandas:', bool(__import__(\"pandas\"))); \
print('LLM_BASE_URL:', bool(os.getenv('LLM_BASE_URL'))); \
print('LLM_API_KEY:', bool(os.getenv('LLM_API_KEY'))); \
print('LLM_MODEL:', bool(os.getenv('LLM_MODEL')))"
```

Windows PowerShell 快速校验：

```powershell
python -c "import os, importlib.util; print('requests:', bool(importlib.util.find_spec('requests'))); print('numpy:', bool(importlib.util.find_spec('numpy'))); print('pandas:', bool(importlib.util.find_spec('pandas'))); print('yaml:', bool(importlib.util.find_spec('yaml'))); print('LLM_BASE_URL:', 'SET' if os.getenv('LLM_BASE_URL') else 'MISSING'); print('LLM_API_KEY:', 'SET' if os.getenv('LLM_API_KEY') else 'MISSING'); print('LLM_MODEL:', os.getenv('LLM_MODEL', 'MISSING'))"

python scripts/llm_ping.py
```

### 建议启动前检查（1 分钟）

```bash
python -c "import os, importlib; [print(f'[OK] {pkg}' if importlib.util.find_spec(pkg) else f'[MISSING] {pkg}') for pkg in ['requests','numpy','pandas','yaml']]; [print(f'{key}:', 'SET' if os.getenv(key) else 'MISSING') for key in ['LLM_BASE_URL','LLM_API_KEY','LLM_MODEL']]"

python scripts/test_e2e_workflow.py
python scripts/translate_llm.py --input "D:\\Dev_Env\\loc-mvr 测试文档\\test_input_200-row.csv" --output /tmp/translation_smoke.csv --style workflow/style_guide.md --glossary workflow/smoke_glossary_approved.yaml --target-lang ru-RU --model claude-haiku-4-5-20251001 --checkpoint data/smoke_checkpoint_200.json
```

---

## 修改 API Key
```powershell
# 编辑 .env.ps1 文件
notepad .env.ps1

# 保存后,重新进入项目目录
cd ..
cd .\project

# 或手动重新加载
. .\.env.ps1
```

---

## 复用到其他机器

### 方式 1: 重新运行 Agent 配置脚本

在新机器的项目目录执行相同的 Agent 配置指令即可。

### 方式 2: 手动配置(快速)
```powershell
# 1. 复制项目中的 .env.ps1 文件(已存在)

# 2. 在新机器的 PowerShell 配置文件添加自动加载逻辑
notepad $PROFILE

# 粘贴以下内容:
function Load-ProjectEnv {
    $envFile = Join-Path $PWD ".env.ps1"
    if (Test-Path $envFile) {
        . $envFile
    }
}

$global:__LastPwd = $PWD
function prompt {
    if ($global:__LastPwd -ne $PWD) {
        $global:__LastPwd = $PWD
        Load-ProjectEnv
    }
    "PS $($executionContext.SessionState.Path.CurrentLocation)$('>' * ($nestedPromptLevel + 1)) "
}

Load-ProjectEnv

# 3. 重启 PowerShell
```

---

## 安全检查清单

- ✅ `.env.ps1` 文件已添加到 `.gitignore`
- ✅ Git 历史中无 `.env` 相关文件
- ✅ PowerShell 自动加载已配置
- ✅ API key 仅存储在本地

---

## 故障排查

### 问题 1: 打开新 PowerShell 窗口,环境变量未加载

**原因**: 可能未切换到项目目录

**解决**:
```powershell
cd D:\your\project\path  # 确保在项目根目录
echo $env:LLM_API_KEY     # 验证
```

### 问题 2: Docker 容器内获取不到环境变量

**原因**: docker-compose.yml 未配置环境变量继承

**解决**:
```yaml
services:
  agent:
    environment:
      - LLM_API_KEY=${LLM_API_KEY}
      - LLM_BASE_URL=${LLM_BASE_URL}
```

### 问题 3: 自动加载不生效

**解决**:
```powershell
# 重新加载 PowerShell 配置
. $PROFILE

# 手动加载当前项目
. .\.env.ps1
```

---

## 卸载配置(可选)
```powershell
# 1. 编辑 PowerShell 配置文件
notepad $PROFILE

# 2. 删除 "Auto-load project .env.ps1" 相关代码块

# 3. 删除项目中的 .env.ps1 文件
Remove-Item .env.ps1
```

