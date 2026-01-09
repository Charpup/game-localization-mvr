#!/usr/bin/env python3
"""
Extract Terms Script
从源文本中提取专业术语候选

Usage:
    python extract_terms.py <input_csv> <output_candidates_yaml> <glossary_yaml> [options]
"""

import csv
import re
import sys
import yaml
from pathlib import Path
from typing import Dict, List, Set, Tuple
from datetime import datetime
from collections import Counter, defaultdict

# 尝试导入 jieba
try:
    import jieba
    JIEBA_AVAILABLE = True
except ImportError:
    JIEBA_AVAILABLE = False


class TermExtractor:
    """术语提取器"""
    
    def __init__(self, input_csv: str, glossary_yaml: str = None):
        self.input_csv = Path(input_csv)
        self.glossary_path = Path(glossary_yaml) if glossary_yaml else None
        
        # 检查 jieba 是否可用
        if not JIEBA_AVAILABLE:
            raise RuntimeError(
                "错误：jieba 分词库未安装。\n"
                "请运行：pip install jieba\n"
                "jieba 是必需的依赖，用于中文分词以确保术语提取的准确性。"
            )
        
        self.source_texts: List[Dict] = []
        self.glossary_terms: Set[str] = set()
        self.term_frequencies: Counter = Counter()
        self.term_positions: Dict[str, List[str]] = defaultdict(list)
        
        # 停用词列表（常见的、不应作为术语的词）
        self.stopwords = self._load_stopwords()
    
    def _load_stopwords(self) -> Set[str]:
        """加载停用词列表"""
        # 基础停用词
        stopwords = {
            '的', '了', '在', '是', '我', '有', '和', '就', '不', '人',
            '都', '一', '一个', '上', '也', '很', '到', '说', '要', '去',
            '你', '会', '着', '没有', '看', '好', '自己', '这', '那', '些',
            '个', '为', '与', '或', '及', '之', '因为', '所以', '但是', '如果',
            '可以', '已经', '还', '从', '对', '把', '被', '让', '给', '用'
        }
        
        # 可以从文件加载更多停用词
        stopwords_file = Path(__file__).parent.parent / 'workflow' / 'stopwords.txt'
        if stopwords_file.exists():
            with open(stopwords_file, 'r', encoding='utf-8') as f:
                for line in f:
                    word = line.strip()
                    if word and not word.startswith('#'):
                        stopwords.add(word)
        
        return stopwords
    
    def load_source_texts(self) -> bool:
        """加载源文本"""
        try:
            with open(self.input_csv, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                
                if 'string_id' not in reader.fieldnames or 'source_zh' not in reader.fieldnames:
                    print("❌ 错误：CSV 文件必须包含 string_id 和 source_zh 列")
                    return False
                
                for row in reader:
                    if row.get('source_zh'):
                        self.source_texts.append({
                            'string_id': row['string_id'],
                            'text': row['source_zh']
                        })
            
            print(f"✅ 加载了 {len(self.source_texts)} 条源文本")
            return True
            
        except FileNotFoundError:
            print(f"❌ 错误：找不到输入文件：{self.input_csv}")
            return False
        except Exception as e:
            print(f"❌ 错误：读取文件时出错：{str(e)}")
            return False
    
    def load_glossary(self) -> None:
        """加载现有术语表"""
        if not self.glossary_path or not self.glossary_path.exists():
            print("ℹ️  未找到现有术语表，将提取所有候选术语")
            return
        
        try:
            with open(self.glossary_path, 'r', encoding='utf-8') as f:
                glossary = yaml.safe_load(f)
                terms = glossary.get('terms', {})
                self.glossary_terms = set(terms.keys())
            
            print(f"✅ 加载了 {len(self.glossary_terms)} 个已知术语")
            
        except Exception as e:
            print(f"⚠️  警告：加载术语表时出错：{str(e)}")
    
    def extract_candidates(self, min_freq: int = 2, min_len: int = 2, max_len: int = 8) -> List[Dict]:
        """提取术语候选"""
        print("\n🔍 开始提取术语...")
        
        # 遍历所有源文本
        for item in self.source_texts:
            string_id = item['string_id']
            text = item['text']
            
            # 移除 token（⟦PH_X⟧ 等）
            text_clean = re.sub(r'⟦[^⟧]+⟧', '', text)
            
            # 使用 jieba 分词
            words = jieba.cut(text_clean)
            
            for word in words:
                # 过滤条件
                word = word.strip()
                if not word:
                    continue
                if word in self.stopwords:
                    continue
                if len(word) < min_len or len(word) > max_len:
                    continue
                # 排除纯数字和纯英文
                if re.match(r'^[0-9]+$', word) or re.match(r'^[a-zA-Z]+$', word):
                    continue
                # 排除单个标点符号
                if re.match(r'^[^\w]+$', word):
                    continue
                
                # 统计
                self.term_frequencies[word] += 1
                self.term_positions[word].append(string_id)
        
        # 生成候选列表
        candidates = []
        for term, freq in self.term_frequencies.most_common():
            if freq < min_freq:
                break
            
            # 跳过已在术语表中的词
            if term in self.glossary_terms:
                continue
            
            candidates.append({
                'term': term,
                'frequency': freq,
                'string_ids': list(set(self.term_positions[term])),  # 去重
                'suggested_translation': '',  # 可以接入翻译 API
                'category': '待分类',
                'note': ''
            })
        
        print(f"✅ 提取了 {len(candidates)} 个术语候选（去除已知术语后）")
        print(f"   总词汇数：{len(self.term_frequencies)}")
        print(f"   高频词汇（≥{min_freq}次）：{sum(1 for f in self.term_frequencies.values() if f >= min_freq)}")
        
        return candidates
    
    def save_candidates(self, candidates: List[Dict], output_path: str) -> bool:
        """保存候选列表到 YAML"""
        try:
            output = {
                'version': '1.0',
                'generated_at': datetime.now().isoformat(),
                'statistics': {
                    'total_strings': len(self.source_texts),
                    'unique_terms': len(candidates),
                    'total_occurrences': sum(c['frequency'] for c in candidates)
                },
                'candidates': candidates,
                'extraction_rules': {
                    'min_frequency': 2,
                    'min_length': 2,
                    'max_length': 8,
                    'segmentation': 'jieba'
                }
            }
            
            with open(output_path, 'w', encoding='utf-8') as f:
                yaml.dump(output, f, allow_unicode=True, sort_keys=False, indent=2)
            
            print(f"✅ 候选列表已保存到：{output_path}")
            return True
            
        except Exception as e:
            print(f"❌ 错误：保存文件时出错：{str(e)}")
            return False
    
    def print_summary(self, candidates: List[Dict], top_n: int = 10) -> None:
        """打印提取摘要"""
        print(f"\n📊 术语提取摘要：")
        print(f"   共处理：{len(self.source_texts)} 条文本")
        print(f"   提取候选：{len(candidates)} 个术语")
        print(f"   已知术语：{len(self.glossary_terms)} 个（已过滤）")
        print()
        
        if candidates:
            print(f"   高频术语 TOP {min(top_n, len(candidates))}：")
            for i, cand in enumerate(candidates[:top_n], 1):
                print(f"      {i}. {cand['term']} (出现 {cand['frequency']} 次)")
    
    def run(self, output_path: str, min_freq: int = 2) -> bool:
        """执行术语提取"""
        print("🚀 开始术语提取流程...")
        print()
        
        # 加载源文本
        if not self.load_source_texts():
            return False
        
        # 加载现有术语表
        self.load_glossary()
        
        # 提取候选
        candidates = self.extract_candidates(min_freq=min_freq)
        
        # 保存结果
        if not self.save_candidates(candidates, output_path):
            return False
        
        # 打印摘要
        self.print_summary(candidates)
        
        print()
        print("✅ 术语提取完成！")
        return True


def main():
    """主入口"""
    if len(sys.argv) < 3:
        print("Usage: python extract_terms.py <input_csv> <output_candidates_yaml> [glossary_yaml] [min_freq]")
        print()
        print("参数说明：")
        print("  input_csv              输入的 CSV 文件（必需包含 string_id 和 source_zh 列）")
        print("  output_candidates_yaml 输出的术语候选 YAML 文件")
        print("  glossary_yaml          现有术语表 YAML 文件（可选）")
        print("  min_freq               最小词频（默认 2）")
        print()
        print("示例：")
        print("  python extract_terms.py data/input.csv data/term_candidates.yaml")
        print("  python extract_terms.py data/input.csv data/term_candidates.yaml data/glossary.yaml 3")
        sys.exit(1)
    
    input_csv = sys.argv[1]
    output_yaml = sys.argv[2]
    glossary_yaml = sys.argv[3] if len(sys.argv) > 3 else None
    min_freq = int(sys.argv[4]) if len(sys.argv) > 4 else 2
    
    extractor = TermExtractor(input_csv, glossary_yaml)
    success = extractor.run(output_yaml, min_freq=min_freq)
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
