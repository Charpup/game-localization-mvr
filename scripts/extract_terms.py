#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Extract Terms Script v2.0
从源文本中提取专业术语候选

多模式支持：
  - jieba: 使用 jieba 中文分词（默认）
  - heuristic: 启发式正则提取（无依赖）
  - llm: LLM API 提取（显式调用）

Usage:
    python extract_terms.py <input_csv> <output_yaml> [options]
    
Options:
    --mode MODE       提取模式: jieba/heuristic/llm (默认: jieba)
    --glossary FILE   现有术语表文件
    --min-freq N      最小词频 (默认: 2)
    --model MODEL     LLM 模型 (仅 llm 模式)
    --provider PROV   LLM 提供商 (仅 llm 模式)
"""

import csv
import re
import os
import sys
import json
import argparse
from pathlib import Path
from typing import Dict, List, Set
from datetime import datetime
from collections import Counter, defaultdict
from abc import ABC, abstractmethod

try:
    import yaml
except ImportError:
    print("❌ Error: PyYAML is required. Install with: pip install pyyaml")
    sys.exit(1)

# 检查 jieba 是否可用
try:
    import jieba
    JIEBA_AVAILABLE = True
except ImportError:
    JIEBA_AVAILABLE = False


# ============================================================================
# 基类
# ============================================================================

class BaseExtractor(ABC):
    """术语提取器基类"""
    
    def __init__(self, glossary_terms: Set[str] = None):
        self.glossary_terms = glossary_terms or set()
        self.stopwords = self._load_stopwords()
    
    def _load_stopwords(self) -> Set[str]:
        """加载停用词"""
        stopwords = {
            '的', '了', '在', '是', '我', '有', '和', '就', '不', '人',
            '都', '一', '一个', '上', '也', '很', '到', '说', '要', '去',
            '你', '会', '着', '没有', '看', '好', '自己', '这', '那', '些',
            '个', '为', '与', '或', '及', '之', '因为', '所以', '但是', '如果',
            '可以', '已经', '还', '从', '对', '把', '被', '让', '给', '用'
        }
        
        stopwords_file = Path(__file__).parent.parent / 'workflow' / 'stopwords.txt'
        if stopwords_file.exists():
            with open(stopwords_file, 'r', encoding='utf-8') as f:
                for line in f:
                    word = line.strip()
                    if word and not word.startswith('#'):
                        stopwords.add(word)
        
        return stopwords
    
    @abstractmethod
    def extract(self, texts: List[Dict]) -> List[Dict]:
        """提取术语候选"""
        pass
    
    @property
    @abstractmethod
    def mode_name(self) -> str:
        """模式名称"""
        pass


# ============================================================================
# Jieba 模式
# ============================================================================

class JiebaExtractor(BaseExtractor):
    """使用 jieba 中文分词的术语提取器"""
    
    @property
    def mode_name(self) -> str:
        return "jieba"
    
    def extract(self, texts: List[Dict], min_freq: int = 2, 
                min_len: int = 2, max_len: int = 8) -> List[Dict]:
        """使用 jieba 分词提取术语"""
        if not JIEBA_AVAILABLE:
            raise RuntimeError("jieba 未安装，请运行: pip install jieba")
        
        freq = Counter()
        positions = defaultdict(list)
        
        for item in texts:
            string_id = item['string_id']
            text = item['text']
            
            # 移除 token
            text_clean = re.sub(r'⟦[^⟧]+⟧', '', text)
            
            # jieba 分词
            words = jieba.cut(text_clean)
            
            for word in words:
                word = word.strip()
                if not word:
                    continue
                if word in self.stopwords:
                    continue
                if len(word) < min_len or len(word) > max_len:
                    continue
                if re.match(r'^[0-9]+$', word) or re.match(r'^[a-zA-Z]+$', word):
                    continue
                if re.match(r'^[^\w]+$', word):
                    continue
                
                freq[word] += 1
                if len(positions[word]) < 5:
                    positions[word].append({'string_id': string_id, 'source_zh': text})
        
        # 生成候选列表
        candidates = []
        for term, count in freq.most_common():
            if count < min_freq:
                break
            if term in self.glossary_terms:
                continue
            
            candidates.append({
                'term_zh': term,
                'score': count,
                'status': 'proposed',
                'examples': positions[term]
            })
        
        return candidates


# ============================================================================
# Heuristic 模式
# ============================================================================

class HeuristicExtractor(BaseExtractor):
    """启发式术语提取器（无依赖）"""
    
    # CJK 连续字符 (2-8字)
    RE_CJK = re.compile(r"[\u4e00-\u9fff]{2,8}")
    # 括号内词
    RE_BRACKETED = re.compile(r"[《【「『](.+?)[》】」』]")
    
    # 额外停用词（常见但非术语的词）
    EXTRA_STOP = {
        "系统", "提示", "点击", "确定", "取消", "开始", "结束", "今日", "明日",
        "获得", "使用", "进行", "完成", "任务", "活动", "奖励", "道具", "角色",
    }
    
    @property
    def mode_name(self) -> str:
        return "heuristic"
    
    def extract(self, texts: List[Dict], max_terms: int = 300) -> List[Dict]:
        """使用启发式规则提取术语"""
        freq = Counter()
        examples = defaultdict(list)
        
        all_stop = self.stopwords | self.EXTRA_STOP
        
        for item in texts:
            string_id = item['string_id']
            text = item['text']
            
            # 移除 token
            text_clean = re.sub(r'⟦[^⟧]+⟧', '', text)
            
            # 括号内词（权重 +2）
            for m in self.RE_BRACKETED.finditer(text_clean):
                term = m.group(1).strip()
                if 2 <= len(term) <= 12 and term not in all_stop:
                    freq[term] += 2
                    if len(examples[term]) < 5:
                        examples[term].append({'string_id': string_id, 'source_zh': text})
            
            # CJK 连续串（权重 +1）
            for m in self.RE_CJK.finditer(text_clean):
                term = m.group(0)
                if term not in all_stop:
                    freq[term] += 1
                    if len(examples[term]) < 3:
                        examples[term].append({'string_id': string_id, 'source_zh': text})
        
        # 生成候选列表
        candidates = []
        for term, count in freq.most_common(max_terms):
            if term in self.glossary_terms:
                continue
            
            candidates.append({
                'term_zh': term,
                'score': count,
                'status': 'proposed',
                'examples': examples[term]
            })
        
        return candidates


# ============================================================================
# LLM 模式
# ============================================================================

class LLMExtractor(BaseExtractor):
    """使用 LLM API 的术语提取器"""
    
    def __init__(self, glossary_terms: Set[str] = None, 
                 provider: str = None, model: str = None):
        super().__init__(glossary_terms)
        self.provider = provider
        self.model = model
        self.config = self._load_config()
    
    def _load_config(self) -> Dict:
        """加载 LLM 配置"""
        config_path = Path(__file__).parent.parent / 'workflow' / 'llm_config.yaml'
        
        if not config_path.exists():
            print(f"⚠️  警告：未找到 LLM 配置文件：{config_path}")
            return {}
        
        with open(config_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    
    def _get_api_key(self) -> str:
        """获取 API 密钥"""
        llm_config = self.config.get('llm', {})
        
        # 优先使用配置文件中的密钥
        if llm_config.get('api_key'):
            return llm_config['api_key']
        
        # 根据提供商从环境变量获取
        provider = self.provider or llm_config.get('provider', 'openai')
        env_vars = {
            'openai': 'OPENAI_API_KEY',
            'anthropic': 'ANTHROPIC_API_KEY',
            'gemini': 'GOOGLE_API_KEY',
        }
        
        env_var = env_vars.get(provider, 'OPENAI_API_KEY')
        api_key = os.environ.get(env_var)
        
        if not api_key:
            raise RuntimeError(
                f"❌ 未找到 API 密钥\n"
                f"   请设置环境变量 {env_var} 或在 workflow/llm_config.yaml 中配置 api_key"
            )
        
        return api_key
    
    @property
    def mode_name(self) -> str:
        return "llm"
    
    def extract(self, texts: List[Dict]) -> List[Dict]:
        """使用 LLM 提取术语"""
        llm_config = self.config.get('llm', {})
        
        # 获取配置
        provider = self.provider or llm_config.get('provider', 'openai')
        model = self.model or llm_config.get('model', 'gpt-4o-mini')
        
        # 验证 API 密钥
        try:
            api_key = self._get_api_key()
        except RuntimeError as e:
            print(str(e))
            print("\n💡 提示：LLM 模式需要配置 API 密钥")
            print("   1. 设置环境变量：export OPENAI_API_KEY='your-key'")
            print("   2. 或编辑配置文件：workflow/llm_config.yaml")
            sys.exit(1)
        
        print(f"✅ 使用 LLM 模式: {provider}/{model}")
        print(f"   API 密钥: {api_key[:8]}...")
        
        # TODO: 实现 LLM API 调用
        print("\n⚠️  LLM 提取功能尚未完全实现")
        print("   当前仅验证 API 配置是否正确")
        print("   实际 API 调用将在后续版本实现")
        
        # 返回空列表（占位）
        return []


# ============================================================================
# 主逻辑
# ============================================================================

def load_glossary(glossary_path: str) -> Set[str]:
    """加载术语表"""
    if not glossary_path or not Path(glossary_path).exists():
        return set()
    
    with open(glossary_path, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f)
        terms = data.get('terms', {})
        return set(terms.keys())


def load_source_texts(input_csv: str) -> List[Dict]:
    """加载源文本"""
    texts = []
    with open(input_csv, 'r', encoding='utf-8-sig', newline='') as f:
        reader = csv.DictReader(f)
        
        if 'string_id' not in reader.fieldnames or 'source_zh' not in reader.fieldnames:
            raise ValueError("CSV 必须包含 string_id 和 source_zh 列")
        
        for row in reader:
            if row.get('source_zh'):
                texts.append({
                    'string_id': row['string_id'],
                    'text': row['source_zh']
                })
    
    return texts


def save_candidates(candidates: List[Dict], output_path: str, 
                   mode: str, texts_count: int, config: Dict = None) -> None:
    """保存候选列表"""
    language_pair = {'source': 'zh-CN', 'target': 'ru-RU'}
    if config:
        language_pair = config.get('language_pair', language_pair)
    
    output = {
        'version': '2.0',
        'extraction_mode': mode,
        'generated_at': datetime.now().isoformat(),
        'language_pair': language_pair,
        'statistics': {
            'total_strings': texts_count,
            'unique_terms': len(candidates),
            'total_occurrences': sum(c['score'] for c in candidates) if candidates else 0
        },
        'candidates': candidates
    }
    
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        yaml.safe_dump(output, f, allow_unicode=True, sort_keys=False)


def main():
    parser = argparse.ArgumentParser(
        description='Extract Terms v2.0 - 多模式术语提取',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
模式说明:
  jieba      使用 jieba 中文分词（默认，需安装 jieba）
  heuristic  启发式正则提取（无依赖，快速）
  llm        使用 LLM API 提取（需配置 API 密钥）

示例:
  python extract_terms.py data/input.csv data/terms.yaml
  python extract_terms.py data/input.csv data/terms.yaml --mode heuristic
  python extract_terms.py data/input.csv data/terms.yaml --mode llm --model gpt-4o
        """
    )
    
    parser.add_argument('input_csv', help='输入 CSV 文件')
    parser.add_argument('output_yaml', help='输出术语候选 YAML')
    parser.add_argument('--mode', choices=['jieba', 'heuristic', 'llm'], 
                       default='jieba', help='提取模式 (默认: jieba)')
    parser.add_argument('--glossary', help='现有术语表文件')
    parser.add_argument('--min-freq', type=int, default=2, help='最小词频 (默认: 2)')
    parser.add_argument('--model', help='LLM 模型 (仅 llm 模式)')
    parser.add_argument('--provider', help='LLM 提供商 (仅 llm 模式)')
    
    args = parser.parse_args()
    
    print("🚀 Extract Terms v2.0")
    print(f"   输入: {args.input_csv}")
    print(f"   输出: {args.output_yaml}")
    print(f"   模式: {args.mode}")
    print()
    
    # 加载术语表
    glossary_terms = load_glossary(args.glossary)
    if glossary_terms:
        print(f"✅ 加载了 {len(glossary_terms)} 个已知术语")
    
    # 加载源文本
    texts = load_source_texts(args.input_csv)
    print(f"✅ 加载了 {len(texts)} 条源文本")
    
    # 选择提取器
    mode = args.mode
    
    # jieba 模式自动 fallback
    if mode == 'jieba' and not JIEBA_AVAILABLE:
        print("⚠️  jieba 未安装，自动切换到 heuristic 模式")
        mode = 'heuristic'
    
    # 创建提取器
    if mode == 'jieba':
        extractor = JiebaExtractor(glossary_terms)
        candidates = extractor.extract(texts, min_freq=args.min_freq)
    elif mode == 'heuristic':
        extractor = HeuristicExtractor(glossary_terms)
        candidates = extractor.extract(texts)
    elif mode == 'llm':
        extractor = LLMExtractor(glossary_terms, args.provider, args.model)
        candidates = extractor.extract(texts)
    
    print(f"\n✅ 提取了 {len(candidates)} 个术语候选")
    
    # 加载 LLM 配置（用于语言对）
    config = {}
    config_path = Path(__file__).parent.parent / 'workflow' / 'llm_config.yaml'
    if config_path.exists():
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
    
    # 保存结果
    save_candidates(candidates, args.output_yaml, extractor.mode_name, len(texts), config)
    print(f"✅ 结果已保存到: {args.output_yaml}")
    
    # 打印 Top 10
    if candidates:
        print(f"\n📊 高频术语 TOP 10:")
        for i, c in enumerate(candidates[:10], 1):
            print(f"   {i}. {c['term_zh']} (score: {c['score']})")
    
    print("\n✅ 术语提取完成!")


if __name__ == "__main__":
    main()
