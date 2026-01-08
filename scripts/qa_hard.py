#!/usr/bin/env python3
"""
QA Hard Script
对 tokenized 翻译文本进行硬性规则校验

Usage:
    python qa_hard.py <translated_csv> <placeholder_map_json> <schema_yaml> <forbidden_txt> <report_json>
"""

import csv
import json
import re
import sys
import yaml
from pathlib import Path
from typing import List, Dict, Set, Tuple
from datetime import datetime
from collections import Counter


class QAHardValidator:
    """硬性规则校验器"""
    
    def __init__(self, translated_csv: str, placeholder_map: str, 
                 schema_yaml: str, forbidden_txt: str, report_json: str):
        self.translated_csv = Path(translated_csv)
        self.placeholder_map_path = Path(placeholder_map)
        self.schema_yaml = Path(schema_yaml)
        self.forbidden_txt = Path(forbidden_txt)
        self.report_json = Path(report_json)
        
        # 数据
        self.placeholder_map: Dict[str, str] = {}
        self.forbidden_patterns: List[str] = []
        self.tag_patterns: List[str] = []
        
        # 错误收集
        self.errors: List[Dict] = []
        self.error_counts: Dict[str, int] = {
            'token_mismatch': 0,
            'tag_unbalanced': 0,
            'forbidden_hit': 0,
            'new_placeholder_found': 0
        }
        self.total_rows = 0
        
        # Token 正则
        self.token_pattern = re.compile(r'⟦(PH_\d+|TAG_\d+)⟧')
    
    def load_placeholder_map(self) -> bool:
        """加载占位符映射"""
        try:
            with open(self.placeholder_map_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.placeholder_map = data.get('mappings', {})
            print(f"✅ Loaded {len(self.placeholder_map)} placeholder mappings")
            return True
        except FileNotFoundError:
            print(f"❌ Error: Placeholder map not found: {self.placeholder_map_path}")
            return False
        except Exception as e:
            print(f"❌ Error loading placeholder map: {str(e)}")
            return False
    
    def load_schema(self) -> bool:
        """加载 schema，提取标签模式"""
        try:
            with open(self.schema_yaml, 'r', encoding='utf-8') as f:
                schema = yaml.safe_load(f)
                patterns = schema.get('placeholder_patterns', [])
                
                # 提取所有 TAG 类型的模式
                for pattern_def in patterns:
                    if pattern_def.get('type') == 'TAG':
                        self.tag_patterns.append(pattern_def['pattern'])
                
            print(f"✅ Loaded schema with {len(self.tag_patterns)} tag patterns")
            return True
        except FileNotFoundError:
            print(f"⚠️  Warning: Schema not found, skipping tag validation")
            return True
        except Exception as e:
            print(f"⚠️  Warning: Error loading schema: {str(e)}")
            return True
    
    def load_forbidden_patterns(self) -> bool:
        """加载禁用模式"""
        try:
            with open(self.forbidden_txt, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        self.forbidden_patterns.append(line)
            
            print(f"✅ Loaded {len(self.forbidden_patterns)} forbidden patterns")
            return True
        except FileNotFoundError:
            print(f"⚠️  Warning: Forbidden patterns file not found")
            return True
        except Exception as e:
            print(f"⚠️  Warning: Error loading forbidden patterns: {str(e)}")
            return True
    
    def extract_tokens(self, text: str) -> Set[str]:
        """提取文本中的所有 token"""
        if not text:
            return set()
        return set(self.token_pattern.findall(text))
    
    def check_token_mismatch(self, string_id: str, source_text: str, 
                            target_text: str, row_num: int) -> None:
        """检查 token 是否匹配"""
        source_tokens = self.extract_tokens(source_text)
        target_tokens = self.extract_tokens(target_text)
        
        missing = source_tokens - target_tokens
        extra = target_tokens - source_tokens
        
        if missing:
            for token in missing:
                self.errors.append({
                    'row': row_num,
                    'string_id': string_id,
                    'type': 'token_mismatch',
                    'detail': f"missing ⟦{token}⟧ in target_text",
                    'source': source_text,
                    'target': target_text
                })
                self.error_counts['token_mismatch'] += 1
        
        if extra:
            for token in extra:
                self.errors.append({
                    'row': row_num,
                    'string_id': string_id,
                    'type': 'token_mismatch',
                    'detail': f"extra ⟦{token}⟧ in target_text",
                    'source': source_text,
                    'target': target_text
                })
                self.error_counts['token_mismatch'] += 1
    
    def check_tag_balance(self, string_id: str, target_text: str, 
                         row_num: int) -> None:
        """检查标签是否平衡（成对出现）"""
        if not target_text:
            return
        
        # 提取所有 TAG token
        tokens = self.extract_tokens(target_text)
        tag_tokens = [t for t in tokens if t.startswith('TAG_')]
        
        if not tag_tokens:
            return
        
        # 检查每个 TAG 对应的原始标签
        opening_tags = []
        closing_tags = []
        
        for tag_token in tag_tokens:
            original = self.placeholder_map.get(tag_token, '')
            
            # 简单判断：以 </ 开头的是闭合标签
            if original.startswith('</'):
                closing_tags.append(tag_token)
            elif original.startswith('<') and not original.startswith('</'):
                opening_tags.append(tag_token)
        
        # 检查数量是否平衡
        if len(opening_tags) != len(closing_tags):
            self.errors.append({
                'row': row_num,
                'string_id': string_id,
                'type': 'tag_unbalanced',
                'detail': f"unbalanced tags: {len(opening_tags)} opening, {len(closing_tags)} closing",
                'target': target_text,
                'opening_tags': opening_tags,
                'closing_tags': closing_tags
            })
            self.error_counts['tag_unbalanced'] += 1
    
    def check_forbidden_patterns(self, string_id: str, target_text: str, 
                                 row_num: int) -> None:
        """检查禁用模式"""
        if not target_text:
            return
        
        for pattern in self.forbidden_patterns:
            try:
                if re.search(pattern, target_text, re.IGNORECASE):
                    self.errors.append({
                        'row': row_num,
                        'string_id': string_id,
                        'type': 'forbidden_hit',
                        'detail': f"matched forbidden pattern: {pattern}",
                        'target': target_text
                    })
                    self.error_counts['forbidden_hit'] += 1
            except re.error as e:
                # 跳过无效的正则表达式
                pass
    
    def check_new_placeholders(self, string_id: str, target_text: str, 
                              row_num: int) -> None:
        """检查是否出现了未经冻结的新占位符"""
        if not target_text:
            return
        
        # 检查常见占位符模式（应该已经被冻结）
        suspicious_patterns = [
            (r'\{\d+\}', 'C# numbered placeholder'),
            (r'\{[a-zA-Z_][a-zA-Z0-9_]*\}', 'C# named placeholder'),
            (r'%[sdf]', 'printf-style placeholder'),
            (r'<color=#?[0-9A-Fa-f]{6,8}>', 'Unity color tag'),
            (r'</color>', 'Unity closing tag'),
        ]
        
        for pattern, desc in suspicious_patterns:
            matches = re.findall(pattern, target_text)
            if matches:
                for match in matches:
                    self.errors.append({
                        'row': row_num,
                        'string_id': string_id,
                        'type': 'new_placeholder_found',
                        'detail': f"found unfrozen {desc}: {match}",
                        'target': target_text
                    })
                    self.error_counts['new_placeholder_found'] += 1
    
    def validate_csv(self) -> bool:
        """验证 CSV 文件"""
        try:
            with open(self.translated_csv, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                
                # 检查必需字段
                required_fields = ['string_id', 'tokenized_zh']
                if not all(field in reader.fieldnames for field in required_fields):
                    print(f"❌ Error: Missing required fields. Need: {required_fields}")
                    return False
                
                # 检查是否有翻译列
                target_field = None
                for possible_field in ['target_text', 'translated_text', 'target_zh', 'tokenized_target']:
                    if possible_field in reader.fieldnames:
                        target_field = possible_field
                        break
                
                if not target_field:
                    print(f"❌ Error: No target translation field found")
                    print(f"   Available fields: {reader.fieldnames}")
                    return False
                
                print(f"✅ Using '{target_field}' as target translation field")
                print()
                
                # 逐行验证
                for idx, row in enumerate(reader, start=2):
                    self.total_rows += 1
                    
                    string_id = row.get('string_id', '')
                    source_text = row.get('tokenized_zh', '')
                    target_text = row.get(target_field, '')
                    
                    # 跳过空翻译
                    if not target_text or not target_text.strip():
                        continue
                    
                    # 运行所有检查
                    self.check_token_mismatch(string_id, source_text, target_text, idx)
                    self.check_tag_balance(string_id, target_text, idx)
                    self.check_forbidden_patterns(string_id, target_text, idx)
                    self.check_new_placeholders(string_id, target_text, idx)
                
                return True
                
        except FileNotFoundError:
            print(f"❌ Error: Translated CSV not found: {self.translated_csv}")
            return False
        except Exception as e:
            print(f"❌ Error validating CSV: {str(e)}")
            import traceback
            traceback.print_exc()
            return False
    
    def generate_report(self) -> None:
        """生成 JSON 报告"""
        report = {
            'has_errors': len(self.errors) > 0,
            'total_rows': self.total_rows,
            'error_counts': self.error_counts,
            'errors': self.errors,
            'metadata': {
                'generated_at': datetime.now().isoformat(),
                'input_file': str(self.translated_csv),
                'total_errors': len(self.errors)
            }
        }
        
        with open(self.report_json, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
    
    def print_summary(self) -> None:
        """打印验证总结"""
        print(f"\n📊 QA Validation Summary:")
        print(f"   Total rows checked: {self.total_rows}")
        print(f"   Total errors: {len(self.errors)}")
        print()
        
        if self.error_counts['token_mismatch'] > 0:
            print(f"   ❌ Token mismatch: {self.error_counts['token_mismatch']}")
        
        if self.error_counts['tag_unbalanced'] > 0:
            print(f"   ❌ Tag unbalanced: {self.error_counts['tag_unbalanced']}")
        
        if self.error_counts['forbidden_hit'] > 0:
            print(f"   ❌ Forbidden patterns: {self.error_counts['forbidden_hit']}")
        
        if self.error_counts['new_placeholder_found'] > 0:
            print(f"   ❌ New placeholders found: {self.error_counts['new_placeholder_found']}")
        
        print()
        
        if len(self.errors) > 0:
            print(f"❌ Validation FAILED with {len(self.errors)} errors")
            print(f"   See detailed report: {self.report_json}")
            print()
            print("   Sample errors:")
            for error in self.errors[:5]:
                print(f"   - [{error['type']}] {error['string_id']}: {error['detail']}")
        else:
            print(f"✅ All checks passed!")
            print(f"   Report saved to: {self.report_json}")
    
    def run(self) -> bool:
        """运行 QA 验证"""
        print(f"🚀 Starting QA Hard validation...")
        print(f"   Input CSV: {self.translated_csv}")
        print(f"   Placeholder map: {self.placeholder_map_path}")
        print(f"   Schema: {self.schema_yaml}")
        print(f"   Forbidden patterns: {self.forbidden_txt}")
        print(f"   Output report: {self.report_json}")
        print()
        
        # 加载资源
        if not self.load_placeholder_map():
            return False
        
        self.load_schema()
        self.load_forbidden_patterns()
        
        print()
        
        # 验证 CSV
        if not self.validate_csv():
            return False
        
        # 生成报告
        self.generate_report()
        
        # 打印总结
        self.print_summary()
        
        return len(self.errors) == 0


def main():
    """主入口"""
    if len(sys.argv) != 6:
        print("Usage: python qa_hard.py <translated_csv> <placeholder_map_json> <schema_yaml> <forbidden_txt> <report_json>")
        print()
        print("Example:")
        print("  python qa_hard.py data/translated.csv data/placeholder_map.json workflow/placeholder_schema.yaml workflow/forbidden_patterns.txt data/qa_report.json")
        sys.exit(1)
    
    validator = QAHardValidator(
        translated_csv=sys.argv[1],
        placeholder_map=sys.argv[2],
        schema_yaml=sys.argv[3],
        forbidden_txt=sys.argv[4],
        report_json=sys.argv[5]
    )
    
    success = validator.run()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
