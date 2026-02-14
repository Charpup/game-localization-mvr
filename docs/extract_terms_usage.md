# Extract Terms 使用说明

## 功能概述

`extract_terms.py` 从游戏本地化源文本中自动提取专业术语候选，帮助翻译团队建立和维护术语表。

## 使用方法

```bash
python scripts/extract_terms.py <input_csv> <output_candidates_yaml> [glossary_yaml] [min_freq]
```

### 参数说明

- **input_csv**: 输入的 CSV 文件（必须包含 `string_id` 和 `source_zh` 列）
- **output_candidates_yaml**: 输出的术语候选 YAML 文件
- **glossary_yaml**: 现有术语表 YAML 文件（可选）
- **min_freq**: 最小词频阈值（默认 2，即至少出现 2 次）

### 示例

```bash
# 基本用法
python scripts/extract_terms.py data/input.csv data/term_candidates.yaml

# 使用现有术语表过滤
python scripts/extract_terms.py data/input.csv data/term_candidates.yaml data/glossary.yaml

# 自定义最小词频
python scripts/extract_terms.py data/input.csv data/term_candidates.yaml data/glossary.yaml 3
```

## 依赖要求

### 必需依赖

- **jieba**: 中文分词库（强制要求）

```bash
pip install jieba
```

> [!IMPORTANT]
> jieba 是强制依赖。如果未安装，脚本会报错并退出，不提供 fallback 方案。

## 工作原理

### 1. 加载源文本

从 CSV 文件中读取 `source_zh` 列的中文文本。

### 2. 中文分词

使用 **jieba 分词**对文本进行精确切分：

```python
words = jieba.cut("欢迎玩家来到游戏世界")
# ['欢迎', '玩家', '来到', '游戏', '世界']
```

### 3. 过滤规则

- **停用词过滤**: 移除"的"、"了"、"在"等常见词
- **长度过滤**: 保留 2-8 个字符的词（可配置）
- **格式过滤**: 排除纯数字、纯英文、标点符号
- **词频过滤**: 只保留出现次数 ≥ min_freq 的词

### 4. 术语表对比

如果提供了 `glossary.yaml`，会自动过滤已知术语，只提取新的候选。

### 5. 生成输出

输出 YAML 文件包含：
- 术语候选列表（按频率排序）
- 每个术语的出现次数
- 出现的 string_id 列表
- 统计信息

## 输出格式

### term_candidates.yaml

```yaml
version: "1.0"
generated_at: "2026-01-10T01:58:00+08:00"

statistics:
  total_strings: 7
  unique_terms: 1
  total_occurrences: 2

candidates:
  - term: "获得"
    frequency: 2
    string_ids:
      - "color_text"
      - "multi_placeholder"
    suggested_translation: ""
    category: "待分类"
    note: ""

extraction_rules:
  min_frequency: 2
  min_length: 2
  max_length: 8
  segmentation: "jieba"
```

## 术语表格式

### glossary.yaml

```yaml
version: "1.0"

terms:
  角色:
    en: Character
    category: gameplay
    note: 游戏中的可控单位
    examples:
      - "创建新角色"
  
  玩家:
    en: Player
    category: gameplay
    note: 控制角色的用户

categories:
  gameplay: 游戏玩法相关
  items: 物品道具相关
  system: 游戏系统相关
```

## 工作流集成

### 完整流程

```
1. Normalize → 冻结占位符
   input.csv → draft.csv

2. Extract Terms → 提取术语候选
   input.csv → term_candidates.yaml

3. Review & Update Glossary → 人工审核
   term_candidates.yaml + glossary.yaml

4. Translate → 使用术语表翻译
   draft.csv → translated.csv

5. QA Hard → 验证翻译质量
   translated.csv → qa_report.json

6. Rehydrate → 还原并导出
   translated.csv → final.csv
```

### 增量更新流程

