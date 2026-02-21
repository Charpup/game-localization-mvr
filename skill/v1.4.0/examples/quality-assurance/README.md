# Quality Assurance Example

## loc-mVR v1.4.0 QA 流程示例

## 示例 1: 基础 QA 检查

### QA 规则配置

```yaml
# basic_qa_rules.yaml
rules:
  # 长度检查
  - id: length_check
    name: "Translation Length"
    type: length
    severity: warning
    params:
      max_ratio: 1.5  # 译文长度不超过原文 1.5 倍
      
  # 占位符检查
  - id: placeholder_check
    name: "Placeholder Consistency"
    type: regex
    severity: error
    pattern: '\{[0-9]+\}'
    check: preserve_count
    message: "Placeholder count mismatch"
    
  # 标点符号检查
  - id: punctuation_check
    name: "Punctuation Format"
    type: regex
    severity: warning
    pattern: '[，。！？]'
    message: "Chinese punctuation found in target"
    
  # 术语一致性
  - id: glossary_check
    name: "Glossary Compliance"
    type: glossary
    severity: error
    glossary: "config/glossary/global.yaml"
```

### 执行 QA

```bash
python -m skill.v1.4.0.scripts.cli qa \
  --input translated.csv \
  --rules basic_qa_rules.yaml \
  --output qa_report.json
```

## 示例 2: 分级别 QA

### 轻度检查 (quick_qa.yaml)

```yaml
# 适用于快速迭代
rules:
  - id: critical_errors
    type: regex
    severity: error
    pattern: '(?i)error|exception|failed'
    message: "Critical error pattern found"
```

### 完整检查 (full_qa.yaml)

```yaml
# 适用于发布前检查
rules:
  - id: length_check
    type: length
    severity: warning
    params:
      max_ratio: 1.3
      
  - id: placeholder_check
    type: regex
    severity: error
    pattern: '\{[0-9]+\}'
    check: preserve_count
    
  - id: glossary_check
    type: glossary
    severity: error
    
  - id: profanity_check
    type: regex
    severity: error
    pattern: '(?i)(badword1|badword2)'
    
  - id: consistency_check
    type: consistency
    severity: warning
    check_similar:
      threshold: 0.8
```

### 分级执行脚本

```bash
#!/bin/bash
# run_qa.sh

INPUT="translated.csv"
LEVEL="${1:-quick}"  # 默认快速检查

case $LEVEL in
  quick)
    echo "Running quick QA..."
    python -m skill.v1.4.0.scripts.cli qa \
      --input "$INPUT" \
      --rules qa_rules/quick_qa.yaml \
      --output reports/qa_quick.json
    ;;
    
  standard)
    echo "Running standard QA..."
    python -m skill.v1.4.0.scripts.cli qa \
      --input "$INPUT" \
      --rules qa_rules/basic_qa_rules.yaml \
      --output reports/qa_standard.json
    ;;
    
  full)
    echo "Running full QA..."
    python -m skill.v1.4.0.scripts.cli qa \
      --input "$INPUT" \
      --rules qa_rules/full_qa.yaml \
      --output reports/qa_full.json
    ;;
    
  *)
    echo "Unknown level: $LEVEL"
    exit 1
    ;;
esac
```

## 示例 3: QA 报告分析

### 报告结构

```json
{
  "metadata": {
    "timestamp": "2024-01-15T10:30:00Z",
    "input_file": "translated.csv",
    "total_entries": 1250
  },
  "summary": {
    "passed": 1180,
    "warnings": 45,
    "errors": 25,
    "pass_rate": "94.4%"
  },
  "issues": [
    {
      "row": 123,
      "key": "quest_title_01",
      "rule": "glossary_check",
      "severity": "error",
      "message": "Term '生命值' should be 'HP'",
      "source": "恢复 50 点生命值",
      "target": "Restore 50 Health Points"
    }
  ],
  "statistics": {
    "by_rule": {
      "glossary_check": {"errors": 15, "warnings": 0},
      "length_check": {"errors": 0, "warnings": 30},
      "placeholder_check": {"errors": 10, "warnings": 0}
    },
    "by_severity": {
      "error": 25,
      "warning": 45
    }
  }
}
```

