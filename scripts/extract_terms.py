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

# Unified batch infrastructure
try:
    from runtime_adapter import batch_llm_call, log_llm_progress, BatchConfig
except ImportError:
    batch_llm_call = None

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

# Module weights for weighted extraction
MODULE_WEIGHTS = {
    "ui_button": 2.0,
    "ui_label": 1.8,
    "system_notice": 1.5,
    "skill_desc": 2.2,
    "item_desc": 1.8,
    "dialogue": 0.3,
    "misc": 1.0
}

# IP/world term bonus patterns
IP_TERM_PATTERNS = ['之', '村', '影', '遁', '术', '式', '印', '丸', '忍', '眼', '道', '族', '国', '隐']

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
# Weighted 模式 (uses normalized.csv with module_tag)
# ============================================================================

class WeightedExtractor(BaseExtractor):
    """使用 normalized.csv 的加权术语提取器"""
    
    def __init__(self, glossary_terms: Set[str] = None, blacklist_path: str = None):
        super().__init__(glossary_terms)
        self.blacklist = self._load_blacklist(blacklist_path)
    
    def _load_blacklist(self, path: str = None) -> Set[str]:
        """Load generic terms blacklist."""
        blacklist = set()
        
        # Default path
        if not path:
            path = Path(__file__).parent.parent / 'glossary' / 'generic_terms_zh.txt'
        
        if Path(path).exists():
            with open(path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        blacklist.add(line)
        
        return blacklist
    
    @property
    def mode_name(self) -> str:
        return "weighted"
    
    def _compute_termness(self, term: str, module_mix: Dict[str, float]) -> float:
        """Compute term-ness score (0.0-1.0)."""
        score = 0.5  # Base score
        
        # Length bonus
        if len(term) >= 3:
            score += 0.1
        if len(term) >= 4:
            score += 0.1
        
        # IP/world term pattern bonus
        for pattern in IP_TERM_PATTERNS:
            if pattern in term:
                score += 0.15
                break
        
        # Skill-heavy terms get bonus
        if module_mix.get('skill_desc', 0) > 0.3:
            score += 0.1
        if module_mix.get('item_desc', 0) > 0.3:
            score += 0.05
        
        # Dialogue-heavy terms get penalty
        if module_mix.get('dialogue', 0) > 0.5:
            score -= 0.2
        
        return max(0.0, min(1.0, score))
    
    def extract(self, texts: List[Dict], min_freq: int = 2, 
                min_len: int = 2, max_len: int = 8,
                min_termness: float = 0.3) -> List[Dict]:
        """Weighted extraction from normalized texts with module_tag."""
        if not JIEBA_AVAILABLE:
            raise RuntimeError("jieba 未安装，请运行: pip install jieba")
        
        # Per-term stats
        freq = Counter()
        weighted_freq = Counter()
        module_counts = defaultdict(lambda: Counter())
        positions = defaultdict(list)
        
        for item in texts:
            string_id = item['string_id']
            text = item['text']
            module_tag = item.get('module_tag', 'misc')
            weight = MODULE_WEIGHTS.get(module_tag, 1.0)
            
            # Clean text
            text_clean = re.sub(r'⟦[^⟧]+⟧', '', text)
            text_clean = re.sub(r'\{[\d\w]+\}', '', text_clean)
            text_clean = re.sub(r'<[^>]+>', '', text_clean)
            
            # Jieba segment
            words = jieba.cut(text_clean)
            
            for word in words:
                word = word.strip()
                if not word:
                    continue
                if word in self.stopwords:
                    continue
                if word in self.blacklist:
                    continue
                if len(word) < min_len or len(word) > max_len:
                    continue
                if re.match(r'^[0-9]+$', word) or re.match(r'^[a-zA-Z]+$', word):
                    continue
                if re.match(r'^[^\w]+$', word):
                    continue
                
                freq[word] += 1
                weighted_freq[word] += weight
                module_counts[word][module_tag] += 1
                if len(positions[word]) < 3:
                    positions[word].append({'string_id': string_id, 'source_zh': text[:100]})
        
        # Generate candidates
        candidates = []
        filtered_counts = {'generic_blacklist': 0, 'low_freq': 0, 'in_glossary': 0, 'low_termness': 0}
        
        for term, wfreq in weighted_freq.most_common():
            raw_freq = freq[term]
            
            if raw_freq < min_freq:
                filtered_counts['low_freq'] += 1
                continue
            if term in self.glossary_terms:
                filtered_counts['in_glossary'] += 1
                continue
            
            # Compute module mix
            total_module = sum(module_counts[term].values())
            module_mix = {k: v/total_module for k, v in module_counts[term].items()}
            
            # Compute termness
            termness = self._compute_termness(term, module_mix)
            if termness < min_termness:
                filtered_counts['low_termness'] += 1
                continue
            
            candidates.append({
                'term_zh': term,
                'score': round(wfreq, 2),
                'raw_freq': raw_freq,
                'weighted_freq': round(wfreq, 2),
                'module_mix': {k: round(v, 2) for k, v in module_mix.items()},
                'termness_score': round(termness, 2),
                'status': 'proposed',
                'examples': positions[term]
            })
        
        print(f"  Filtered: {filtered_counts}")
        return candidates


# ============================================================================
# LLM 模式
# ============================================================================

def build_system_prompt_extract() -> str:
    """Build system prompt for term extraction."""
    return (
        "你是手游本地化术语提取专家。\n\n"
        "任务：从提供的文本中提取候选术语（zh-CN）。\n"
        "目标：识别具有专业性、代表性或翻译难度的词汇，包括：\n"
        "- 游戏机制/数值名称\n"
        "- 专属名词（人名、地名、组织、技能名、道具名）\n"
        "- UI 界面固定用语\n\n"
        "输出格式（硬性 JSON）：\n"
        "{\n"
        '  "items": [\n'
        "    {\n"
        '      "id": "<string_id>",\n'
        '      "terms": ["术语1", "术语2", ...]\n'
        "    }\n"
        "  ]\n"
        "}\n"
        "规则：\n"
        "- 如果行内没有术语，不要出现在 items 中。\n"
        "- 术语应为 2-8 字，避免提取长难句。\n"
        "- 排除通用代词和极简常用词。\n"
    )

def build_user_prompt_extract(items: List[Dict]) -> str:
    """Build user prompt for extraction."""
    # items from batch_llm_call: list of {'id', 'source_text'}
    clean_items = []
    for it in items:
        clean_items.append({
            "string_id": it["id"],
            "text": it["source_text"]
        })
    return json.dumps(clean_items, ensure_ascii=False, indent=2)

class LLMExtractor(BaseExtractor):
    """使用 LLM API 的术语提取器"""
    
    def __init__(self, glossary_terms: Set[str] = None, 
                 provider: str = None, model: str = None):
        super().__init__(glossary_terms)
        self.provider = provider
        self.model = model or "claude-haiku-4-5-20251001"
    
    @property
    def mode_name(self) -> str:
        return "llm"
    
    def extract(self, texts: List[Dict]) -> List[Dict]:
        """使用 LLM 提取术语"""
        if not batch_llm_call:
            raise RuntimeError("batch_llm_call is not available")
        
        print(f"✅ 使用 LLM 模式: {self.model}")
        
        # 准备 batch_rows
        batch_rows = []
        id_to_original_text = {}
        for item in texts:
            sid = str(item['string_id'])
            text = item['text']
            batch_rows.append({
                "id": sid,
                "source_text": text
            })
            id_to_original_text[sid] = text

        # 执行批次调用
        try:
            batch_results = batch_llm_call(
                step="glossary_extract",
                rows=batch_rows,
                model=self.model,
                system_prompt=build_system_prompt_extract(),
                user_prompt_template=build_user_prompt_extract,
                content_type="normal",
                retry=1,
                allow_fallback=True,
                partial_match=True
            )
        except Exception as e:
            print(f"❌ LLM 提取失败: {e}")
            return []

        # 聚合结果
        term_freq = Counter()
        term_examples = defaultdict(list)
        
        for item in batch_results:
            sid = str(item.get("id", ""))
            terms = item.get("terms", [])
            if not isinstance(terms, list):
                continue
                
            orig_text = id_to_original_text.get(sid, "")
            
            for term in terms:
                term = term.strip()
                if not term or term in self.glossary_terms:
                    continue
                if term in self.stopwords:
                    continue
                
                term_freq[term] += 1
                if len(term_examples[term]) < 5:
                    term_examples[term].append({
                        "string_id": sid,
                        "source_zh": orig_text
                    })

        # 构建最终候选列表
        candidates = []
        for term, count in term_freq.most_common():
            candidates.append({
                'term_zh': term,
                'score': count,
                'status': 'proposed',
                'examples': term_examples[term]
            })
            
        return candidates


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
    """加载源文本 - 支持多种列名格式，支持 normalized.csv"""
    texts = []
    with open(input_csv, 'r', encoding='utf-8-sig', newline='') as f:
        reader = csv.DictReader(f)
        fields = reader.fieldnames or []
        
        # Flexible column name mapping
        id_col = None
        zh_col = None
        tag_col = None  # For weighted mode
        
        for name in ['string_id', 'id', 'ID', 'StringId']:
            if name in fields:
                id_col = name
                break
        
        for name in ['source_zh', 'zh', 'ZH', 'text', 'Text', 'text_zh', 'SourceText']:
            if name in fields:
                zh_col = name
                break
        
        # Optional: module_tag for weighted mode
        if 'module_tag' in fields:
            tag_col = 'module_tag'
        
        if not id_col or not zh_col:
            raise ValueError(f"CSV 必须包含 ID 列 (string_id/id) 和源文本列 (source_zh/zh/text). Found: {fields}")
        
        for row in reader:
            if row.get(zh_col):
                item = {
                    'string_id': row[id_col],
                    'text': row[zh_col]
                }
                if tag_col:
                    item['module_tag'] = row.get(tag_col, 'misc')
                texts.append(item)
    
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
    
    parser.add_argument('input_csv', help='输入 CSV 文件 (或 normalized.csv)')
    parser.add_argument('output_yaml', help='输出术语候选 YAML')
    parser.add_argument('--mode', choices=['jieba', 'heuristic', 'llm', 'weighted'], 
                       default='jieba', help='提取模式 (默认: jieba, weighted需要normalized.csv)')
    parser.add_argument('--glossary', help='现有术语表文件')
    parser.add_argument('--blacklist', help='通用词黑名单 (weighted模式)')
    parser.add_argument('--min-freq', type=int, default=2, help='最小词频 (默认: 2)')
    parser.add_argument('--min-termness', type=float, default=0.3, help='最小术语度 (weighted模式, 默认: 0.3)')
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
    elif mode == 'weighted':
        extractor = WeightedExtractor(glossary_terms, args.blacklist)
        candidates = extractor.extract(texts, min_freq=args.min_freq, min_termness=args.min_termness)
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
