# GitHub 上传操作手册

## 项目信息

- **项目名称**: Game Localization MVR Workflow v2.0
- **本地路径**: `c:\Users\bob_c\.gemini\antigravity\playground\loc-mvr`
- **GitHub 用户**: Charpup
- **仓库名称**: game-localization-mvr
- **仓库 URL**: https://github.com/Charpup/game-localization-mvr

## 前提条件

确认 Git 已安装：
```powershell
git --version
```

如果未安装，使用 winget 安装：
```powershell
winget install Git.Git
```

## 操作步骤

### 一、本地仓库准备

#### 1. 进入项目目录
```powershell
cd c:\Users\bob_c\.gemini\antigravity\playground\loc-mvr
```

#### 2. 检查 Git 状态
```powershell
git status
```

如果尚未初始化，运行：
```powershell
git init
git add .
git commit -m "Update to v2.0: Term extraction + Schema v2.0 + Core scripts upgrade"
```

#### 3. 查看当前改动（如果已有仓库）
```powershell
git status
git diff
```

### 二、提交最新改动

#### 1. 添加所有新文件和修改
```powershell
git add .
```

#### 2. 查看将要提交的内容
```powershell
git status
```

#### 3. 提交改动
```powershell
git commit -m "v2.0 Update: Major workflow improvements

- Added term extraction with jieba integration (extract_terms.py)
- Upgraded placeholder_schema to v2.0 with paired_tags
- Enhanced forbidden_patterns with 20 rules
- Upgraded normalize_guard to v2.0 with token reuse
- Upgraded qa_hard to v2.0 with paired_tags validation
- All tests passing"
```

### 三、推送到 GitHub

#### 1. 检查远程仓库
```powershell
git remote -v
```

如果没有远程仓库，添加：
```powershell
git remote add origin https://github.com/Charpup/game-localization-mvr.git
```

#### 2. 设置主分支
```powershell
git branch -M main
```

#### 3. 推送到 GitHub
```powershell
git push -u origin main
```

如果提示认证，使用 **Personal Access Token (PAT)**：
- Username: `Charpup`
- Password: 粘贴你的 PAT（不是 GitHub 密码）

### 四、验证上传

访问仓库：https://github.com/Charpup/game-localization-mvr

检查：
- ✅ 最新提交时间正确
- ✅ v2.0 新增文件全部存在
- ✅ README.md 正确显示

## v2.0 新增文件清单

### 新增核心脚本
- `scripts/extract_terms.py` - 术语提取
- `scripts/test_extract_terms.py` - 术语提取测试
- `scripts/test_forbidden_patterns.py` - 禁用模式测试

### 新增数据文件
- `data/glossary.yaml` - 术语表（9个术语）
- `data/term_candidates.yaml` - 术语候选
- `data/translated.csv` - 翻译示例

### 更新的核心脚本
- `scripts/normalize_guard.py` → v2.0（Token 重用 + 早期检查）
- `scripts/qa_hard.py` → v2.0（Paired Tags + 性能优化）

### 更新的配置文件
- `workflow/placeholder_schema.yaml` → v2.0（patterns + paired_tags）
- `workflow/forbidden_patterns.txt` → 20 规则

### 新增文档
- `docs/extract_terms_usage.md` - 术语提取使用文档

## 常见问题

### Q: 推送时显示 "error: failed to push"

**A**: 可能是远程仓库有更新，先拉取：
```powershell
git pull origin main --rebase
git push -u origin main
```

### Q: 需要 Personal Access Token 怎么办？

**A**: 
1. 访问：https://github.com/settings/tokens
2. 点击 "Generate new token (classic)"
3. 勾选 `repo` 权限
4. 生成并复制 token
5. 在 `git push` 时用 token 作为密码

### Q: 如何查看当前版本？

**A**:
```powershell
git log --oneline -5
git show HEAD
```

### Q: 如何回退到之前的版本？

**A**:
```powershell
git log --oneline
git reset --hard <commit-hash>
git push -f origin main  # 强制推送（谨慎使用）
```

## 后续更新流程

每次修改代码后：

```powershell
cd c:\Users\bob_c\.gemini\antigravity\playground\loc-mvr

# 1. 查看修改
git status
git diff

# 2. 添加修改
git add .

# 3. 提交（描述性的提交信息）
git commit -m "描述你的修改"

# 4. 推送到 GitHub
git push
```

## 快速命令参考

```powershell
# 查看状态
git status

# 添加所有文件
git add .

# 提交
git commit -m "message"

# 推送
git push

# 拉取最新
git pull

# 查看日志
git log --oneline -10

# 查看远程仓库
git remote -v
```

## 备注

- 确保 `.gitignore` 已正确配置，排除临时文件
- 提交前检查 `git status` 确认文件列表
- 使用描述性的提交信息
- 定期推送到 GitHub 备份

## 联系方式

如有问题，请在 GitHub Issues 中提出：
https://github.com/Charpup/game-localization-mvr/issues
