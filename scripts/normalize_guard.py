#!/usr/bin/env python3
"""
Normalize Guard Script
冻结占位符/标签为 token，生成 draft.csv 和 placeholder_map.json

Usage:
    python normalize_guard.py <input_csv> <output_draft_csv> <output_map_json> <schema_yaml>
"""

import csv
import json
import re
import sys
import yaml
from pathlib import Path
from typing import List, Dict, Tuple, Set
from datetime import datetime


class PlaceholderFreezer:
    """冻结占位符和标签为 token"""
    
    def __init__(self, schema_path: str):
        self.schema_path = Path(schema_path)
        self.patterns: List[Dict] = []
        self.ph_counter = 0
        self.tag_counter = 0
        self.placeholder_map: Dict[str, str] = {}
        
        self.load_schema()
    
    def load_schema(self) -> None:
        """加载 placeholder schema"""
        try:
            with open(self.schema_path, 'r', encoding='utf-8') as f:
                schema = yaml.safe_load(f)
                self.patterns = schema.get('placeholder_patterns', [])
                print(f"✅ Loaded {len(self.patterns)} placeholder patterns from schema")
        except FileNotFoundError:
            print(f"⚠️  Warning: Schema file not found: {self.schema_path}")
            print("   Using default patterns...")
            self._load_default_patterns()
        except Exception as e:
            print(f"⚠️  Warning: Error loading schema: {str(e)}")
            print("   Using default patterns...")
            self._load_default_patterns()
    
    def _load_default_patterns(self) -> None:
        """加载默认占位符模式"""
        self.patterns = [
            {'name': 'csharp_numbered', 'pattern': r'\{\d+\}', 'type': 'PH'},
            {'name': 'csharp_named', 'pattern': r'\{[a-zA-Z_][a-zA-Z0-9_]*\}', 'type': 'PH'},
            {'name': 'printf_string', 'pattern': r'%s', 'type': 'PH'},
            {'name': 'printf_int', 'pattern': r'%d', 'type': 'PH'},
            {'name': 'unity_color_tag', 'pattern': r'<color=#?[0-9A-Fa-f]{6,8}>', 'type': 'TAG'},
            {'name': 'unity_close_tag', 'pattern': r'</color>', 'type': 'TAG'},
            {'name': 'newline', 'pattern': r'\\n', 'type': 'PH'},
        ]
    
    def freeze_text(self, text: str) -> Tuple[str, Dict[str, str]]:
        """
        冻结文本中的占位符和标签
        
        Returns:
            (tokenized_text, local_map) - token 化的文本和本次冻结的映射
        """
        if not text:
            return text, {}
        
        local_map = {}
        result = text
        
        # 记录所有匹配及其位置
        matches = []
        for pattern_def in self.patterns:
            pattern = pattern_def['pattern']
            ph_type = pattern_def['type']
            
            for match in re.finditer(pattern, text):
                matches.append({
                    'start': match.start(),
                    'end': match.end(),
                    'text': match.group(),
                    'type': ph_type,
                    'name': pattern_def['name']
                })
        
        # 按位置排序（从后往前替换，避免位置偏移）
        matches.sort(key=lambda x: x['start'], reverse=True)
        
        # 替换为 token
        for match in matches:
            original = match['text']
            ph_type = match['type']
            
            # 生成 token 名称
            if ph_type == 'PH':
                self.ph_counter += 1
                token_name = f"PH_{self.ph_counter}"
            else:  # TAG
                self.tag_counter += 1
                token_name = f"TAG_{self.tag_counter}"
            
            token = f"⟦{token_name}⟧"
            
            # 替换文本
            result = result[:match['start']] + token + result[match['end']:]
            
            # 记录映射
            local_map[token_name] = original
            self.placeholder_map[token_name] = original
        
        return result, local_map
    
    def reset_counters(self) -> None:
        """重置计数器（用于处理新文件）"""
        self.ph_counter = 0
        self.tag_counter = 0
        self.placeholder_map = {}


