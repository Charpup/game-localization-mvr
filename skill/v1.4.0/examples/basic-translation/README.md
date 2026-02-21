# Basic Translation Example

## loc-mVR v1.4.0 基础翻译示例

## 示例 1: 简单翻译

### 输入文件 (input.csv)

```csv
key,source,context
welcome_title,欢迎来到游戏,ui
start_button,开始游戏,ui
settings_button,设置,ui
```

### 执行命令

```bash
python -m skill.v1.4.0.scripts.cli translate \
  --input input.csv \
  --source zh-CN \
  --target en-US \
  --output output.csv
```

### 输出文件 (output.csv)

```csv
key,source,target,context
welcome_title,欢迎来到游戏,Welcome to the Game,ui
start_button,开始游戏,Start Game,ui
settings_button,设置,Settings,ui
```

## 示例 2: 使用术语表

### 术语表 (glossary.yaml)

```yaml
terms:
  - source: "生命值"
    target: "HP"
    context: "gameplay"
  - source: "魔法值"
    target: "MP"
    context: "gameplay"
  - source: "经验值"
    target: "XP"
    context: "gameplay"
```

### 输入文件

```csv
key,source,context
hp_label,生命值,ui
mp_label,魔法值,ui
xp_label,经验值,ui
```

### 执行命令

```bash
python -m skill.v1.4.0.scripts.cli translate \
  --input input.csv \
  --source zh-CN \
  --target en-US \
  --glossary glossary.yaml \
  --output output.csv
```

### 预期输出

```csv
key,source,target,context
hp_label,生命值,HP,ui
mp_label,魔法值,MP,ui
xp_label,经验值,XP,ui
```

## 示例 3: 批量翻译

### 文件结构

```
batch_translation/
├── input/
│   ├── ui_texts.csv
│   ├── dialogues.csv
│   └── items.csv
└── output/
```

### 批处理脚本

```bash
#!/bin/bash
# batch_translate.sh

INPUT_DIR="batch_translation/input"
OUTPUT_DIR="batch_translation/output"
GLOSSARY="config/glossary/game_terms.yaml"

for file in "$INPUT_DIR"/*.csv; do
    filename=$(basename "$file")
    echo "Translating: $filename"
    
    python -m skill.v1.4.0.scripts.cli translate \
        --input "$file" \
        --source zh-CN \
        --target en-US \
        --glossary "$GLOSSARY" \
        --output "$OUTPUT_DIR/$filename"
done

echo "Batch translation complete!"
```

### 运行批处理

```bash
chmod +x batch_translate.sh
./batch_translate.sh
```

## 示例 4: 多语言翻译

### 配置 (languages.txt)

```
en-US
ja-JP
ko-KR
```

### 多语言脚本

```bash
#!/bin/bash
# multi_language_translate.sh

INPUT="input.csv"
SOURCE="zh-CN"

for target in $(cat languages.txt); do
    echo "Translating to: $target"
    
    python -m skill.v1.4.0.scripts.cli translate \
        --input "$INPUT" \
        --source "$SOURCE" \
        --target "$target" \
        --output "output_${target}.csv"
done
```

## 示例 5: 带上下文的翻译

### 输入文件

```csv
key,source,context,notes
damage_text,造成 {0} 点伤害,combat,"{0} is a number"
heal_text,恢复 {0} 点生命,combat,"{0} is a number"
quest_complete,任务完成！,notification,"Celebratory tone"
```

### 命令

```bash
python -m skill.v1.4.0.scripts.cli translate \
  --input input.csv \
  --source zh-CN \
  --target en-US \
  --preserve-placeholders \
  --output output.csv
```

## 验证结果

```bash
# 检查输出文件
head -5 output.csv

# 统计翻译条目
wc -l output.csv

# 检查是否有空翻译
grep ',$' output.csv || echo "No empty translations found"
```
