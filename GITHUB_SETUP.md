# GitHub 上传指南

## 前提条件

### 1. 安装 Git

如果还没有安装 Git，请先安装：

**Windows**:
- 下载：https://git-scm.com/download/win
- 安装后重启终端

**验证安装**:
```bash
git --version
```

### 2. 配置 Git（首次使用）

```bash
git config --global user.name "Your Name"
git config --global user.email "your.email@example.com"
```

## 步骤 1: 初始化本地 Git 仓库

在项目目录 `c:\Users\bob_c\.gemini\antigravity\playground\loc-mvr` 中运行：

```bash
# 初始化 Git 仓库
git init

# 添加所有文件
git add .

# 创建初始提交
git commit -m "Initial commit: Game localization MVR workflow"
```

## 步骤 2: 在 GitHub 上创建新仓库

### 方式 A: 通过网页创建（推荐）

1. 访问 https://github.com/new

2. 填写仓库信息：
   - **Repository name**: `game-localization-mvr`
   - **Description**: `Game localization workflow with placeholder freezing, QA validation, and export automation`
   - **Public/Private**: 选择 Public（或根据需要选择 Private）
   - **⚠️ 重要**: 不要勾选以下选项（我们已经有这些文件）：
     - ❌ Add a README file
     - ❌ Add .gitignore
     - ❌ Choose a license

3. 点击 **Create repository**

4. 复制显示的 HTTPS URL，类似：
   ```
   https://github.com/YOUR_USERNAME/game-localization-mvr.git
   ```

### 方式 B: 使用 GitHub CLI（如果已安装）

```bash
gh repo create game-localization-mvr --public --description "Game localization workflow with placeholder freezing, QA validation, and export automation" --source=. --remote=origin --push
```

## 步骤 3: 连接本地仓库到 GitHub

使用步骤 2 中获得的 URL：

```bash
# 添加远程仓库
git remote add origin https://github.com/YOUR_USERNAME/game-localization-mvr.git

# 推送到 GitHub
git branch -M main
git push -u origin main
```

## 步骤 4: 验证上传

访问你的 GitHub 仓库页面：
```
https://github.com/YOUR_USERNAME/game-localization-mvr
```

应该能看到：
- ✅ README.md 显示项目介绍
- ✅ 所有脚本文件
- ✅ 文档目录
- ✅ 测试文件

## 后续更新流程

### 日常提交和推送

```bash
# 1. 查看修改
git status

# 2. 添加修改的文件
git add .
# 或添加特定文件
git add scripts/normalize_guard.py

# 3. 提交修改
git commit -m "描述你的修改"

# 4. 推送到 GitHub
git push
```

### 常用命令

```bash
# 查看提交历史
git log --oneline

# 查看远程仓库
git remote -v

# 拉取最新更改（如果有协作者）
git pull

# 创建新分支
git checkout -b feature/new-feature

# 切换分支
git checkout main

# 合并分支
git merge feature/new-feature
```

## 推荐的提交信息格式

```bash
# 新功能
git commit -m "feat: Add support for custom placeholder patterns"

# 修复 bug
git commit -m "fix: Correct token matching in qa_hard.py"

# 文档更新
git commit -m "docs: Update README with installation instructions"

# 测试
git commit -m "test: Add unit tests for rehydrate_export"

# 重构
git commit -m "refactor: Simplify placeholder freezing logic"
```

## 常见问题

### Q: 推送时要求输入用户名和密码

**A**: GitHub 已不再支持密码认证，需要使用 Personal Access Token (PAT)：

1. 访问 https://github.com/settings/tokens
2. 点击 "Generate new token (classic)"
3. 选择权限：至少勾选 `repo`
4. 生成并复制 token
5. 推送时使用 token 作为密码

**或者使用 SSH**：
```bash
# 生成 SSH 密钥
ssh-keygen -t ed25519 -C "your.email@example.com"

# 添加到 GitHub: https://github.com/settings/keys
# 修改远程 URL
git remote set-url origin git@github.com:YOUR_USERNAME/game-localization-mvr.git
```

### Q: 如何忽略某些文件？

**A**: 编辑 `.gitignore` 文件（已创建），添加要忽略的文件模式。

### Q: 如何撤销最后一次提交？

**A**: 
```bash
# 保留修改，撤销提交
git reset --soft HEAD~1

# 完全撤销（危险！）
git reset --hard HEAD~1
```

## 项目文件清单

已准备好上传的文件：

```
✅ README.md - 项目介绍
✅ .gitignore - Git 忽略规则
✅ scripts/ - 核心脚本
   ├── normalize_guard.py
   ├── qa_hard.py
   ├── rehydrate_export.py
   └── test_*.py
✅ workflow/ - 配置文件
   ├── placeholder_schema.yaml
   ├── forbidden_patterns.txt
   └── style_guide.md
✅ docs/ - 文档
   ├── normalize_guard_usage.md
   ├── qa_hard_usage.md
   ├── rehydrate_export_usage.md
   └── demo.md
✅ data/ - 示例数据
   ├── input.csv
   ├── draft.csv
   ├── translated_good.csv
   └── translated_bad.csv
```

## 下一步

1. 安装 Git（如果还没有）
2. 按照步骤 1-3 完成上传
3. 开始使用 Git 进行版本控制
4. 邀请协作者（如需要）

## 有用的资源

- Git 官方文档: https://git-scm.com/doc
- GitHub 指南: https://guides.github.com/
- Git 速查表: https://training.github.com/downloads/github-git-cheat-sheet/