class NormalizeGuard:
    """主处理类：规范化输入并生成 draft.csv 和 placeholder_map.json"""
    
    def __init__(self, input_path: str, output_draft_path: str, 
                 output_map_path: str, schema_path: str):
        self.input_path = Path(input_path)
        self.output_draft_path = Path(output_draft_path)
        self.output_map_path = Path(output_map_path)
        self.schema_path = Path(schema_path)
        
        self.freezer = PlaceholderFreezer(schema_path)
        self.errors: List[str] = []
        self.warnings: List[str] = []
    
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
            with open(self.input_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                headers = reader.fieldnames
                
                if not self.validate_input_headers(headers):
                    return False, []
                
                processed_rows = []
                seen_ids = set()
                
                for idx, row in enumerate(reader, start=2):
                    string_id = row.get('string_id', '').strip()
                    source_zh = row.get('source_zh', '').strip()
                    
                    # 验证 string_id
                    if not string_id:
                        self.errors.append(f"Row {idx}: Empty string_id")
                        continue
                    
                    if string_id in seen_ids:
                        self.errors.append(f"Row {idx}: Duplicate string_id '{string_id}'")
                        continue
                    
                    seen_ids.add(string_id)
                    
                    # 冻结占位符
                    tokenized_zh, local_map = self.freezer.freeze_text(source_zh)
                    
                    # 构建输出行
                    output_row = {
                        'string_id': string_id,
                        'source_zh': source_zh,
                        'tokenized_zh': tokenized_zh,
                    }
                    
                    # 保留其他列
                    for key in headers:
                        if key not in ['string_id', 'source_zh']:
                            output_row[key] = row.get(key, '')
                    
                    processed_rows.append(output_row)
                    
                    # 如果有占位符，打印信息
                    if local_map:
                        print(f"  Row {idx} ({string_id}): Froze {len(local_map)} placeholders")
                
                return len(self.errors) == 0, processed_rows
                
        except FileNotFoundError:
            self.errors.append(f"Input file not found: {self.input_path}")
            return False, []
        except Exception as e:
            self.errors.append(f"Error processing CSV: {str(e)}")
            return False, []
    
    def write_draft_csv(self, rows: List[Dict]) -> bool:
        """写入 draft.csv"""
        try:
            if not rows:
                self.warnings.append("No rows to write")
                return True
            
            # 确保列顺序
            fieldnames = ['string_id', 'source_zh', 'tokenized_zh']
            # 添加其他列
            for key in rows[0].keys():
                if key not in fieldnames:
                    fieldnames.append(key)
            
            with open(self.output_draft_path, 'w', encoding='utf-8', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(rows)
            
            print(f"✅ Wrote {len(rows)} rows to {self.output_draft_path}")
            return True
            
        except Exception as e:
            self.errors.append(f"Error writing draft CSV: {str(e)}")
            return False
    
    def write_placeholder_map(self) -> bool:
        """写入 placeholder_map.json"""
        try:
            output = {
                'metadata': {
                    'generated_at': datetime.now().isoformat(),
                    'input_file': str(self.input_path),
                    'total_placeholders': len(self.freezer.placeholder_map),
                    'version': '1.0'
                },
                'mappings': self.freezer.placeholder_map
            }
            
            with open(self.output_map_path, 'w', encoding='utf-8') as f:
                json.dump(output, f, indent=2, ensure_ascii=False)
            
            print(f"✅ Wrote {len(self.freezer.placeholder_map)} placeholder mappings to {self.output_map_path}")
            return True
            
        except Exception as e:
            self.errors.append(f"Error writing placeholder map: {str(e)}")
            return False
    
    def run(self) -> bool:
        """执行规范化流程"""
        print(f"🚀 Starting normalize guard...")
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
        
        # 打印总结
        self._print_summary(rows)
        
        return True
    
    def _print_errors(self) -> None:
        """打印错误信息"""
        if self.warnings:
            print("\n⚠️  Warnings:")
            for warning in self.warnings:
                print(f"   {warning}")
        
        if self.errors:
            print("\n❌ Errors:")
            for error in self.errors:
                print(f"   {error}")
    
    def _print_summary(self, rows: List[Dict]) -> None:
        """打印处理总结"""
        print(f"\n📊 Summary:")
        print(f"   Total strings processed: {len(rows)}")
        print(f"   Total placeholders frozen: {len(self.freezer.placeholder_map)}")
        print(f"   PH tokens: {self.freezer.ph_counter}")
        print(f"   TAG tokens: {self.freezer.tag_counter}")
        
        if self.warnings:
            print(f"   Warnings: {len(self.warnings)}")
        
        print(f"\n✅ Normalization complete!")


def main():
    """主入口"""
    if len(sys.argv) != 5:
        print("Usage: python normalize_guard.py <input_csv> <output_draft_csv> <output_map_json> <schema_yaml>")
        print()
        print("Example:")
        print("  python normalize_guard.py data/input.csv data/draft.csv data/placeholder_map.json workflow/placeholder_schema.yaml")
        sys.exit(1)
    
    guard = NormalizeGuard(
        input_path=sys.argv[1],
        output_draft_path=sys.argv[2],
        output_map_path=sys.argv[3],
        schema_path=sys.argv[4]
    )
    
    success = guard.run()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
