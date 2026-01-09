# 快速上传到 GitHub - v2.0

## 一键命令（适用于已配置仓库）

```powershell
# 进入项目目录
cd c:\Users\bob_c\.gemini\antigravity\playground\loc-mvr

# 查看当前状态
git status

# 添加所有改动
git add .

# 提交（v2.0 更新）
git commit -m "v2.0 Update: Term extraction + Schema v2.0 + Core scripts upgrade"

# 推送到 GitHub
git push
```

## 如果是首次推送

```powershell
# 进入项目目录
cd c:\Users\bob_c\.gemini\antigravity\playground\loc-mvr

# 初始化（如果未初始化）
git init

# 添加所有文件
git add .

# 首次提交
git commit -m "Initial commit: Game Localization MVR Workflow v2.0"

# 添加远程仓库
git remote add origin https://github.com/Charpup/game-localization-mvr.git

# 设置主分支
git branch -M main

# 推送
git push -u origin main
```

## 认证

如果提示认证：
- **Username**: `Charpup`
- **Password**: 使用 **Personal Access Token**（不是密码）

获取 PAT：https://github.com/settings/tokens

## v2.0 新增内容

本次更新包含：
- ✨ 术语提取功能（extract_terms.py）
- ✨ Schema v2.0（patterns + paired_tags）
- ✨ Forbidden Patterns（20规则）
- ✨ Normalize Guard v2.0（Token重用）
- ✨ QA Hard v2.0（Paired Tags检查）

## 验证

上传后访问：https://github.com/Charpup/game-localization-mvr

---

详细文档见：[GITHUB_UPLOAD_GUIDE.md](GITHUB_UPLOAD_GUIDE.md)
