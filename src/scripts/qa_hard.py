#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
QA Hard Script v2.0
对 tokenized 翻译文本进行硬性规则校验

融合版本：结合 v1.0 的完整性和 v2.0 的现代化特性

Usage:
    python qa_hard.py <translated_csv> <placeholder_map_json> <schema_yaml> <forbidden_txt> <report_json>

Features:
    - 使用 schema v2.0 格式 (patterns, paired_tags)
    - 4 类错误检查：token_mismatch, tag_unbalanced, forbidden_hit, new_placeholder_found
    - 使用 paired_tags 进行精确的标签配对检查
    - 动态加载新占位符检测模式
    - 性能优化（编译正则）
    - 限制错误输出（2000条）
    - 向后兼容 schema v1.0
"""

import csv
import json
import re
import sys
from pathlib import Path
from typing import List, Dict, Set, Tuple
from datetime import datetime
from collections import Counter

# Ensure UTF-8 output on Windows
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

try:
    import yaml
except ImportError:
    print("❌ Error: PyYAML is required. Install with: pip install pyyaml")
    sys.exit(1)


class QAHardValidator:
    """硬性规则校验器 v2.0"""
    
    def __init__(self, translated_csv: str, placeholder_map: str,
                 schema_yaml: str, forbidden_txt: str, report_json: str):
        self.translated_csv = Path(translated_csv)
        self.placeholder_map_path = Path(placeholder_map)
        self.schema_yaml = Path(schema_yaml)
        self.forbidden_txt = Path(forbidden_txt)
        self.report_json = Path(report_json)
        
        # 数据
        self.placeholder_map: Dict[str, str] = {}
        self.paired_tags: List[Dict] = []
        self.compiled_patterns: List[re.Pattern] = []
        self.compiled_forbidden: List[re.Pattern] = []
        
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
        """加载 schema v2.0（支持 v1.0 fallback）"""
        try:
            with open(self.schema_yaml, 'r', encoding='utf-8') as f:
                schema = yaml.safe_load(f)
                schema_version = schema.get('version', 1)
                
                # 尝试 v2.0 格式
                patterns = schema.get('patterns', None)
                if patterns is None:
                    # Fallback 到 v1.0 格式
                    patterns = schema.get('placeholder_patterns', [])
                    print(f"⚠️  Using schema v1.0 format (placeholder_patterns)")
                else:
                    print(f"✅ Using schema v2.0 format (patterns)")
                
                # 编译所有模式用于新占位符检测
                for pattern_def in patterns:
                    try:
                        regex = pattern_def.get('regex') or pattern_def.get('pattern')
                        if regex:
                            self.compiled_patterns.append(re.compile(regex))
                    except re.error as e:
                        print(f"⚠️  Warning: Invalid regex in pattern '{pattern_def.get('name')}': {e}")
                
                # 加载 paired_tags（v2.0 新特性）
                self.paired_tags = schema.get('paired_tags', [])
                
                print(f"✅ Loaded schema with {len(self.compiled_patterns)} patterns")
                if self.paired_tags:
                    print(f"✅ Loaded {len(self.paired_tags)} paired tag rules")
                
                return True
                
        except FileNotFoundError:
            print(f"⚠️  Warning: Schema not found, skipping advanced validation")
            return True
        except Exception as e:
            print(f"⚠️  Warning: Error loading schema: {str(e)}")
            return True
    
    def load_forbidden_patterns(self) -> bool:
        """加载禁用模式（编译正则）"""
        try:
            with open(self.forbidden_txt, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        try:
                            self.compiled_forbidden.append(re.compile(line))
                        except re.error as e:
                            print(f"⚠️  Warning: Invalid forbidden pattern '{line}': {e}")
            
            print(f"✅ Loaded {len(self.compiled_forbidden)} forbidden patterns")
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
        """
        检查标签是否平衡（使用 paired_tags 配置）
        
        v2.0 新特性：使用 schema 中的 paired_tags 进行精确配对检查
        Fallback：如果没有 paired_tags，使用简单的开放/闭合标签计数
        """
        if not target_text:
            return
        
        # 提取所有 TAG token
        tokens = self.extract_tokens(target_text)
        tag_tokens = [t for t in tokens if t.startswith('TAG_')]
        
        if not tag_tokens:
            return
        
        # 如果有 paired_tags 配置，使用精确配对检查
        if self.paired_tags:
            self._check_paired_tags(string_id, target_text, tag_tokens, row_num)
        else:
            # Fallback：简单的开放/闭合标签计数
            self._check_tag_count(string_id, target_text, tag_tokens, row_num)
    
    def _check_paired_tags(self, string_id: str, target_text: str,
                          tag_tokens: List[str], row_num: int) -> None:
        """使用 paired_tags 配置进行精确配对检查"""
        # 统计每种标签对的数量
        for pair_config in self.paired_tags:
            open_pattern = pair_config['open']
            close_pattern = pair_config['close']
            
            open_count = 0
            close_count = 0
            
            for tag_token in tag_tokens:
                original = self.placeholder_map.get(tag_token, '')
                if open_pattern in original and not original.startswith('</'):
                    open_count += 1
                elif close_pattern in original:
                    close_count += 1
            
            # 检查配对是否平衡
            if open_count != close_count:
                self.errors.append({
                    'row': row_num,
                    'string_id': string_id,
                    'type': 'tag_unbalanced',
                    'detail': f"unbalanced {pair_config.get('description', 'tags')}: {open_count} opening, {close_count} closing",
                    'target': target_text,
                    'open_pattern': open_pattern,
                    'close_pattern': close_pattern
                })
                self.error_counts['tag_unbalanced'] += 1
    
    def _check_tag_count(self, string_id: str, target_text: str,
                        tag_tokens: List[str], row_num: int) -> None:
        """Fallback：简单的开放/闭合标签计数"""
        opening_tags = []
        closing_tags = []
        
        for tag_token in tag_tokens:
            original = self.placeholder_map.get(tag_token, '')
            
            if original.startswith('</'):
                closing_tags.append(tag_token)
            elif original.startswith('<') and not original.startswith('</'):
                opening_tags.append(tag_token)
        
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
        """检查禁用模式（使用编译的正则）"""
        if not target_text:
            return
        
        for pattern in self.compiled_forbidden:
            try:
                if pattern.search(target_text):
                    self.errors.append({
                        'row': row_num,
                        'string_id': string_id,
                        'type': 'forbidden_hit',
                        'detail': f"matched forbidden pattern: {pattern.pattern}",
                        'target': target_text
                    })
                    self.error_counts['forbidden_hit'] += 1
                    break  # 只报告第一个匹配的禁用模式
            except Exception:
                pass
    
    def check_new_placeholders(self, string_id: str, target_text: str,
                              row_num: int) -> None:
        """
        检查是否出现了未经冻结的新占位符
        
        v2.0 改进：动态从 schema 加载检测模式
        """
        if not target_text:
            return
        
        # 使用从 schema 加载的模式
        for pattern in self.compiled_patterns:
            try:
                matches = pattern.findall(target_text)
                if matches:
                    # 确保匹配的不是 token 格式（⟦...⟧）
                    for match in matches:
                        if isinstance(match, tuple):
                            match = match[0] if match else ''
                        
                        # 跳过已经是 token 的
                        if match.startswith('⟦') or '⟦' in match:
                            continue
                        
                        self.errors.append({
                            'row': row_num,
                            'string_id': string_id,
                            'type': 'new_placeholder_found',
                            'detail': f"found unfrozen placeholder: {match}",
                            'target': target_text,
                            'pattern': pattern.pattern
                        })
                        self.error_counts['new_placeholder_found'] += 1
                        break  # 每个模式只报告一次
            except Exception:
                pass
    
    def validate_csv(self) -> bool:
        """验证 CSV 文件"""
        try:
            with open(self.translated_csv, 'r', encoding='utf-8-sig', newline='') as f:
                reader = csv.DictReader(f)
                
                # 检查必需字段
                required_fields = ['string_id', 'tokenized_zh']
                if not all(field in reader.fieldnames for field in required_fields):
                    print(f"❌ Error: Missing required fields. Need: {required_fields}")
                    return False
                
                # 检查是否有翻译列
                target_field = None
                for possible_field in ['target_text', 'translated_text', 'target_zh', 'tokenized_target', 'target_ru', 'target_en']:
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
                    source_text = row.get('tokenized_zh') or row.get('source_zh') or ''
                    target_text = row.get(target_field, '')
                    
                    # 跳过空翻译
                    if not target_text or not target_text.strip():
                        continue
                    
                    # 运行所有检查
                    self.check_token_mismatch(string_id, source_text, target_text, idx)
                    self.check_tag_balance(string_id, target_text, idx)
                    self.check_forbidden_patterns(string_id, target_text, idx)
                    self.check_new_placeholders(string_id, target_text, idx)
                    self.check_length_overflow(string_id, target_text, row, idx)
                
                return True

                
        except FileNotFoundError:
            print(f"❌ Error: Translated CSV not found: {self.translated_csv}")
            return False
        except Exception as e:
            print(f"❌ Error validating CSV: {str(e)}")
            import traceback
            traceback.print_exc()
            return False
    
    def check_length_overflow(self, string_id: str, target_text: str, row: Dict, row_num: int):
        """检查长度溢出"""
        max_len = row.get("max_length_target") or row.get("max_len_target")
        if not max_len:
            return
            
        try:
            limit = int(float(max_len))
            if limit <= 0: return
        except ValueError:
            return

        actual_len = len(target_text)
        if actual_len > limit:
            overflow_ratio = actual_len / limit
            severity = "critical" if overflow_ratio > 1.5 else "major"
            
            self.errors.append({
                "row": row_num,
                "string_id": string_id,
                "type": "length_overflow",
                "severity": severity,
                "detail": f"Length {actual_len} > {limit} (ratio: {overflow_ratio:.2f})",
                "source": row.get('tokenized_zh', '')[:50],
                "target": target_text[:50]
            })
            self.error_counts['length_overflow'] = self.error_counts.get('length_overflow', 0) + 1

    def generate_report(self) -> None:
        """生成 JSON 报告（限制错误数量）"""
        report = {
            'has_errors': len(self.errors) > 0,
            'total_rows': self.total_rows,
            'error_counts': self.error_counts,
            'errors': self.errors[:2000],  # 限制到 2000 条
            'metadata': {
                'version': '2.0',
                'generated_at': datetime.now().isoformat(),
                'input_file': str(self.translated_csv),
                'total_errors': len(self.errors),
                'errors_truncated': len(self.errors) > 2000
            }
        }
        
        # 创建输出目录
        self.report_json.parent.mkdir(parents=True, exist_ok=True)
        
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
            if len(self.errors) > 2000:
                print(f"   ⚠️  Report truncated to 2000 errors (total: {len(self.errors)})")
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
        print(f"🚀 Starting QA Hard validation v2.0...")
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
    import argparse
    
    ap = argparse.ArgumentParser(description="QA Hard - 硬性规则校验")
    ap.add_argument("translated_csv", nargs="?", default="data/translated.csv",
                    help="Input translated CSV (default: data/translated.csv)")
    ap.add_argument("placeholder_map", nargs="?", default="data/placeholder_map.json",
                    help="Placeholder map JSON (default: data/placeholder_map.json)")
    ap.add_argument("schema_yaml", nargs="?", default="workflow/placeholder_schema.yaml",
                    help="Schema YAML (default: workflow/placeholder_schema.yaml)")
    ap.add_argument("forbidden_txt", nargs="?", default="workflow/forbidden_patterns.txt",
                    help="Forbidden patterns TXT (default: workflow/forbidden_patterns.txt)")
    ap.add_argument("report_json", nargs="?", default="data/qa_hard_report.json",
                    help="Output report JSON (default: data/qa_hard_report.json)")
    
    args = ap.parse_args()
    
    validator = QAHardValidator(
        translated_csv=args.translated_csv,
        placeholder_map=args.placeholder_map,
        schema_yaml=args.schema_yaml,
        forbidden_txt=args.forbidden_txt,
        report_json=args.report_json
    )
    
    success = validator.run()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()