### 报告分析脚本

```bash
#!/bin/bash
# analyze_qa_report.sh

REPORT="$1"

if [ ! -f "$REPORT" ]; then
    echo "Report not found: $REPORT"
    exit 1
fi

echo "=== QA Report Analysis ==="
echo ""

# 总体统计
echo "Summary:"
jq '.summary' "$REPORT"

# 错误详情
echo ""
echo "Errors:"
jq '.issues[] | select(.severity == "error") | "[\(.row)] \(.key): \(.message)"' "$REPORT"

# 按规则统计
echo ""
echo "Issues by Rule:"
jq '.statistics.by_rule | to_entries[] | "\(.key): \(.value.errors) errors, \(.value.warnings) warnings"' "$REPORT"
```

## 示例 4: 自动化 QA 管道

### CI 集成

```yaml
# .github/workflows/qa.yml
name: Localization QA

on:
  pull_request:
    paths:
      - 'data/translations/**'

jobs:
  qa:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.10'
      
      - name: Install dependencies
        run: pip install -r requirements.txt
      
      - name: Run QA
        run: |
          python -m skill.v1.4.0.scripts.cli qa \
            --input data/translated.csv \
            --rules config/qa_rules/full_qa.yaml \
            --output qa_report.json
      
      - name: Check QA Results
        run: |
          errors=$(jq '.summary.errors' qa_report.json)
          if [ "$errors" -gt 0 ]; then
            echo "QA failed with $errors errors"
            exit 1
          fi
          echo "QA passed!"
      
      - name: Upload Report
        uses: actions/upload-artifact@v3
        with:
          name: qa-report
          path: qa_report.json
```

## 示例 5: 修复工作流

### 自动修复脚本

```bash
#!/bin/bash
# auto_fix.sh

REPORT="qa_report.json"
INPUT="translated.csv"
OUTPUT="translated_fixed.csv"

echo "Processing QA report for auto-fixable issues..."

# 1. 提取可自动修复的问题
jq '.issues[] | select(.rule == "punctuation_check")' "$REPORT" > punctuation_issues.json

# 2. 应用标点符号修复
python << 'EOF'
import csv
import json

# 加载问题
with open('punctuation_issues.json') as f:
    issues = [json.loads(line) for line in f if line.strip()]

# 修复映射
fixes = {issue['row']: issue['suggested_fix'] for issue in issues if 'suggested_fix' in issue}

# 应用修复
with open('$INPUT', 'r') as infile, open('$OUTPUT', 'w', newline='') as outfile:
    reader = csv.DictReader(infile)
    writer = csv.DictWriter(outfile, fieldnames=reader.fieldnames)
    writer.writeheader()
    
    for i, row in enumerate(reader, start=1):
        if i in fixes:
            row['target'] = fixes[i]
        writer.writerow(row)

print(f"Applied {len(fixes)} automatic fixes")
EOF

# 3. 重新运行 QA
echo "Re-running QA..."
python -m skill.v1.4.0.scripts.cli qa \
  --input "$OUTPUT" \
  --rules config/qa_rules/basic_qa_rules.yaml \
  --output qa_report_fixed.json

# 4. 显示改进
before=$(jq '.summary.errors' "$REPORT")
after=$(jq '.summary.errors' qa_report_fixed.json)
improved=$((before - after))

echo ""
echo "Improvement: $improved errors fixed"
echo "Before: $before errors"
echo "After: $after errors"
```

## 最佳实践

1. **分阶段 QA**: 开发期快速检查，发布前完整检查
2. **阈值设置**: 错误零容忍，警告可协商
3. **定期审查**: 每周分析 QA 趋势
4. **规则维护**: 根据误报调整规则
