# Quick Commands for GitHub Setup

## Prerequisites
```bash
# Install Git first: https://git-scm.com/download/win
# Then configure:
git config --global user.name "Your Name"
git config --global user.email "your.email@example.com"
```

## Initial Upload

```bash
# Navigate to project directory
cd c:\Users\bob_c\.gemini\antigravity\playground\loc-mvr

# Initialize Git
git init

# Add all files
git add .

# Create initial commit
git commit -m "Initial commit: Game localization MVR workflow with normalize, QA, and rehydrate scripts"

# Add remote (replace YOUR_USERNAME with your GitHub username)
git remote add origin https://github.com/YOUR_USERNAME/game-localization-mvr.git

# Push to GitHub
git branch -M main
git push -u origin main
```

## Daily Workflow

```bash
# Check status
git status

# Add changes
git add .

# Commit
git commit -m "Your commit message"

# Push
git push
```

## Create GitHub Repository

1. Go to: https://github.com/new
2. Repository name: `game-localization-mvr`
3. Description: `Game localization workflow with placeholder freezing, QA validation, and export automation`
4. Public
5. **DO NOT** check: README, .gitignore, or license
6. Click "Create repository"
7. Copy the HTTPS URL shown
