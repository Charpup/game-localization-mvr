#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Normalize Guard Script v2.0
冻结占位符/标签为 token，生成 draft.csv 和 placeholder_map.json

融合版本：结合 v1.0 的严格验证和 v2.0 的新特性

Usage:
    python normalize_guard.py <input_csv> <output_draft_csv> <output_map_json> <schema_yaml>

Features:
    - 使用新的 schema v2.0 格式 (patterns, token_format)
    - Token 重用机制（相同占位符使用相同 token）
    - 基本平衡检查（括号、标签平衡）
    - 早期 QA 报告生成
    - 详细的错误处理和验证
    - 重复 ID 检测
"""

import csv
import io
import json
import re
import sys
import jieba
from pathlib import Path
from typing import List, Dict, Tuple, Set
from datetime import datetime

def configure_standard_streams() -> None:
    """Best-effort UTF-8 console setup for CLI execution only."""
    if sys.platform != 'win32':
        return

    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        if stream is None:
            continue
        try:
            if hasattr(stream, "reconfigure"):
                stream.reconfigure(encoding='utf-8', errors='replace')
                continue
            buffer = getattr(stream, "buffer", None)
            if buffer is not None:
                wrapped = io.TextIOWrapper(buffer, encoding='utf-8', errors='replace')
                setattr(sys, stream_name, wrapped)
        except Exception:
            # Test runners and wrapped streams may not support reconfiguration.
            continue

try:
    import yaml
except ImportError:
    print("[ERROR] PyYAML is required. Install with: pip install pyyaml")
    sys.exit(1)


class PlaceholderFreezer:
    """占位符冻结器 - 使用 schema v2.0"""
    
    def __init__(self, schema_path: str):
        self.schema_path = Path(schema_path)
        self.patterns: List[Dict] = []
        self.token_format: Dict[str, str] = {}
        self._skip_segmentation_re = re.compile(
            r"(<[^>]+>|\{[^{}]*\}|\[[^\[\]]+\]|\\[ntr]|%(?:\d+\$)?[A-Za-z]|【|】)"
        )
        
        # 计数器
        self.ph_counter = 0
        self.tag_counter = 0
        
        # 映射：token_name -> original_text
        self.placeholder_map: Dict[str, str] = {}
        
        # 反向映射：original_text -> token_name（用于重用）
        self.reverse_map: Dict[str, str] = {}
        
        self.load_schema()
    
    def load_schema(self) -> None:
        """加载 schema v2.0"""
        try:
            with open(self.schema_path, 'r', encoding='utf-8') as f:
                schema = yaml.safe_load(f)
                
                # v2.0 使用 'patterns' 而不是 'placeholder_patterns'
                self.patterns = schema.get('patterns', [])
                self.token_format = schema.get('token_format', {
                    'placeholder': '⟦PH_{n}⟧',
                    'tag': '⟦TAG_{n}⟧'
                })
                
                if not self.patterns:
                    print("[WARN] No patterns found in schema")
                    print(f"   Schema keys: {list(schema.keys())}")
                else:
                    print(f"[OK] Loaded {len(self.patterns)} patterns from schema v{schema.get('version', 'unknown')}")

        except FileNotFoundError:
            print(f"[ERROR] Schema file not found: {self.schema_path}")
            sys.exit(1)
        except Exception as e:
            print(f"[ERROR] Error loading schema: {str(e)}")
            sys.exit(1)
    
    def freeze_text(self, text: str, source_lang: str = 'zh-CN') -> Tuple[str, Dict[str, str]]:
        """
        冻结文本中的占位符和标签
        
        重要：使用 token 重用机制，相同的占位符重用相同的 token
        新增：中文分词预处理 (source_lang='zh-CN' related)
        
        Returns:
            (tokenized_text, local_map) - token 化的文本和本次冻结的映射
        """
        if not text:
            return text, {}
        
        local_map = {}
        result = text

        # 新增: 中文分词预处理
        # 遇到占位符/标签时按块分词，避免将 {0} 误切成 { 0 } 这类序列，
        # 同时保留中文语块的空格边界。
        if source_lang.startswith('zh') and result:
            parts = re.split(f"({self._skip_segmentation_re.pattern})", result)
            segmented_parts = []
            for part in parts:
                if not part:
                    continue
                if self._skip_segmentation_re.fullmatch(part):
                    segmented_parts.append(part)
                    continue
                words = jieba.lcut(part)
                segmented_parts.append(' '.join(word for word in words if word))
            result = ' '.join(part for part in segmented_parts if part).strip()
        
        # 编译所有模式的正则表达式
        compiled_patterns = []
        for p in self.patterns:
            try:
                compiled_patterns.append({
                    'name': p['name'],
                    'type': p['type'],
                    'regex': re.compile(p['regex'])
                })
            except re.error as e:
                print(f"[WARN] Invalid regex in pattern '{p['name']}': {e}")
        
        # 按优先级顺序处理每个模式
        for pattern_def in compiled_patterns:
            regex = pattern_def['regex']
            ptype = pattern_def['type']
            
            def repl(match):
                original = match.group(0)
                
                # 检查是否已经冻结过这个字符串（重用 token）
                if original in self.reverse_map:
                    token_name = self.reverse_map[original]
                    return f"⟦{token_name}⟧"
                
                # 生成新 token
                if ptype == 'placeholder':
                    self.ph_counter += 1
                    token_name = f"PH_{self.ph_counter}"
                else:  # tag
                    self.tag_counter += 1
                    token_name = f"TAG_{self.tag_counter}"
                
                # 记录映射
                self.placeholder_map[token_name] = original
                self.reverse_map[original] = token_name
                local_map[token_name] = original
                
                return f"⟦{token_name}⟧"
            
            result = regex.sub(repl, result)
        
        return result, local_map
    
    def reset_counters(self) -> None:
        """重置计数器（用于处理新文件）"""
        self.ph_counter = 0
        self.tag_counter = 0
        self.placeholder_map = {}
        self.reverse_map = {}


def detect_unbalanced_basic(text: str) -> List[str]:
    """
    基本的平衡检查 - 检测明显的不平衡
    
    这是保守的健全性检查，用于早期发现问题
    """
    issues = []
    
    # 花括号平衡
    if text.count('{') != text.count('}'):
        issues.append('brace_unbalanced')
    
    # 尖括号平衡（粗略检查，标签会在 QA 中详细检查）
    if text.count('<') != text.count('>'):
        issues.append('angle_unbalanced')
    
    # 方括号平衡
    if text.count('[') != text.count(']'):
        issues.append('square_unbalanced')
    
    return issues


class NormalizeGuard:
    """主处理类：规范化输入并生成 draft.csv 和 placeholder_map.json"""
    
    def __init__(
        self,
        input_path: str,
        output_draft_path: str,
        output_map_path: str,
        schema_path: str,
        source_lang: str = "zh-CN",
        long_text_threshold: int = 200,
    ):
        self.source_lang = source_lang
        self.input_path = Path(input_path)
        self.output_draft_path = Path(output_draft_path)
        self.output_map_path = Path(output_map_path)
        self.schema_path = Path(schema_path)
        self.long_text_threshold = int(long_text_threshold)
        
        self.freezer = PlaceholderFreezer(schema_path)
        self.errors: List[str] = []
        self.warnings: List[str] = []
        self.sanity_errors: List[Dict] = []  # 源文本平衡问题
    
    def validate_input_headers(self, headers: List[str]) -> bool:
        """验证输入文件必需列"""
        required = ['string_id', 'source_zh']
        missing = set(required) - set(headers)
        
        if missing:
            self.errors.append(f"Missing required columns: {missing}")
            return False
        return True
    
    def process_csv(self) -> Tuple[bool, List[Dict]]:
        """处理 CSV 文件"""
        try:
            with open(self.input_path, 'r', encoding='utf-8-sig', newline='') as f:
                reader = csv.DictReader(f)
                headers = reader.fieldnames
                
                if not self.validate_input_headers(headers):
                    return False, []
                
                processed_rows = []
                seen_ids: Set[str] = set()
                
                for idx, row in enumerate(reader, start=2):
                    string_id = (row.get('string_id') or '').strip()
                    source_zh = row.get('source_zh') or ''
                    
                    # 验证 string_id
                    if not string_id:
                        self.errors.append(f"Row {idx}: Empty string_id")
                        continue
                    
                    if string_id in seen_ids:
                        self.warnings.append(f"Row {idx}: Duplicate string_id '{string_id}'")
                    
                    seen_ids.add(string_id)
                    
                    # 基本平衡检查
                    issues = detect_unbalanced_basic(source_zh)
                    if issues:
                        self.sanity_errors.append({
                            'string_id': string_id,
                            'issues': issues,
                            'source_zh': source_zh,
                            'row': idx
                        })
                    
                    # 冻结占位符
                    tokenized_zh, local_map = self.freezer.freeze_text(source_zh, self.source_lang)
                    
                    # 构建输出行
                    output_row = {
                        'string_id': string_id,
                        'source_zh': source_zh,
                        'tokenized_zh': tokenized_zh,
                        'is_long_text': "true" if len(source_zh) >= self.long_text_threshold else "false",
                    }
                    
                    # 保留其他列
                    for key in headers:
                        if key not in ['string_id', 'source_zh']:
                            output_row[key] = row.get(key, '')
                    
                    processed_rows.append(output_row)
                    
                    # 打印冻结信息
                    if local_map:
                        print(f"  Row {idx} ({string_id}): Froze {len(local_map)} placeholders")
                
                return len(self.errors) == 0, processed_rows
                
        except FileNotFoundError:
            self.errors.append(f"Input file not found: {self.input_path}")
            return False, []
        except Exception as e:
            self.errors.append(f"Error processing CSV: {str(e)}")
            import traceback
            traceback.print_exc()
            return False, []
    
    def write_draft_csv(self, rows: List[Dict]) -> bool:
        """写入 draft.csv"""
        try:
            if not rows:
                self.warnings.append("No rows to write")
                return True
            
            # 确保列顺序：string_id, source_zh, tokenized_zh, 其他列
            fieldnames = ['string_id', 'source_zh', 'tokenized_zh']
            for key in rows[0].keys():
                if key not in fieldnames:
                    fieldnames.append(key)
            
            # 创建输出目录
            self.output_draft_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(self.output_draft_path, 'w', encoding='utf-8-sig', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(rows)
            
            print(f"[OK] Wrote {len(rows)} rows to {self.output_draft_path}")
            return True
            
        except Exception as e:
            self.errors.append(f"Error writing draft CSV: {str(e)}")
            return False
    
    def write_placeholder_map(self) -> bool:
        """写入 placeholder_map.json"""
        try:
            output = {
                'metadata': {
                    'version': '2.0',
                    'generated_at': datetime.now().isoformat(),
                    'input_file': str(self.input_path),
                    'total_placeholders': len(self.freezer.placeholder_map),
                    'ph_count': self.freezer.ph_counter,
                    'tag_count': self.freezer.tag_counter
                },
                'mappings': self.freezer.placeholder_map
            }
            
            # 创建输出目录
            self.output_map_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(self.output_map_path, 'w', encoding='utf-8') as f:
                json.dump(output, f, indent=2, ensure_ascii=False)
            
            print(f"[OK] Wrote {len(self.freezer.placeholder_map)} placeholder mappings to {self.output_map_path}")
            return True
            
        except Exception as e:
            self.errors.append(f"Error writing placeholder map: {str(e)}")
            return False
    
    def write_early_qa_report(self, total_rows: int) -> None:
        """
        写入早期 QA 报告（如果发现源文本平衡问题）
        
        这是一个可选的早期检查，帮助在翻译前发现问题
        """
        if not self.sanity_errors:
            return
        
        early_report = {
            'has_errors': True,
            'total_rows': total_rows,
            'error_counts': {
                'source_unbalanced_basic': len(self.sanity_errors)
            },
            'errors': [
                {
                    'row': e['row'],
                    'string_id': e['string_id'],
                    'type': 'source_unbalanced_basic',
                    'detail': ', '.join(e['issues']),
                    'source': e['source_zh']
                }
                for e in self.sanity_errors[:200]  # 限制错误数量
            ],
            'metadata': {
                'generated_at': datetime.now().isoformat(),
                'note': 'Early sanity check - source text balance issues detected'
            }
        }
        
        # 写入早期报告
        early_path = self.output_map_path.parent / 'qa_hard_report.json'
        with open(early_path, 'w', encoding='utf-8') as f:
            json.dump(early_report, f, ensure_ascii=False, indent=2)
        
            print(f"[WARN] Found {len(self.sanity_errors)} source sanity issues")
            print(f"   Early QA report written: {early_path}")
    
    def run(self) -> bool:
        """执行规范化流程"""
        print("[INFO] Starting normalize guard v2.0...")
        print(f"   Input: {self.input_path}")
        print(f"   Output draft: {self.output_draft_path}")
        print(f"   Output map: {self.output_map_path}")
        print(f"   Schema: {self.schema_path}")
        print()
        
        # 处理 CSV
        success, rows = self.process_csv()
        
        if not success:
            self._print_errors()
            return False
        
        # 写入输出文件
        success = self.write_draft_csv(rows)
        if not success:
            self._print_errors()
            return False
        
        success = self.write_placeholder_map()
        if not success:
            self._print_errors()
            return False
        
        # 写入早期 QA 报告（如果有平衡问题）
        self.write_early_qa_report(len(rows))
        
        # 打印总结
        self._print_summary(rows)
        
        return True
    
    def _print_errors(self) -> None:
        """打印错误信息"""
        if self.warnings:
            print("\n[WARN] Warnings:")
            for warning in self.warnings:
                print(f"   {warning}")
        
        if self.errors:
            print("\n[ERROR] Errors:")
            for error in self.errors:
                print(f"   {error}")
    
    def _print_summary(self, rows: List[Dict]) -> None:
        """打印处理总结"""
        print(f"\n[SUMMARY]")
        print(f"   Total strings processed: {len(rows)}")
        print(f"   Total placeholders frozen: {len(self.freezer.placeholder_map)}")
        print(f"   PH tokens: {self.freezer.ph_counter}")
        print(f"   TAG tokens: {self.freezer.tag_counter}")
        
        if self.sanity_errors:
            print(f"   Source balance issues: {len(self.sanity_errors)}")
        
        if self.warnings:
            print(f"   Warnings: {len(self.warnings)}")
        
        print(f"\n[OK] Normalization complete!")


def main():
    """主入口"""
    import argparse
    configure_standard_streams()
    parser = argparse.ArgumentParser(description="Normalize Guard v2.0")
    parser.add_argument("input_csv", help="Input CSV path")
    parser.add_argument("output_draft", help="Output draft CSV path")
    parser.add_argument("output_map", help="Output map JSON path")
    parser.add_argument("schema_yaml", help="Schema YAML path")
    parser.add_argument("--source-lang", default="zh-CN", help="Source language (default: zh-CN)")
    parser.add_argument(
        "--long-text-threshold",
        type=int,
        default=200,
        help="Length threshold to flag long text for single-row translation.",
    )
    
    args = parser.parse_args()
    
    guard = NormalizeGuard(
        input_path=args.input_csv,
        output_draft_path=args.output_draft,
        output_map_path=args.output_map,
        schema_path=args.schema_yaml,
        source_lang=args.source_lang,
        long_text_threshold=args.long_text_threshold,
    )
    
    success = guard.run()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
