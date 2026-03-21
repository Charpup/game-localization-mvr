#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Extract Terms Script v2.1

中文术语候选提取，支持可插拔分词后端链路
(pkuseg -> thulac/lac -> jieba -> heuristic)，并输出分层候选。
"""

import argparse
import csv
import hashlib
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple, Any

from segmenter_factory import segment_text, build_segmenter_chain

try:
    import yaml
except ImportError:
    print("❌ Error: PyYAML is required. Install with: pip install pyyaml")
    sys.exit(1)

try:
    from runtime_adapter import batch_llm_call
except ImportError:
    batch_llm_call = None

DEFAULT_SEG_BACKEND = "pkuseg,thulac,lac,jieba,heuristic"
MODULE_WEIGHTS = {
    "ui_button": 2.0,
    "ui_label": 1.8,
    "ui_tab": 1.6,
    "system_notice": 1.5,
    "skill_desc": 2.2,
    "item_desc": 1.8,
    "item_name": 1.9,
    "dialogue": 0.3,
    "story": 0.4,
    "narrative": 0.4,
    "misc": 1.0,
}
IP_TERM_HINTS = ["之", "村", "影", "遁", "术", "式", "印", "丸", "忍", "眼", "道", "族", "国", "隐"]


def _sha1(s: str) -> str:
    return hashlib.md5(s.encode("utf-8")).hexdigest()[:10]


class BaseExtractor:
    def __init__(
        self,
        glossary_terms: Optional[Set[str]] = None,
        stopwords: Optional[Set[str]] = None,
        named_entities: Optional[Set[str]] = None,
        style_profile: Optional[Dict[str, Any]] = None,
        seg_backend: str = DEFAULT_SEG_BACKEND,
        domain_hint: str = "",
    ):
        self.glossary_terms = glossary_terms or set()
        self.stopwords = set(stopwords or set())
        self.named_entities = set(named_entities or set())
        self.seg_backend = seg_backend
        self.domain_hint = domain_hint
        self.style_profile = style_profile or {}

        profile_terms = self.style_profile.get("terminology", {}) or {}
        forbidden = profile_terms.get("forbidden_terms", [])
        banned = profile_terms.get("banned_terms", [])
        self.forbidden_terms = {str(x).strip() for x in forbidden if str(x).strip()}
        self.banned_terms = {str(x).strip() for x in banned if str(x).strip()}

        self.stopwords |= self._load_stopwords()

    def _is_forbidden_term(self, term: str) -> bool:
        return term in self.forbidden_terms or term in self.banned_terms

    @property
    def mode_name(self) -> str:
        raise NotImplementedError

    def _load_stopwords(self) -> Set[str]:
        base = {
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
                    text = line.strip()
                    if text and not text.startswith('#'):
                        base.add(text)
        return base

    def _segment(self, text: str, domain_hint: Optional[str] = None) -> List[str]:
        return segment_text(text, self.seg_backend, domain_hint or self.domain_hint)

    def _classify(self, stability: float, boundary: float, context: float) -> str:
        if stability >= 0.72 and boundary >= 0.7 and context >= 0.65:
            return "critical"
        if stability >= 0.40 and boundary >= 0.35 and context >= 0.30:
            return "proposed"
        return "low_confidence"

    def _is_ner(self, term: str) -> bool:
        if term in self.named_entities:
            return True
        if '·' in term or '-' in term:
            return True
        if len(term) >= 2 and any(ch.isupper() for ch in term):
            return True
        return False

    @staticmethod
    def _length_penalty(term: str) -> float:
        ln = len(term)
        if ln <= 2:
            return 0.0
        if ln <= 5:
            return 0.05
        if ln <= 7:
            return 0.15
        if ln <= 10:
            return 0.30
        return 0.5

    @staticmethod
    def _module_mix(counts: Counter) -> Dict[str, float]:
        total = sum(counts.values()) or 1
        return {k: round(v / total, 3) for k, v in counts.items()}

    @staticmethod
    def _normalize_module(tag: str) -> str:
        return (tag or '').strip().lower()


class SegmentedExtractor(BaseExtractor):
    """分词提取（默认）"""

    @property
    def mode_name(self) -> str:
        return "segmented"

    def extract(self, texts: List[Dict], min_freq: int = 2, min_len: int = 2, max_len: int = 12) -> List[Dict]:
        freq = Counter()
        term_modules = defaultdict(Counter)
        evidence = defaultdict(list)

        for row in texts:
            sid = str(row.get('string_id', ''))
            raw = str(row.get('text', '') or '')
            module = self._normalize_module(row.get('module_tag', 'misc'))
            line_no = row.get('source_line_no')
            source = row.get('text', '')
            cleaned = re.sub(r'⟦[^⟧]+⟧', '', raw)
            terms = self._segment(cleaned, self.domain_hint)

            if not terms:
                terms = re.findall(r"[\u4e00-\u9fff]{2,}|[A-Za-z0-9._\-+%]+", cleaned)

            for t in terms:
                t = t.strip()
                if not t:
                    continue
                if t in self.stopwords:
                    continue
                if len(t) < min_len or len(t) > max_len:
                    continue
                if t in self.glossary_terms:
                    continue
                if re.fullmatch(r'^[a-zA-Z]+$', t):
                    continue
                if re.fullmatch(r'^\d+$', t):
                    continue
                if re.fullmatch(r'^[^\w]+$', t):
                    continue
                if not any('\u4e00' <= ch <= '\u9fff' for ch in t):
                    continue

                freq[t] += 1
                term_modules[t][module] += 1
                if len(evidence[t]) < 4:
                    evidence[t].append({
                        'string_id': sid,
                        'line': line_no,
                        'module_tag': module,
                        'context': source[:100],
                    })

        max_freq = max(freq.values()) if freq else 1
        out = []
        for term, cnt in freq.most_common():
            if cnt < min_freq:
                continue

            stability = min(1.0, cnt / max_freq)
            module_mix = self._module_mix(term_modules[term])
            ui_score = module_mix.get('ui_button', 0) + module_mix.get('ui_label', 0) + module_mix.get('ui_tab', 0)
            if ui_score >= 0.5:
                context_score = 0.8
            elif module_mix.get('dialogue', 0) >= 0.5 or module_mix.get('story', 0) >= 0.5:
                context_score = 0.35
            elif module_mix.get('narrative', 0) >= 0.5:
                context_score = 0.45
            else:
                context_score = 0.6

            boundary = 0.4
            if self._is_ner(term):
                boundary = 0.9
            elif any(p in term for p in IP_TERM_HINTS):
                boundary = min(1.0, boundary + 0.2)

            penalty = self._length_penalty(term)
            score = round(cnt * (1.0 - penalty), 3)
            tier = self._classify(stability, boundary, context_score)
            status = {'critical': 'approved', 'proposed': 'proposed', 'low_confidence': 'banned'}[tier]
            if self._is_forbidden_term(term):
                tier = 'low_confidence'
                status = 'banned'

            out.append({
                'term_zh': term,
                'score': score,
                'frequency': cnt,
                'status': status,
                'tier': tier,
                'approval_hint': tier if tier != 'low_confidence' else 'banned',
                'term_fingerprint': _sha1(term),
                'metrics': {
                    'stability_score': round(stability, 3),
                    'context_score': round(context_score, 3),
                    'boundary_score': round(boundary, 3),
                    'length_penalty': round(penalty, 3),
                    'module_mix': module_mix,
                },
                'evidence': {
                    'sources': evidence[term],
                    'domain_hint': self.domain_hint,
                    'backend_chain': [s.name for s in build_segmenter_chain(self.seg_backend)],
                },
                'policy': 'forbidden_term_review' if self._is_forbidden_term(term) else None,
            })
        return out


class HeuristicExtractor(BaseExtractor):
    @property
    def mode_name(self) -> str:
        return 'heuristic'

    RE_CJK = re.compile(r"[\u4e00-\u9fff]{2,8}")
    RE_BRACKET = re.compile(r"[《【「『](.+?)[》】」』]")
    EXTRA_STOP = {
        "系统", "提示", "点击", "确定", "取消", "开始", "结束",
        "获得", "使用", "进行", "完成", "任务", "活动", "奖励", "道具", "角色",
    }

    def extract(self, texts: List[Dict], max_terms: int = 500, min_len: int = 2, max_len: int = 12) -> List[Dict]:
        freq = Counter()
        term_modules = defaultdict(Counter)
        evidence = defaultdict(list)

        for row in texts:
            sid = str(row.get('string_id', ''))
            raw = str(row.get('text', '') or '')
            module = self._normalize_module(row.get('module_tag', 'misc'))
            line_no = row.get('source_line_no')
            source = row.get('text', '')
            text = re.sub(r'⟦[^⟧]+⟧', '', raw)

            for m in self.RE_BRACKET.finditer(text):
                term = m.group(1).strip()
                if min_len <= len(term) <= max_len and term not in self.stopwords:
                    freq[term] += 2
                    term_modules[term][module] += 1
                    if len(evidence[term]) < 4:
                        evidence[term].append({'string_id': sid, 'line': line_no, 'module_tag': module, 'context': source[:100]})

            for m in self.RE_CJK.finditer(text):
                term = m.group(0)
                if not (min_len <= len(term) <= max_len):
                    continue
                if term in self.EXTRA_STOP or term in self.stopwords:
                    continue
                freq[term] += 1
                term_modules[term][module] += 1
                if len(evidence[term]) < 3:
                    evidence[term].append({'string_id': sid, 'line': line_no, 'module_tag': module, 'context': source[:100]})

        max_freq = max(freq.values()) if freq else 1
        out = []
        for term, cnt in freq.most_common(max_terms):
            if term in self.glossary_terms:
                continue
            if not any('\u4e00' <= ch <= '\u9fff' for ch in term):
                continue
            stability = min(1.0, cnt / max_freq)
            boundary = 0.75 if self._is_ner(term) else 0.35
            context_score = 0.55
            mix = self._module_mix(term_modules[term])
            tier = self._classify(stability, boundary, context_score)
            status = {'critical': 'approved', 'proposed': 'proposed', 'low_confidence': 'banned'}[tier]
            if self._is_forbidden_term(term):
                tier = 'low_confidence'
                status = 'banned'
            score = round(cnt * (1.0 - self._length_penalty(term)), 3)

            out.append({
                'term_zh': term,
                'score': score,
                'frequency': cnt,
                'status': status,
                'tier': tier,
                'approval_hint': tier if tier != 'low_confidence' else 'banned',
                'term_fingerprint': _sha1(term),
                'metrics': {
                    'stability_score': round(stability, 3),
                    'context_score': round(context_score, 3),
                    'boundary_score': round(boundary, 3),
                    'length_penalty': round(self._length_penalty(term), 3),
                    'module_mix': mix,
                },
                'evidence': {
                    'sources': evidence[term],
                    'domain_hint': self.domain_hint,
                    'backend_chain': [s.name for s in build_segmenter_chain(self.seg_backend)],
                },
                'policy': 'forbidden_term_review' if self._is_forbidden_term(term) else None,
            })
        return out


class WeightedExtractor(BaseExtractor):
    def __init__(self, glossary_terms: Optional[Set[str]] = None, blacklist_path: Optional[str] = None, **kwargs):
        super().__init__(glossary_terms=glossary_terms, **kwargs)
        self.blacklist = self._load_blacklist(blacklist_path)

    @property
    def mode_name(self) -> str:
        return 'weighted'

    def _load_blacklist(self, path: Optional[str]) -> Set[str]:
        if not path:
            path = Path(__file__).parent.parent / 'glossary' / 'generic_terms_zh.txt'
        out = set()
        if Path(path).exists():
            with open(path, 'r', encoding='utf-8') as f:
                for line in f:
                    v = line.strip()
                    if v and not v.startswith('#'):
                        out.add(v)
        return out

    def _termness(self, term: str, module_mix: Dict[str, float]) -> float:
        score = 0.5
        if len(term) >= 3:
            score += 0.1
        if len(term) >= 4:
            score += 0.1
        if any(p in term for p in IP_TERM_HINTS):
            score += 0.15
        if module_mix.get('skill_desc', 0) > 0.3:
            score += 0.1
        if module_mix.get('item_name', 0) > 0.3:
            score += 0.05
        if module_mix.get('dialogue', 0) > 0.5:
            score -= 0.2
        return max(0.0, min(1.0, score))

    def extract(self, texts: List[Dict], min_freq: int = 2, min_len: int = 2, max_len: int = 12, min_termness: float = 0.3) -> List[Dict]:
        freq = Counter()
        weighted = Counter()
        term_modules = defaultdict(Counter)
        evidence = defaultdict(list)

        for row in texts:
            sid = str(row.get('string_id', ''))
            raw = str(row.get('text', '') or '')
            module = self._normalize_module(row.get('module_tag', 'misc'))
            line_no = row.get('source_line_no')
            source = row.get('text', '')
            text = re.sub(r'\{[^}]+\}', '', re.sub(r'<[^>]+>', '', re.sub(r'⟦[^⟧]+⟧', '', raw)))
            terms = self._segment(text, self.domain_hint)
            if not terms:
                terms = re.findall(r"[\u4e00-\u9fff]{2,}|[A-Za-z0-9._\-+%]+", text)

            weight = MODULE_WEIGHTS.get(module, 1.0)
            for t in terms:
                t = t.strip()
                if not t:
                    continue
                if t in self.stopwords or t in self.blacklist or t in self.glossary_terms:
                    continue
                if len(t) < min_len or len(t) > max_len:
                    continue
                if not any('\u4e00' <= ch <= '\u9fff' for ch in t):
                    continue
                if re.fullmatch(r'^[a-zA-Z]+$', t):
                    continue
                if re.fullmatch(r'^[^\w]+$', t):
                    continue

                freq[t] += 1
                weighted[t] += weight
                term_modules[t][module] += 1
                if len(evidence[t]) < 3:
                    evidence[t].append({'string_id': sid, 'line': line_no, 'module_tag': module, 'context': source[:100]})

        max_freq = max(freq.values()) if freq else 1
        out = []
        for term, wfreq in weighted.most_common():
            raw_freq = freq[term]
            if raw_freq < min_freq:
                continue
            mix = self._module_mix(term_modules[term])
            termness = self._termness(term, mix)
            if termness < min_termness:
                continue

            stability = min(1.0, raw_freq / max_freq)
            context = 0.35 if mix.get('dialogue', 0) >= 0.5 else 0.75 if (mix.get('ui_button', 0) + mix.get('ui_label', 0) >= 0.5) else 0.55
            boundary = 0.5
            if self._is_ner(term):
                boundary = 0.85
            elif any(p in term for p in IP_TERM_HINTS):
                boundary = min(1.0, boundary + 0.2)

            tier = self._classify(stability, boundary, context)
            status = {'critical': 'approved', 'proposed': 'proposed', 'low_confidence': 'banned'}[tier]
            if self._is_forbidden_term(term):
                tier = 'low_confidence'
                status = 'banned'
            score = round(wfreq * (1.0 - self._length_penalty(term)), 3)

            out.append({
                'term_zh': term,
                'score': score,
                'raw_freq': raw_freq,
                'weighted_freq': round(wfreq, 2),
                'module_mix': mix,
                'termness_score': round(termness, 3),
                'status': status,
                'tier': tier,
                'approval_hint': tier if tier != 'low_confidence' else 'banned',
                'stability_score': round(stability, 3),
                'boundary_score': round(boundary, 3),
                'context_score': round(context, 3),
                'term_fingerprint': _sha1(term),
                'evidence': {
                    'sources': evidence[term],
                    'domain_hint': self.domain_hint,
                    'backend_chain': [s.name for s in build_segmenter_chain(self.seg_backend)],
                },
                'policy': 'forbidden_term_review' if self._is_forbidden_term(term) else None,
            })
        return out


class LLMExtractor(BaseExtractor):
    def __init__(
        self,
        glossary_terms: Optional[Set[str]] = None,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        style_profile: Optional[Dict[str, Any]] = None,
        seg_backend: str = DEFAULT_SEG_BACKEND,
        domain_hint: str = "",
    ):
        super().__init__(
            glossary_terms=glossary_terms,
            style_profile=style_profile,
            seg_backend=seg_backend,
            domain_hint=domain_hint,
        )
        self.provider = provider
        self.model = model or 'claude-haiku-4-5-20251001'

    @property
    def mode_name(self) -> str:
        return 'llm'

    def extract(self, texts: List[Dict]) -> List[Dict]:
        if not batch_llm_call:
            raise RuntimeError('batch_llm_call unavailable')
        print(f"✅ 使用 LLM 模式: {self.model}")

        batch_rows = [{'id': str(r.get('string_id', '')), 'source_text': str(r.get('text', ''))} for r in texts]
        id2text = {str(r.get('string_id', '')): str(r.get('text', '')) for r in texts}
        results = batch_llm_call(
            step='glossary_extract',
            rows=batch_rows,
            model=self.model,
            system_prompt=build_system_prompt_extract(),
            user_prompt_template=build_user_prompt_extract,
            content_type='normal',
            retry=1,
            allow_fallback=True,
            partial_match=True,
        )

        freq = Counter()
        examples = defaultdict(list)
        for item in results:
            sid = str(item.get('id', ''))
            terms = item.get('terms', [])
            if not isinstance(terms, list):
                continue
            for term in terms:
                term = str(term).strip()
                if not term or term in self.stopwords or term in self.glossary_terms:
                    continue
                freq[term] += 1
                if len(examples[term]) < 5:
                    examples[term].append({'string_id': sid, 'context': id2text.get(sid, '')[:100]})

        out = []
        for term, cnt in freq.most_common():
            if self._is_forbidden_term(term):
                tier = 'low_confidence'
                status = 'banned'
            else:
                tier = 'proposed' if cnt >= 1 else 'low_confidence'
                status = {'critical': 'approved', 'proposed': 'proposed', 'low_confidence': 'banned'}[tier]
            out.append({
                'term_zh': term,
                'score': cnt,
                'status': status,
                'tier': tier,
                'approval_hint': tier,
                'term_fingerprint': _sha1(term),
                'metrics': {
                    'stability_score': 0.4,
                    'context_score': 0.5,
                    'boundary_score': 0.5,
                    'length_penalty': self._length_penalty(term),
                },
                'evidence': {
                    'sources': examples[term],
                    'domain_hint': self.domain_hint,
                    'backend_chain': [s.name for s in build_segmenter_chain(self.seg_backend)],
                },
                'policy': 'forbidden_term_review' if self._is_forbidden_term(term) else None,
            })
        return out


def build_system_prompt_extract() -> str:
    return (
        '你是手游本地化术语提取专家。\n\n'
        '任务：从提供的文本中提取候选术语（zh-CN）。\n'
        '目标：识别具有专业性、代表性或翻译难度的词汇，包括：\n'
        '- 游戏机制/数值名称\n'
        '- 专属名词（人名、地名、组织、技能名、道具名）\n'
        '- UI 界面固定用语\n\n'
        '输出格式（硬性 JSON）：\n'
        '{\n'
        '  "items": [\n'
        '    {\n'
        '      "id": "<string_id>",\n'
        '      "terms": ["术语1", "术语2", ...]\n'
        '    }\n'
        '  ]\n'
        '}\n'
        '规则：\n'
        '- 如果行内没有术语，不要出现在 items 中。\n'
        '- 术语应为 2-8 字，避免提取长难句。\n'
        '- 排除通用代词和极简常用词。'
    )


def build_user_prompt_extract(items: List[Dict]) -> str:
    payload = [{'string_id': it['id'], 'text': it['source_text']} for it in items]
    return json.dumps(payload, ensure_ascii=False, indent=2)


def load_glossary(path: str) -> Set[str]:
    if not path or not Path(path).exists():
        return set()
    with open(path, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f) or {}

    terms = set()
    if isinstance(data.get('terms'), dict):
        terms.update(str(k).strip() for k in data['terms'].keys() if str(k).strip())
    if isinstance(data.get('entries'), list):
        for it in data['entries']:
            if not isinstance(it, dict):
                continue
            term = str(it.get('term_zh') or '').strip()
            if term:
                terms.add(term)
    return terms


def load_stopword_config(path: Optional[str]) -> Tuple[Set[str], Set[str]]:
    if not path or not Path(path).exists():
        return set(), set()
    with open(path, 'r', encoding='utf-8') as f:
        raw = f.read()
    if path.lower().endswith('.json'):
        try:
            payload = json.loads(raw)
        except Exception:
            payload = {}
    else:
        try:
            payload = yaml.safe_load(raw) or {}
        except Exception:
            payload = {}
    if not isinstance(payload, dict):
        return set(), set()
    stopwords = {str(x).strip() for x in payload.get('stopwords', []) if str(x).strip()}
    named = {str(x).strip() for x in payload.get('named_entities', []) if str(x).strip()}
    return stopwords, named


def load_style_profile(path: Optional[str]) -> Dict[str, Any]:
    if not path or not Path(path).exists():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        raw = f.read()
    if path.lower().endswith(".json"):
        if not raw.strip():
            return {}
        try:
            return json.loads(raw)
        except Exception:
            return {}
    if yaml is None:
        return {}
    try:
        return yaml.safe_load(raw) or {}
    except Exception:
        return {}


def load_source_texts(input_csv: str) -> List[Dict]:
    with open(input_csv, 'r', encoding='utf-8-sig', newline='') as f:
        r = csv.DictReader(f)
        fields = r.fieldnames or []

        id_col = next((x for x in ['string_id', 'id', 'ID', 'StringId'] if x in fields), None)
        text_col = next((x for x in ['source_zh', 'zh', 'ZH', 'text', 'Text', 'text_zh', 'SourceText'] if x in fields), None)
        module_col = 'module_tag' if 'module_tag' in fields else None
        if not id_col or not text_col:
            raise ValueError(f'CSV 缺少 id 或 source 列。当前列名: {fields}')

        out = []
        for line_no, row in enumerate(r, start=2):
            if not row.get(text_col):
                continue
            out.append({
                'string_id': row[id_col],
                'text': row[text_col],
                'module_tag': row.get(module_col, 'misc') if module_col else 'misc',
                'source_line_no': line_no,
            })
        return out


def _bucket(candidates: List[Dict]) -> Dict[str, List[Dict]]:
    buckets = {'critical': [], 'proposed': [], 'low_confidence': []}
    for c in candidates:
        tier = c.get('tier', 'proposed')
        if tier not in buckets:
            tier = 'proposed'
        buckets[tier].append(c)
    return buckets


def save_candidates(candidates: List[Dict], output_path: str, mode: str, texts_count: int, config: Dict, output_evidence: Optional[str] = None) -> None:
    buckets = _bucket(candidates)
    ordered = buckets['critical'] + buckets['proposed'] + buckets['low_confidence']
    payload = {
        'version': '2.1',
        'extraction_mode': mode,
        'generated_at': datetime.now().isoformat(),
        'language_pair': config.get('language_pair', {'source': 'zh-CN', 'target': 'ru-RU'}),
        'seg_backend': config.get('seg_backend', DEFAULT_SEG_BACKEND),
        'domain_hint': config.get('domain_hint'),
        'style_profile': config.get('style_profile'),
        'statistics': {
            'total_strings': texts_count,
            'unique_terms': len(candidates),
            'total_occurrences': sum(c.get('score', 0) for c in candidates),
            'critical': len(buckets['critical']),
            'proposed': len(buckets['proposed']),
            'low_confidence': len(buckets['low_confidence']),
        },
        'candidates': ordered,
        'critical': buckets['critical'],
        'proposed': buckets['proposed'],
        'low_confidence': buckets['low_confidence'],
    }

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        yaml.safe_dump(payload, f, allow_unicode=True, sort_keys=False)

    if output_evidence:
        evidence = {'generated_at': payload['generated_at'], 'output': output_path,
                    'evidence': [{'term': c['term_zh'], 'tier': c.get('tier'), 'evidence': c.get('evidence', {})} for c in ordered[:500]]}
        Path(output_evidence).parent.mkdir(parents=True, exist_ok=True)
        with open(output_evidence, 'w', encoding='utf-8') as f:
            yaml.safe_dump(evidence, f, allow_unicode=True, sort_keys=False)


def main():
    p = argparse.ArgumentParser('extract_terms', description='Extract Terms Script')
    p.add_argument('input_csv')
    p.add_argument('output_yaml')
    p.add_argument('--mode', choices=['segmented', 'heuristic', 'weighted', 'llm'], default='segmented')
    p.add_argument('--seg-backend', default=DEFAULT_SEG_BACKEND, help='分词后端链路')
    p.add_argument('--domain-hint', default='', help='领域提示（ui/dialogue/system/game）')
    p.add_argument('--style-profile', default='data/style_profile.yaml', help='项目 style_profile 配置')
    p.add_argument('--stopwords-config', help='停用词/命名实体配置文件')
    p.add_argument('--glossary', help='现有 glossary 文件')
    p.add_argument('--blacklist', help='通用词黑名单（weighted）')
    p.add_argument('--min-freq', type=int, default=2)
    p.add_argument('--min-termness', type=float, default=0.3)
    p.add_argument('--model', help='llm 模型')
    p.add_argument('--provider', help='llm 提供商')
    p.add_argument('--output-evidence', help='单独输出 evidence 文件')
    args = p.parse_args()

    print('🚀 Extract Terms v2.1')
    print(f'   输入: {args.input_csv}')
    print(f'   输出: {args.output_yaml}')

    glossary = load_glossary(args.glossary)
    style_profile = load_style_profile(args.style_profile)
    stopwords_extra, named_entities = load_stopword_config(args.stopwords_config)

    profile_seg_backend = ""
    if isinstance(style_profile.get("segmentation"), dict):
        profile_seg_backend = str(style_profile["segmentation"].get("backend_chain", "") or "").strip()
    if args.seg_backend == DEFAULT_SEG_BACKEND and profile_seg_backend:
        args.seg_backend = profile_seg_backend
    if not args.domain_hint:
        args.domain_hint = str(style_profile.get("project", {}).get("domain_hint", "")).strip()

    profile_terms = style_profile.get("terminology", {}) if isinstance(style_profile.get("terminology"), dict) else {}
    profile_named = set()
    if isinstance(profile_terms, dict):
        profile_named = {str(x).strip() for x in profile_terms.get("protected_entities", []) if str(x).strip()}
    if profile_named:
        named_entities = named_entities | profile_named

    if glossary:
        print(f'✅ 加载了 {len(glossary)} 个已知术语')

    texts = load_source_texts(args.input_csv)
    print(f'✅ 加载了 {len(texts)} 条源文本')

    base = {
        'glossary_terms': glossary,
        'stopwords': stopwords_extra,
        'named_entities': named_entities,
        'style_profile': style_profile,
        'seg_backend': args.seg_backend,
        'domain_hint': args.domain_hint,
    }

    if args.mode == 'segmented':
        extractor = SegmentedExtractor(**base)
        candidates = extractor.extract(texts, min_freq=args.min_freq)
    elif args.mode == 'heuristic':
        extractor = HeuristicExtractor(**base)
        candidates = extractor.extract(texts)
    elif args.mode == 'weighted':
        extractor = WeightedExtractor(blacklist_path=args.blacklist, **base)
        candidates = extractor.extract(texts, min_freq=args.min_freq, min_termness=args.min_termness)
    else:
        extractor = LLMExtractor(**base, provider=args.provider, model=args.model)
        candidates = extractor.extract(texts)

    print(f'✅ 提取候选: {len(candidates)}')
    b = _bucket(candidates)
    print(f"   critical={len(b['critical'])}, proposed={len(b['proposed'])}, low_confidence={len(b['low_confidence'])}")

    config = {
        'language_pair': {'source': 'zh-CN', 'target': 'ru-RU'},
        'seg_backend': args.seg_backend,
        'domain_hint': args.domain_hint,
        'style_profile': args.style_profile,
    }
    config_file = Path(__file__).parent.parent / 'workflow' / 'llm_config.yaml'
    if config_file.exists():
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                config.update(yaml.safe_load(f) or {})
        except Exception:
            pass

    save_candidates(candidates, args.output_yaml, extractor.mode_name, len(texts), config, args.output_evidence)
    print(f'✅ 结果已保存到: {args.output_yaml}')
    if args.output_evidence:
        print(f'✅ evidence 已保存到: {args.output_evidence}')

    if candidates:
        print('📊 Top 10:')
        for i, c in enumerate(candidates[:10], 1):
            print(f"  {i}. {c['term_zh']} ({c['score']}, {c.get('tier')})")


if __name__ == '__main__':
    main()
