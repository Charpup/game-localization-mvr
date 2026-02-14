# 规则同步机制

## 目的

确保 `docs/WORKSPACE_RULES.md` 的规则变更能够同步到 `.agent/rules/localization-mvr-rules.md`，使 Antigravity IDE 能够识别和执行最新规则。

## 文件关系

- **`docs/WORKSPACE_RULES.md`**: 完整详细的规则文档（约 480 行），包含所有规则的详细说明、示例代码、表格等
- **`.agent/rules/localization-mvr-rules.md`**: 精简版规则文档（约 100 行），用于 Antigravity IDE 约束，包含核心规则的简洁描述

## 同步流程

### 1. 规则变更时

当修改 `WORKSPACE_RULES.md` 添加或更新规则时：

1. **更新完整文档**: 在 `docs/WORKSPACE_RULES.md` 中添加/修改规则
2. **提取核心内容**: 将规则的核心约束提取为精简版本
3. **同步到 Antigravity**: 更新 `.agent/rules/localization-mvr-rules.md`
4. **验证同步**: 运行验证脚本确保关键内容已同步

### 2. 精简原则

同步到 `.agent/rules/localization-mvr-rules.md` 时应遵循：

- **保留核心约束**: 必须包含的强制规则
- **简化示例**: 移除冗长的代码示例，保留关键示例
- **突出禁止项**: 明确标注禁止操作
- **保留参数值**: 锁定的参数值必须完整保留

### 3. 版本号同步

两个文件的版本号必须保持一致：

- 修改任一文件时，同步更新版本号
- 在 Changelog 中记录变更

## 验证脚本

创建验证脚本 `scripts/verify_rules_sync.py` 检查：

```python
def verify_rules_sync():
    # 1. 检查版本号是否一致
    # 2. 检查关键规则是否都存在
    # 3. 检查锁定参数值是否一致
    pass
```

## 示例：Rule 14 同步

**完整版 (WORKSPACE_RULES.md)**:

- 包含详细表格
- 包含强制执行流程
- 包含生产事故案例
- 包含违规后果说明

**精简版 (localization-mvr-rules.md)**:

- 保留参数锁定表格
- 保留强制执行流程（简化）
- 保留生产事故案例（简化）
- 保留不可覆盖声明

## 自动化建议

未来可考虑：

1. 创建 `sync_rules.py` 脚本自动同步
2. 在 pre-commit hook 中检查版本号一致性
3. CI/CD 中验证两个文件的关键内容同步

---
Version: 1.0
Created: 2026-01-31
