# 手动 GitHub 上传步骤

## 当前状态
- ✅ Git 正在安装中（63.2 MB，正在下载）
- ✅ 你已登录 GitHub 并在新建仓库页面
- ✅ 所有项目文件已准备就绪

## 步骤 1: 在浏览器中创建 GitHub 仓库

你现在应该在 https://github.com/new 页面，请按以下步骤操作：

1. **Repository name**: 输入 `game-localization-mvr`

2. **Description**: 输入 `Game localization workflow with placeholder freezing, QA validation, and export automation`

3. **Public/Private**: 选择 **Public**（或根据需要选择 Private）

4. **重要**: 确保以下选项 **不要勾选**：
   - ❌ Add a README file
   - ❌ Add .gitignore  
   - ❌ Choose a license

5. 点击绿色的 **"Create repository"** 按钮

6. 创建后，你会看到一个页面显示如何推送现有仓库的命令

7. **复制 HTTPS URL**，应该类似：
   ```
   https://github.com/YOUR_USERNAME/game-localization-mvr.git
   ```

## 步骤 2: 等待 Git 安装完成

Git 正在安装中，请等待安装完成（大约 1-2 分钟）。

安装完成后，**重启你的终端/PowerShell**。

## 步骤 3: 验证 Git 安装

打开新的 PowerShell 窗口，运行：

```powershell
git --version
```

应该显示类似：`git version 2.52.0.windows.1`

## 步骤 4: 配置 Git（首次使用）

```powershell
git config --global user.name "Your Name"
git config --global user.email "your.email@example.com"
```

## 步骤 5: 初始化并上传项目

在项目目录中运行以下命令：

```powershell
# 进入项目目录
cd c:\Users\bob_c\.gemini\antigravity\playground\loc-mvr

# 初始化 Git 仓库
git init

# 添加所有文件
git add .

# 创建初始提交
git commit -m "Initial commit: Game localization MVR workflow with normalize, QA, and rehydrate scripts"

# 添加远程仓库（替换为你的 URL）
git remote add origin https://github.com/YOUR_USERNAME/game-localization-mvr.git

# 设置主分支名称
git branch -M main

# 推送到 GitHub
git push -u origin main
```

## 步骤 6: 验证上传

访问你的仓库页面：
```
https://github.com/YOUR_USERNAME/game-localization-mvr
```

你应该能看到：
- ✅ README.md 显示完整的项目介绍
- ✅ 所有脚本文件（scripts/）
- ✅ 文档目录（docs/）
- ✅ 配置文件（workflow/）
- ✅ 测试文件

## 如果遇到认证问题

GitHub 不再支持密码认证，你需要使用 Personal Access Token：

1. 访问 https://github.com/settings/tokens
2. 点击 "Generate new token (classic)"
3. 勾选 `repo` 权限
4. 生成并复制 token
5. 在 `git push` 时，使用 token 作为密码

## 后续更新

以后修改代码后，使用以下命令更新：

```powershell
git add .
git commit -m "描述你的修改"
git push
```

---

**提示**: 如果你完成了步骤 1（创建仓库），请告诉我你的 GitHub 用户名和仓库 URL，我可以帮你生成完整的命令。
