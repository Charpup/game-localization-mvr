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
import io
import json
import math
import re
import sys
from pathlib import Path
from typing import Any, Dict, List
from datetime import datetime
from collections import Counter

UI_ART_POLICY_TABLE = {
    "badge_micro_1c": {"hard_floor": 4, "review_floor": 6, "issue_type": "compact_mapping_missing"},
    "badge_micro_2c": {"hard_floor": 6, "review_floor": 8, "issue_type": "compact_mapping_missing"},
    "label_generic_short": {"hard_floor": 8, "review_floor": 10, "review_ratio": 2.5, "issue_type": "length_overflow"},
    "title_name_short": {"hard_floor": 10, "review_floor": 12, "review_ratio": 2.5, "issue_type": "length_overflow"},
    "promo_short": {"hard_floor": 10, "review_floor": 12, "review_ratio": 2.6, "issue_type": "length_overflow"},
    "item_skill_name": {"hard_floor": 10, "hard_ratio": 2.6, "review_floor": 12, "review_ratio": 3.0, "issue_type": "length_overflow"},
    "slogan_long": {"hard_floor": 10, "hard_ratio": 2.6, "review_floor": 12, "review_ratio": 3.2, "issue_type": "headline_budget_overflow"},
    "other_review": {"hard_floor": 10, "review_floor": 14, "review_ratio": 2.6, "issue_type": "length_overflow"},
}

PROMO_BANNED_EXPANSIONS = ("превью", "выбор", "ниндзя")
WORD_RE = re.compile(r"[A-Za-zА-Яа-яЁё0-9]+", re.UNICODE)


def _parse_int(value: Any, default: int = 0) -> int:
    try:
        return int(float(value))
    except Exception:
        return default


def _count_visual_lines(text: str) -> int:
    if not text:
        return 1
    return max(1, len(re.split(r"(?:\\n|\n)", text)))


def _build_ui_art_length_policy(row: Dict[str, Any]) -> Dict[str, Any]:
    category = str(row.get("ui_art_category") or "other_review").strip() or "other_review"
    spec = UI_ART_POLICY_TABLE.get(category, UI_ART_POLICY_TABLE["other_review"])
    source_len = _parse_int(row.get("source_len_clean") or 0)
    placeholder_budget = _parse_int(row.get("placeholder_budget") or 0)
    base_target = _parse_int(row.get("max_length_target") or row.get("max_len_target") or 0)
    base_review = _parse_int(row.get("max_len_review_limit") or 0)

    hard_ratio = spec.get("hard_ratio")
    hard_ratio_limit = math.floor(source_len * float(hard_ratio)) + placeholder_budget if hard_ratio else 0
    hard_limit = max(base_target, int(spec.get("hard_floor", 0)) + placeholder_budget, hard_ratio_limit)
    review_ratio = spec.get("review_ratio")
    review_ratio_limit = math.floor(source_len * float(review_ratio)) + placeholder_budget if review_ratio else 0
    review_limit = max(base_review, int(spec.get("review_floor", 0)) + placeholder_budget, review_ratio_limit)

    return {
        "category": category,
        "hard_limit": hard_limit,
        "review_limit": review_limit,
        "issue_type": str(spec.get("issue_type") or "length_overflow"),
        "source_lines": _count_visual_lines((row.get("source_zh") or row.get("tokenized_zh") or "")),
        "compact_rule": str(row.get("compact_rule") or ""),
        "compact_term": str(row.get("ui_art_compact_term") or "").strip(),
        "compact_mapping_status": str(row.get("compact_mapping_status") or ""),
        "strategy_hint": str(row.get("ui_art_strategy_hint") or "").strip(),
    }


def _contains_promo_expansion(text: str) -> bool:
    normalized = str(text or "").lower()
    return any(term in normalized for term in PROMO_BANNED_EXPANSIONS)


def _content_word_count(text: str) -> int:
    words = [token for token in WORD_RE.findall(text or "") if not token.isdigit()]
    return len(words)

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
                stream.reconfigure(encoding="utf-8", errors="replace")
                continue
            buffer = getattr(stream, "buffer", None)
            if buffer is not None:
                wrapped = io.TextIOWrapper(buffer, encoding="utf-8", errors="replace")
                setattr(sys, stream_name, wrapped)
        except Exception:
            continue