```bash
# 1. 从新的源文本提取术语
python scripts/extract_terms.py data/input_new.csv data/new_terms.yaml data/glossary.yaml

# 2. 人工审核 new_terms.yaml，将确认的术语添加到 glossary.yaml

# 3. 重新运行提取，验证已无遗漏
python scripts/extract_terms.py data/input_new.csv data/verify.yaml data/glossary.yaml
# 应该只剩下少量或无候选词
```

## 自定义配置

### 修改停用词

在 `workflow/stopwords.txt` 中添加项目特定的停用词：

```
# 项目特定停用词
的
了
在
# 添加更多...
```

### 调整提取参数

修改脚本调用参数：

```bash
# 更严格：最少出现 5 次
python scripts/extract_terms.py data/input.csv data/terms.yaml data/glossary.yaml 5

# 更宽松：最少出现 1 次（会有很多噪音）
python scripts/extract_terms.py data/input.csv data/terms.yaml data/glossary.yaml 1
```

## 运行示例

```bash
$ python scripts/extract_terms.py data/input.csv data/term_candidates_test.yaml data/glossary.yaml

🚀 开始术语提取流程...

✅ 加载了 7 条源文本
✅ 加载了 9 个已知术语

🔍 开始提取术语...
Building prefix dict from the default dictionary ...
Prefix dict has been built successfully.
✅ 提取了 1 个术语候选（去除已知术语后）
   总词汇数：13
   高频词汇（≥2次）：2
✅ 候选列表已保存到：data/term_candidates_test.yaml

📊 术语提取摘要：
   共处理：7 条文本
   提取候选：1 个术语
   已知术语：9 个（已过滤）

   高频术语 TOP 1：
      1. 获得 (出现 2 次)

✅ 术语提取完成！
```

## 常见问题

### Q: jieba 未安装怎么办？

**A**: 脚本会立即报错：
```
错误：jieba 分词库未安装。
请运行：pip install jieba
jieba 是必需的依赖，用于中文分词以确保术语提取的准确性。
```

安装即可：
```bash
pip install jieba
```

### Q: 提取的术语太多都是噪音？

**A**: 
1. 提高 `min_freq` 参数（如设为 3 或 5）
2. 维护更完整的 `glossary.yaml`，已知术语会被自动过滤
3. 添加项目特定停用词到 `workflow/stopwords.txt`

### Q: 如何处理候选列表？

**A**:
1. 人工审核 `term_candidates.yaml`
2. 选择真正的专业术语
3. 添加到 `glossary.yaml` 并补充英文翻译
4. 重新运行提取验证

### Q: 能否使用 LLM 进行分词？

**A**: 当前版本使用 jieba。未来版本可考虑集成 LLM 作为可选方案：
- 优点：更准确的语义理解
- 缺点：需要 API 调用，成本和延迟

## 最佳实践

1. **定期更新术语表**: 每次添加新文本后运行提取
2. **团队协作**: 术语确认应该由翻译团队和项目方共同审核
3. **版本控制**: 将 `glossary.yaml` 纳入 Git 版本控制
4. **文档化**: 为每个术语添加 note 和 examples

## 测试

```bash
# 运行测试
python scripts/test_extract_terms.py

# 预期输出
🧪 Testing extract_terms.py output...
✅ Loaded term candidates file
✅ Test passed: File structure correct
📊 Statistics:
   Total strings: 7
   Unique terms: 1
🎉 All extract_terms tests passed!
```

## 相关文件

- [extract_terms.py](file:///c:/Users/bob_c/.gemini/antigravity/playground/loc-mvr/scripts/extract_terms.py) - 主脚本
- [glossary.yaml](file:///c:/Users/bob_c/.gemini/antigravity/playground/loc-mvr/data/glossary.yaml) - 术语表
- [term_candidates.yaml](file:///c:/Users/bob_c/.gemini/antigravity/playground/loc-mvr/data/term_candidates.yaml) - 候选列表
