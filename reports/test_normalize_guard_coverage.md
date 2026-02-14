# normalize_guard.py 单元测试覆盖率报告

**生成时间**: 2026-02-15  
**测试文件**: `tests/test_normalize_guard_v2.py`  
**目标覆盖率**: ≥90%  
**实际覆盖率**: **93%** ✅

---

## 覆盖率摘要

```
Name                         Stmts   Miss  Cover   Missing
----------------------------------------------------------
scripts/normalize_guard.py     260     19    93%
----------------------------------------------------------
TOTAL                          260     19    93%
```

### 未覆盖代码行
- 32-34: Windows 平台 UTF-8 输出设置
- 38-40: YAML 模块缺失错误处理
- 339-341: 早期 QA 报告错误输出
- 367-369: 错误写入 placeholder map
- 429-430, 434-435, 466, 469, 499: 主函数和打印辅助函数的边缘情况

---

## 测试用例统计

| 测试类 | 测试数 | 描述 |
|--------|--------|------|
| TestPlaceholderFreezerInit | 4 | 初始化、文件加载、错误处理 |
| TestTagProtection | 6 | 标签保护/还原功能 |
| TestFreezeText | 13 | 占位符冻结、中文分词 |
| TestCounterManagement | 2 | 计数器重置和管理 |
| TestDetectUnbalancedBasic | 7 | 括号平衡检查 |
| TestNormalizeGuardInit | 2 | NormalizeGuard 初始化 |
| TestValidateInputHeaders | 3 | CSV 头验证 |
| TestProcessCSV | 7 | CSV 处理各种场景 |
| TestWriteOutputFiles | 3 | 输出文件写入 |
| TestQAReport | 2 | QA 报告生成 |
| TestFullWorkflow | 2 | 完整工作流 |
| TestEdgeCases | 6 | 边界情况测试 |
| TestErrorHandling | 2 | 错误处理测试 |
| TestMainFunction | 2 | 主入口测试 |
| TestPrintMethods | 2 | 打印辅助函数 |

**总计**: 62 个测试用例 ✅ 全部通过

---

## 功能覆盖详情

### ✅ PlaceholderFreezer
- [x] Schema YAML 加载
- [x] 空 schema 警告处理
- [x] 文件不存在错误处理
- [x] 无效 YAML 错误处理

### ✅ Tag Protection
- [x] 简单标签保护
- [x] 多个标签保护
- [x] 无标签文本处理
- [x] 嵌套标签处理
- [x] 标签还原功能

### ✅ freeze_text 功能
- [x] 花括号占位符: `{0}`, `{name}`
- [x] printf 风格: `%d`, `%s`, `%.2f`
- [x] 转义序列: `\n`, `\t`, `\r`
- [x] 尖括号标签: `<color>`, `<b>`, `<i>`
- [x] Token 重用机制
- [x] 空字符串处理
- [x] 中文分词 (jieba)
- [x] 中文+占位符混合
- [x] 标签+中文混合

### ✅ Balance Detection
- [x] 花括号平衡检查
- [x] 尖括号平衡检查
- [x] 方括号平衡检查
- [x] 多种不平衡同时检测
- [x] 嵌套平衡文本

### ✅ NormalizeGuard
- [x] CSV 头验证
- [x] 必需列检查
- [x] 空 string_id 检测
- [x] 重复 string_id 检测
- [x] 长文本检测 (>500 chars)
- [x] 额外列保留
- [x] draft.csv 写入
- [x] placeholder_map.json 写入
- [x] 早期 QA 报告生成
- [x] 完整工作流运行

### ✅ Edge Cases
- [x] Unicode 内容 (日文、表情符号)
- [x] 特殊字符
- [x] 超长文本 (10,000+ chars)
- [x] 多种相同标签

---

## 测试执行

```bash
cd /root/.openclaw/workspace/projects/game-localization-mvr/01_active/src
python3 -m pytest tests/test_normalize_guard_v2.py -v --tb=short
```

**结果**: 62 passed, 1 warning

---

## 报告文件

- `tests/test_normalize_guard_v2.py` - 测试文件 (1000+ 行)
- `htmlcov/index.html` - HTML 可视化报告
- `coverage.xml` - XML 格式报告

---

## 结论

✅ 目标达成：覆盖率 93% > 90%  
✅ 所有 62 个测试用例通过  
✅ 核心功能全部覆盖  
✅ 边界情况充分测试