try:
    import yaml
except ImportError:
    print("[ERROR] PyYAML is required. Install with: pip install pyyaml")
    sys.exit(1)


class QAHardValidator:
    """硬性规则校验器 v2.0"""

    APPROVED_WARNING_TYPES = {
        'empty_source_translation_soft',
        'source_tag_unbalanced',
    }
    
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
        self.warnings: List[Dict] = []
        self.error_counts: Dict[str, int] = {
            'token_mismatch': 0,
            'tag_unbalanced': 0,
            'forbidden_hit': 0,
            'new_placeholder_found': 0,
            'empty_translation': 0
        }
        self.warning_counts: Dict[str, int] = {
            'source_tag_unbalanced': 0,
            'empty_source_translation': 0,
            'token_mismatch_soft': 0,
            'length_overflow': 0,
            'line_budget_overflow': 0,
            'headline_budget_overflow': 0,
            'promo_expansion_forbidden': 0,
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
            print(f"[OK] Loaded {len(self.placeholder_map)} placeholder mappings")
            return True
        except FileNotFoundError:
            print(f"[ERROR] Placeholder map not found: {self.placeholder_map_path}")
            return False
        except Exception as e:
            print(f"[ERROR] Error loading placeholder map: {str(e)}")
            return False
    
    def load_schema(self) -> bool:
        """加载 schema v2.0（支持 v1.0 fallback）"""
        try:
            with open(self.schema_yaml, 'r', encoding='utf-8') as f:
                schema = yaml.safe_load(f)
                if not isinstance(schema, dict):
                    print(f"[ERROR] Invalid schema format, expected mapping in {self.schema_yaml}")
                    return False

                schema_version = schema.get('version', 1)
                
                # 尝试 v2.0 格式
                patterns = schema.get('patterns', None)
                if patterns is None:
                    # Fallback 到 v1.0 格式
                    patterns = schema.get('placeholder_patterns', [])
                    if not patterns:
                        print("[WARN] schema missing both 'patterns' and 'placeholder_patterns', skipping placeholder checks.")
                        return True
                    print("[WARN] Using schema v1.0 format (placeholder_patterns)")
                else:
                    print("[OK] Using schema v2.0 format (patterns)")
                
                # 编译所有模式用于新占位符检测
                for pattern_def in patterns:
                    try:
                        regex = pattern_def.get('regex') or pattern_def.get('pattern')
                        if regex:
                            self.compiled_patterns.append(re.compile(regex))
                    except re.error as e:
                        print(f"[WARN] Invalid regex in pattern '{pattern_def.get('name')}': {e}")
                
                # 加载 paired_tags（v2.0 新特性）
                self.paired_tags = schema.get('paired_tags', [])
                
                print(f"[OK] Loaded schema with {len(self.compiled_patterns)} patterns")
                if self.paired_tags:
                    print(f"[OK] Loaded {len(self.paired_tags)} paired tag rules")
                
                return True
                
        except FileNotFoundError:
            print(f"[ERROR] Schema not found: {self.schema_yaml}")
            return False
        except Exception as e:
            print(f"[ERROR] Error loading schema: {str(e)}")
            return False
    
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
                            print(f"[WARN] Invalid forbidden pattern '{line}': {e}")
            
            print(f"[OK] Loaded {len(self.compiled_forbidden)} forbidden patterns")
            return True
        except FileNotFoundError:
            print("[WARN] Forbidden patterns file not found")
            return True
        except Exception as e:
            print(f"[WARN] Error loading forbidden patterns: {str(e)}")
            return True
    
    def extract_tokens(self, text: str) -> List[str]:
        """提取文本中的所有 token，保留重复出现次数"""
        if not text:
            return []
        return self.token_pattern.findall(text)

    def _token_matches_pattern(self, tag_text: str, pattern: str) -> bool:
        """判断标签是否匹配配置模式；为 <c / </c 做边界保护避免与 <color 误判。"""
        if not tag_text or not pattern:
            return False
        text = tag_text.lower()
        p = pattern.lower()

        if p == "<c":
            return bool(re.match(r"^<\s*c(?=[\s>])", text))
        if p == "</c":
            return bool(re.match(r"^</\s*c(?=[\s>])", text))
        return text.startswith(p)

    def _source_has_unbalanced_tags(self, source_text: str) -> bool:
        if not source_text:
            return False
        tags = re.findall(r"</?\w+(?:\s*=?\s*[^>]*)?>", source_text)
        if not tags:
            return False
        opens = 0
        closes = 0
        self_closing = {"br", "img", "hr", "meta", "input", "base", "link"}
        for tag in tags:
            if tag.endswith("/>"):
                continue
            if tag.startswith("</"):
                closes += 1
                continue
            m = re.match(r"<\s*(\w+)", tag)
            if m and m.group(1).lower() in self_closing:
                continue
            opens += 1
        return opens != closes

    def _normalize_paired_tags(self) -> List[Dict[str, Any]]:
        """按 family 归并 paired_tags，避免 <color 与 <c 重复统计。"""
        if not self.paired_tags:
            return []

        merged: Dict[str, Dict[str, Any]] = {}
        for pair_config in self.paired_tags:
            open_pattern = (pair_config.get("open") or "").strip()
            close_pattern = (pair_config.get("close") or "").strip()
            if not open_pattern or not close_pattern:
                continue

            if open_pattern.lower() in ("<color", "<c"):
                family = "color"
                open_patterns = ["<color", "<c"]
                close_patterns = ["</color", "</c"]
                description = "Unity 颜色标签"
            elif open_pattern.lower() in ("<size",):
                family = "size"
                open_patterns = [open_pattern]
                close_patterns = [close_pattern]
                description = pair_config.get("description", "Unity 大小标签")
            elif open_pattern.lower() in ("<b",):
                family = "bold"
                open_patterns = [open_pattern]
                close_patterns = [close_pattern]
                description = pair_config.get("description", "粗体标签")
            elif open_pattern.lower() in ("<i",):
                family = "italic"
                open_patterns = [open_pattern]
                close_patterns = [close_pattern]
                description = pair_config.get("description", "斜体标签")
            else:
                family = f"custom:{open_pattern}"
                open_patterns = [open_pattern]
                close_patterns = [close_pattern]
                description = pair_config.get("description", f"paired tag {open_pattern}")

            rule = merged.get(family, {
                "family": family,
                "open_patterns": [],
                "close_patterns": [],
                "description": description,
                "open_sample": open_patterns[0],
                "close_sample": close_patterns[0],
            })
            for pattern in open_patterns:
                if pattern not in rule["open_patterns"]:
                    rule["open_patterns"].append(pattern)
            for pattern in close_patterns:
                if pattern not in rule["close_patterns"]:
                    rule["close_patterns"].append(pattern)
            merged[family] = rule

        return list(merged.values())
    
    def check_token_mismatch(self, string_id: str, source_text: str,
                            target_text: str, row_num: int) -> None:
        """检查 token 是否匹配"""
        source_tokens = Counter(self.extract_tokens(source_text))
        target_tokens = Counter(self.extract_tokens(target_text))
        
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
            # 若仅出现单 token 的重复且源中已存在该 token，视为软告警，避免模型重述时误判阻断
            token = next(iter(extra), None)
            if len(extra) == 1 and token in source_tokens and sum(extra.values()) == 1:
                self.warnings.append({
                    'row': row_num,
                    'string_id': string_id,
                    'type': 'token_mismatch_soft',
                    'detail': f"extra ⟦{token}⟧ in target_text",
                    'source': source_text,
                    'target': target_text
                })
                self.warning_counts['token_mismatch_soft'] += 1
            else:
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
    
    def check_tag_balance(self, string_id: str, target_text: str, source_text: str,
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

        # 源文本标签本身不平衡则降级为非阻断告警：由 source schema 预检查负责
        if self._source_has_unbalanced_tags(source_text):
            self.warnings.append({
                'row': row_num,
                'string_id': string_id,
                'type': 'source_tag_unbalanced',
                'detail': 'source text has unbalanced raw tags, skip strict target tag validation',
                'source': source_text,
                'target': target_text
            })
            self.warning_counts['source_tag_unbalanced'] += 1
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
        paired_rules = self._normalize_paired_tags()
        if not paired_rules:
            self._check_tag_count(string_id, target_text, tag_tokens, row_num)
            return

        open_counts: Dict[str, int] = Counter()
        close_counts: Dict[str, int] = Counter()

        for tag_token in tag_tokens:
            original = self.placeholder_map.get(tag_token, '')
            if not original:
                continue

            original_l = original.lower()
            if original_l.startswith('</'):
                for rule in paired_rules:
                    for pattern in rule.get("close_patterns", []):
                        if self._token_matches_pattern(original_l, pattern):
                            close_counts[rule["family"]] += 1
                            break
                    else:
                        continue
                    break
            else:
                for rule in paired_rules:
                    for pattern in rule.get("open_patterns", []):
                        if self._token_matches_pattern(original_l, pattern):
                            open_counts[rule["family"]] += 1
                            break
                    else:
                        continue
                    break

        for rule in paired_rules:
            family = rule["family"]
            open_count = open_counts.get(family, 0)
            close_count = close_counts.get(family, 0)
            if open_count != close_count:
                self.errors.append({
                    'row': row_num,
                    'string_id': string_id,
                    'type': 'tag_unbalanced',
                    'detail': f"unbalanced {rule['description']}: {open_count} opening, {close_count} closing",
                    'target': target_text,
                    'open_pattern': rule["open_sample"],
                    'close_pattern': rule["close_sample"]
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
                              source_text: str, row_num: int) -> None:
        """
        检查是否出现了未经冻结的新占位符
        
        v2.0 改进：动态从 schema 加载检测模式
        """
        if not target_text:
            return
        
        for token_name in self.extract_tokens(target_text):
            if token_name in self.placeholder_map:
                continue
            self.errors.append({
                'row': row_num,
                'string_id': string_id,
                'type': 'new_placeholder_found',
                'detail': f"found unknown token placeholder: ⟦{token_name}⟧",
                'target': target_text,
                'pattern': 'token_format'
            })
            self.error_counts['new_placeholder_found'] += 1

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

                        # 目标文本里原样出现于源文本，说明不是新占位符
                        if source_text and match in source_text:
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
                    print(f"[ERROR] Missing required fields. Need: {required_fields}")
                    return False
                
                # 检查是否有翻译列
                target_field = None
                for possible_field in [
                    'target_text',
                    'translated_text',
                    'target_en',
                    'target_ru',
                    'target_zh',
                    'tokenized_target'
                ]:
                    if possible_field in reader.fieldnames:
                        target_field = possible_field
                        break
                
                if not target_field:
                    print("[ERROR] No target translation field found")
                    print(f"   Available fields: {reader.fieldnames}")
                    return False
                
                print(f"[OK] Using '{target_field}' as target translation field")
                print()
                
                # 逐行验证
                for idx, row in enumerate(reader, start=2):
                    self.total_rows += 1
                    
                    string_id = row.get('string_id', '')
                    source_text = row.get('tokenized_zh') or row.get('source_zh') or ''
                    source_zh = row.get('source_zh', '')
                    source_for_warning = source_zh if source_zh.strip() else source_text
                    target_text = row.get(target_field, '')
                    
                    # 空翻译且源文本也为空：记录软告警，继续后续流程（保留可复核痕迹）
                    if (not source_for_warning or not source_for_warning.strip()) and (not target_text or not target_text.strip()):
                        self.warnings.append({
                            'row': idx,
                            'string_id': string_id,
                            'type': 'empty_source_translation_soft',
                            'detail': 'empty source_zh; keep as non-blocking warning',
                            'source': source_text,
                            'target': target_text
                        })
                        self.warning_counts['empty_source_translation'] += 1
                        continue

                    # 空翻译视为硬错误
                    if not target_text or not target_text.strip():
                        self.errors.append({
                            'row': idx,
                            'string_id': string_id,
                            'type': 'empty_translation',
                            'detail': f"empty translation field: {target_field}",
                            'source': source_text,
                            'target': target_text
                        })
                        self.error_counts['empty_translation'] += 1
                        continue
                    
                    # 运行所有检查
                    self.check_token_mismatch(string_id, source_text, target_text, idx)
                    self.check_tag_balance(string_id, target_text, source_for_warning, idx)
                    self.check_forbidden_patterns(string_id, target_text, idx)
                    self.check_new_placeholders(string_id, target_text, source_text, idx)
                    self.check_length_overflow(string_id, target_text, row, idx)
                
                return True

                
        except FileNotFoundError:
            print(f"[ERROR] Translated CSV not found: {self.translated_csv}")
            return False
        except Exception as e:
            print(f"[ERROR] Error validating CSV: {str(e)}")
            import traceback
            traceback.print_exc()
            return False
    
    def check_length_overflow(self, string_id: str, target_text: str, row: Dict, row_num: int):
        """检查长度溢出"""
        policy = _build_ui_art_length_policy(row)
        limit = int(policy.get("hard_limit") or 0)
        review_limit = int(policy.get("review_limit") or 0)
        if limit <= 0:
            return

        actual_len = len(target_text)
        target_lines = _count_visual_lines(target_text)
        strategy_hint = str(policy.get("strategy_hint") or "")
        if (
            policy["category"] == "slogan_long"
            and strategy_hint in {"", "headline_multiline"}
            and target_lines > int(policy["source_lines"] or 1)
        ):
            self.errors.append({
                "row": row_num,
                "string_id": string_id,
                "type": "line_budget_overflow",
                "severity": "critical",
                "detail": f"line count {target_lines} > source line budget {policy['source_lines']}",
                "source": (row.get('source_zh') or row.get('tokenized_zh') or '')[:50],
                "target": target_text[:50]
            })
            self.error_counts['line_budget_overflow'] = self.error_counts.get('line_budget_overflow', 0) + 1
            return

        compact_rule = str(policy.get("compact_rule") or "")
        compact_term = str(policy.get("compact_term") or "")
        compact_mapping_status = str(policy.get("compact_mapping_status") or "")
        compact_violation = ""
        normalized_target = target_text.strip()
        if compact_rule == "dictionary_only":
            if compact_mapping_status == "manual_review_required" and actual_len > 0:
                compact_violation = "compact_mapping_missing"
            elif compact_term and normalized_target != compact_term:
                compact_violation = "compact_term_miss"
        elif strategy_hint == "promo_exact_head" and compact_term and normalized_target != compact_term:
            compact_violation = "compact_term_miss"

        if compact_term and normalized_target == compact_term and (
            compact_rule == "dictionary_only" or strategy_hint in {"promo_exact_head", "headline_nameplate"}
        ):
            return

        content_violation = ""
        if not compact_violation and strategy_hint == "promo_compound_pack" and _contains_promo_expansion(normalized_target):
            content_violation = "promo_expansion_forbidden"
        elif (
            not compact_violation
            and policy["category"] == "item_skill_name"
            and compact_term
            and normalized_target != compact_term
            and _content_word_count(normalized_target) > 2
        ):
            content_violation = "length_overflow"

        if actual_len <= limit and not compact_violation and not content_violation:
            return

        issue_type = compact_violation or content_violation or str(policy["issue_type"] or "length_overflow")
        source_preview = (row.get('source_zh') or row.get('tokenized_zh') or '')[:50]
        severity = "critical" if ((review_limit and actual_len > review_limit) or issue_type == "line_budget_overflow") else "major"
        if issue_type == "compact_mapping_missing":
            detail = "No approved compact mapping for compact-only badge category"
        elif issue_type == "compact_term_miss":
            detail = f"Expected approved compact term '{compact_term}' for compact-constrained category"
        elif issue_type == "promo_expansion_forbidden":
            detail = "Promo compact title contains banned expansion tail (Превью / Выбор / Ниндзя)"
        elif issue_type == "headline_budget_overflow":
            detail = (
                f"Headline length {actual_len} > target {limit}"
                if severity == "major"
                else f"Headline length {actual_len} > review limit {review_limit}"
            )
        elif issue_type == "length_overflow" and policy["category"] == "item_skill_name" and _content_word_count(normalized_target) > 2:
            detail = f"Item/skill name uses {_content_word_count(normalized_target)} content words; compact noun rule allows at most 2"
        else:
            detail = (
                f"Length {actual_len} > target {limit}"
                if severity == "major"
                else f"Length {actual_len} > review limit {review_limit}"
            )

        self.errors.append({
            "row": row_num,
            "string_id": string_id,
            "type": issue_type,
            "severity": severity,
            "detail": detail,
            "source": source_preview,
            "target": target_text[:50],
            "ui_art_category": policy["category"],
            "max_len_target": limit,
            "max_len_review_limit": review_limit,
        })
        self.error_counts[issue_type] = self.error_counts.get(issue_type, 0) + 1

    def generate_report(self) -> None:
        """生成 JSON 报告（限制错误数量）"""
        approved_warnings = [w for w in self.warnings if w.get('type') in self.APPROVED_WARNING_TYPES]
        actionable_warnings = [w for w in self.warnings if w.get('type') not in self.APPROVED_WARNING_TYPES]
        approved_warning_counts = dict(Counter(w.get('type', 'unknown') for w in approved_warnings))
        actionable_warning_counts = dict(Counter(w.get('type', 'unknown') for w in actionable_warnings))
        report = {
            'has_errors': len(self.errors) > 0,
            'total_rows': self.total_rows,
            'warning_counts': self.warning_counts,
            'warning_policy': {
                'approved_non_blocking_types': sorted(self.APPROVED_WARNING_TYPES),
                'approved_warning_total': len(approved_warnings),
                'approved_warning_counts': approved_warning_counts,
                'actionable_warning_total': len(actionable_warnings),
                'actionable_warning_counts': actionable_warning_counts,
            },
            'error_counts': self.error_counts,
            'errors': self.errors[:2000],  # 限制到 2000 条
            'warnings': self.warnings[:2000],
            'metadata': {
                'version': '2.0',
                'generated_at': datetime.now().isoformat(),
                'input_file': str(self.translated_csv),
                'total_errors': len(self.errors),
                'total_warnings': len(self.warnings),
                'errors_truncated': len(self.errors) > 2000
            }
        }
        
        # 创建输出目录
        self.report_json.parent.mkdir(parents=True, exist_ok=True)
        
        with open(self.report_json, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
    
    def print_summary(self) -> None:
        """打印验证总结"""
        print("\n[INFO] QA Validation Summary:")
        print(f"   Total rows checked: {self.total_rows}")
        print(f"   Total errors: {len(self.errors)}")
        print()
        
        if self.error_counts['token_mismatch'] > 0:
            print(f"   [ERROR] Token mismatch: {self.error_counts['token_mismatch']}")
        
        if self.error_counts['tag_unbalanced'] > 0:
            print(f"   [ERROR] Tag unbalanced: {self.error_counts['tag_unbalanced']}")
        
        if self.error_counts['forbidden_hit'] > 0:
            print(f"   [ERROR] Forbidden patterns: {self.error_counts['forbidden_hit']}")
        
        if self.error_counts['new_placeholder_found'] > 0:
            print(f"   [ERROR] New placeholders found: {self.error_counts['new_placeholder_found']}")

        if self.error_counts['empty_translation'] > 0:
            print(f"   [ERROR] Empty translations: {self.error_counts['empty_translation']}")
        if self.warning_counts['empty_source_translation'] > 0:
            print(f"   [WARN] Empty source rows (non-blocking): {self.warning_counts['empty_source_translation']}")
        if self.warning_counts['source_tag_unbalanced'] > 0:
            print(f"   [WARN] Source tag imbalance (non-blocking): {self.warning_counts['source_tag_unbalanced']}")
        if self.warning_counts['token_mismatch_soft'] > 0:
            print(f"   [WARN] Soft token mismatch: {self.warning_counts['token_mismatch_soft']}")
        if self.warnings:
            approved_total = sum(1 for w in self.warnings if w.get('type') in self.APPROVED_WARNING_TYPES)
            actionable_total = len(self.warnings) - approved_total
            print(f"   [INFO] Approved non-blocking warnings: {approved_total}")
            print(f"   [WARN] Actionable warnings: {actionable_total}")
        
        print()
        
        if len(self.errors) > 0:
            print(f"[ERROR] Validation FAILED with {len(self.errors)} errors")
            if len(self.errors) > 2000:
                print(f"   [WARN] Report truncated to 2000 errors (total: {len(self.errors)})")
            print(f"   See detailed report: {self.report_json}")
            print()
            print("   Sample errors:")
            for error in self.errors[:5]:
                print(f"   - [{error['type']}] {error['string_id']}: {error['detail']}")
        else:
            print("[OK] All checks passed!")
            print(f"   Report saved to: {self.report_json}")
    
    def run(self) -> bool:
        """运行 QA 验证"""
        print("[INFO] Starting QA Hard validation v2.0...")
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
    configure_standard_streams()
    
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

