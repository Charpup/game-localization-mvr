#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Rehydrate Export Script v2.0
将 tokenized 文本还原为原始占位符

融合版本：结合 v1.0 的完整性和 v2.0 的简洁性

Usage:
    python rehydrate_export.py <translated_csv> <placeholder_map_json> <final_csv> [--overwrite]

Features:
    - 支持 v1.0 和 v2.0 placeholder_map 格式
    - 多 target 字段支持
    - 详细的错误处理（fail fast）
    - 可选覆盖模式（--overwrite 直接修改 target_text）
    - Token 还原统计
"""

import csv
import json
import re
import sys
from pathlib import Path
from typing import Dict, Set, List
from datetime import datetime


class RehydrateExporter:
    """Token 还原导出器 v2.0"""
    
    def __init__(self, translated_csv: str, placeholder_map: str, final_csv: str, 
                 overwrite_mode: bool = False):
        self.translated_csv = Path(translated_csv)
        self.placeholder_map_path = Path(placeholder_map)
        self.final_csv = Path(final_csv)
        self.overwrite_mode = overwrite_mode
        
        self.placeholder_map: Dict[str, str] = {}
        self.map_version = "unknown"
        self.token_pattern = re.compile(r'⟦(PH_\d+|TAG_\d+)⟧')
        
        self.errors: List[str] = []
        self.total_rows = 0
        self.tokens_restored = 0
    
    def load_placeholder_map(self) -> bool:
        """加载占位符映射（支持 v1.0 和 v2.0 格式）"""
        try:
            with open(self.placeholder_map_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # 检测格式版本
            if 'mappings' in data:
                # v2.0 格式：有 metadata 和 mappings
                self.placeholder_map = data['mappings']
                metadata = data.get('metadata', {})
                self.map_version = metadata.get('version', '2.0')
                print(f"✅ Loaded placeholder_map v{self.map_version}")
            else:
                # v1.0 格式：直接是 dict
                self.placeholder_map = data
                self.map_version = "1.0"
                print(f"✅ Loaded placeholder_map v{self.map_version} (legacy format)")
            
            print(f"   Total mappings: {len(self.placeholder_map)}")
            return True
            
        except FileNotFoundError:
            print(f"❌ Error: Placeholder map not found: {self.placeholder_map_path}")
            return False
        except json.JSONDecodeError as e:
            print(f"❌ Error: Invalid JSON in placeholder map: {e}")
            return False
        except Exception as e:
            print(f"❌ Error loading placeholder map: {str(e)}")
            return False
    
    def extract_tokens(self, text: str) -> Set[str]:
        """提取文本中的所有 token"""
        if not text:
            return set()
        return set(self.token_pattern.findall(text))
    
    def rehydrate_text(self, text: str, string_id: str, row_num: int) -> str:
        """
        还原文本中的 token
        
        如果发现未知 token，直接报错并返回 None
        """
        if not text:
            return text
        
        # 提取所有 token
        tokens = self.extract_tokens(text)
        
        # 检查是否有未知 token
        unknown_tokens = []
        for token in tokens:
            if token not in self.placeholder_map:
                unknown_tokens.append(token)
        
        if unknown_tokens:
            error_msg = (
                f"Row {row_num}, string_id '{string_id}': "
                f"Unknown token(s): {unknown_tokens}"
            )
            print(f"\n❌ FATAL ERROR: {error_msg}")
            print(f"   These tokens are not in placeholder_map.json.")
            print(f"   This should have been caught by qa_hard.py validation.")
            self.errors.append(error_msg)
            return None  # 返回 None 表示错误
        
        # 还原所有 token
        result = text
        for token in tokens:
            original = self.placeholder_map[token]
            token_with_brackets = f"⟦{token}⟧"
            result = result.replace(token_with_brackets, original)
            self.tokens_restored += 1
        
        return result
    
    def process_csv(self) -> bool:
        """处理 CSV 文件"""
        try:
            with open(self.translated_csv, 'r', encoding='utf-8-sig', newline='') as f:
                reader = csv.DictReader(f)
                headers = reader.fieldnames
                
                # 检查必需字段
                if 'string_id' not in headers:
                    print("❌ Error: Missing 'string_id' column")
                    return False
                
                # 查找目标翻译列
                target_field = None
                for possible_field in ['target_text', 'translated_text', 'target_zh', 'tokenized_target']:
                    if possible_field in headers:
                        target_field = possible_field
                        break
                
                if not target_field:
                    print(f"❌ Error: No target translation field found")
                    print(f"   Available fields: {headers}")
                    return False
                
                print(f"✅ Using '{target_field}' as target translation field")
                if self.overwrite_mode:
                    print(f"✅ Overwrite mode: will modify '{target_field}' directly")
                else:
                    print(f"✅ Add column mode: will add 'rehydrated_text' column")
                print()
                
                # 处理每一行
                processed_rows = []
                
                for idx, row in enumerate(reader, start=2):
                    self.total_rows += 1
                    
                    string_id = row.get('string_id', '')
                    target_text = row.get(target_field, '')
                    
                    # 还原 token
                    rehydrated = self.rehydrate_text(target_text, string_id, idx)
                    
                    if rehydrated is None:
                        # 发现错误，直接退出
                        return False
                    
                    # 构建输出行
                    output_row = dict(row)
                    
                    if self.overwrite_mode:
                        # 覆盖模式：直接修改 target_text
                        output_row[target_field] = rehydrated
                    else:
                        # 添加新列模式
                        output_row['rehydrated_text'] = rehydrated
                    
                    processed_rows.append(output_row)
                
                # 写入输出文件
                return self.write_final_csv(processed_rows, headers, target_field)
                
        except FileNotFoundError:
            print(f"❌ Error: Translated CSV not found: {self.translated_csv}")
            return False
        except Exception as e:
            print(f"❌ Error processing CSV: {str(e)}")
            import traceback
            traceback.print_exc()
            return False
    
    def write_final_csv(self, rows: List[Dict], original_headers: List[str], 
                       target_field: str) -> bool:
        """写入最终 CSV"""
        try:
            # 构建输出列
            fieldnames = list(original_headers)
            
            if not self.overwrite_mode and 'rehydrated_text' not in fieldnames:
                # 在 target_field 后面插入 rehydrated_text
                target_idx = fieldnames.index(target_field)
                fieldnames.insert(target_idx + 1, 'rehydrated_text')
            
            # 创建输出目录
            self.final_csv.parent.mkdir(parents=True, exist_ok=True)
            
            with open(self.final_csv, 'w', encoding='utf-8-sig', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(rows)
            
            print(f"✅ Wrote {len(rows)} rows to {self.final_csv}")
            return True
            
        except Exception as e:
            print(f"❌ Error writing final CSV: {str(e)}")
            return False
    
    def print_summary(self) -> None:
        """打印处理总结"""
        print(f"\n📊 Rehydrate Export v2.0 Summary:")
        print(f"   Placeholder map version: {self.map_version}")
        print(f"   Total rows processed: {self.total_rows}")
        print(f"   Total tokens restored: {self.tokens_restored}")
        print(f"   Output mode: {'overwrite' if self.overwrite_mode else 'add column'}")
        print(f"   Output file: {self.final_csv}")
        print()
        print(f"✅ Rehydration complete!")
    
    def run(self) -> bool:
        """运行还原流程"""
        print(f"🚀 Starting rehydrate export v2.0...")
        print(f"   Input CSV: {self.translated_csv}")
        print(f"   Placeholder map: {self.placeholder_map_path}")
        print(f"   Output CSV: {self.final_csv}")
        print()
        
        # 加载占位符映射
        if not self.load_placeholder_map():
            return False
        
        print()
        
        # 处理 CSV
        if not self.process_csv():
            print()
            print("❌ Rehydration FAILED")
            print("   Please run qa_hard.py to validate translations before rehydrating.")
            return False
        
        # 打印总结
        self.print_summary()
        
        return True


def main():
    """主入口"""
    # 解析参数
    args = sys.argv[1:]
    overwrite_mode = '--overwrite' in args
    
    # 移除 --overwrite 标志
    args = [a for a in args if a != '--overwrite']
    
    if len(args) != 3:
        print("Usage: python rehydrate_export.py <translated_csv> <placeholder_map_json> <final_csv> [--overwrite]")
        print()
        print("Options:")
        print("  --overwrite    Modify target_text directly instead of adding rehydrated_text column")
        print()
        print("Example:")
        print("  python rehydrate_export.py data/translated.csv data/placeholder_map.json data/final.csv")
        print("  python rehydrate_export.py data/translated.csv data/placeholder_map.json data/final.csv --overwrite")
        sys.exit(1)
    
    exporter = RehydrateExporter(
        translated_csv=args[0],
        placeholder_map=args[1],
        final_csv=args[2],
        overwrite_mode=overwrite_mode
    )
    
    success = exporter.run()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
