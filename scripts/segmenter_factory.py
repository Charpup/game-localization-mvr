#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
segmenter_factory.py

Provides a pluggable Chinese word segmentation backend with ordered fallback.

Planned backends:
  1. pkuseg (when installed)
  2. thulac (when installed)
  3. lac (when installed)
  4. jieba (when installed)
  5. heuristic regex fallback

The public API is intentionally tiny so extract_terms.py can stay thin.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence


class Segmenter:
    """抽象分词器。"""

    def __init__(self, name: str):
        self.name = name

    def segment(self, text: str, domain_hint: Optional[str] = None) -> List[str]:
        """返回分词结果。"""
        raise NotImplementedError

    def is_available(self) -> bool:
        return True


class HeuristicSegmenter(Segmenter):
    """Fallback regex 分词：保留中文连续片段 + 英文字母连续片段。"""

    _re = re.compile(r"[\u4e00-\u9fff]{2,}|[A-Za-z0-9._\-+%]+")

    def __init__(self):
        super().__init__("heuristic")

    def segment(self, text: str, domain_hint: Optional[str] = None) -> List[str]:
        return [m.group(0).strip() for m in self._re.finditer(text or "") if m.group(0).strip()]


class JiebaSegmenter(Segmenter):
    def __init__(self):
        super().__init__("jieba")
        try:
            import jieba  # type: ignore

            self._jieba = jieba
        except Exception:
            self._jieba = None

    def is_available(self) -> bool:
        return self._jieba is not None

    def segment(self, text: str, domain_hint: Optional[str] = None) -> List[str]:
        if not self._jieba:
            return []
        return [w.strip() for w in self._jieba.cut(text or "") if w and w.strip()]


class PkusegSegmenter(Segmenter):
    def __init__(self):
        super().__init__("pkuseg")
        try:
            import pkuseg  # type: ignore

            self._engine = pkuseg.pkuseg()
        except Exception:
            self._engine = None

    def is_available(self) -> bool:
        return self._engine is not None

    def segment(self, text: str, domain_hint: Optional[str] = None) -> List[str]:
        if not self._engine:
            return []
        return [w.strip() for w in self._engine.cut(text or "") if w and w.strip()]


class ThulacSegmenter(Segmenter):
    def __init__(self):
        super().__init__("thulac")
        try:
            import thulac  # type: ignore

            self._engine = thulac.thulac(seg_only=True)
        except Exception:
            self._engine = None

    def is_available(self) -> bool:
        return self._engine is not None

    def segment(self, text: str, domain_hint: Optional[str] = None) -> List[str]:
        if not self._engine:
            return []
        # thulac 返回 [(word, tag), ...] 或 "word1 word2 ..."
        segments = self._engine.cut(text or "")
        out = []
        if isinstance(segments, str):
            segments = segments.strip().split()
        for item in segments:
            if isinstance(item, (list, tuple)) and len(item) >= 1:
                out.append(str(item[0]).strip())
            else:
                out.append(str(item).strip())
        return [w for w in out if w]


class LacSegmenter(Segmenter):
    def __init__(self):
        super().__init__("lac")
        try:
            from LAC import LAC  # type: ignore

            self._engine = LAC(mode="lac")
        except Exception:
            self._engine = None

    def is_available(self) -> bool:
        return self._engine is not None

    def segment(self, text: str, domain_hint: Optional[str] = None) -> List[str]:
        if not self._engine:
            return []
        # LAC 的 run 返回 [["word","tag"], ...] 风格多变，这里兼容多种返回
        segments = self._engine.run(text or "")
        if not segments:
            return []
        if isinstance(segments, tuple):
            segments = list(segments)
        # 常见返回形态：[words, tags]
        if isinstance(segments, list) and len(segments) == 2 and all(isinstance(x, (list, tuple)) for x in segments):
            candidate = segments[0]
            return [str(x).strip() for x in candidate if str(x).strip()]
        out = []
        if isinstance(segments[0], (list, tuple)):
            for item in segments:
                if isinstance(item, (list, tuple)) and item:
                    out.append(str(item[0]).strip())
                else:
                    out.append(str(item).strip())
        else:
            out = [str(x).strip() for x in segments]
        return [w for w in out if w]


def _normalize_request(request: str) -> List[str]:
    if not request:
        return []
    out = []
    for part in request.split(","):
        p = part.strip().lower()
        if p:
            out.append(p)
    return out


def _backend_factory(name: str) -> Segmenter:
    if name in ("pkuseg",):
        return PkusegSegmenter()
    if name in ("thulac", "thu"):
        return ThulacSegmenter()
    if name in ("lac",):
        return LacSegmenter()
    if name in ("jieba",):
        return JiebaSegmenter()
    return HeuristicSegmenter()


def _default_chain_for_domain(domain_hint: Optional[str] = None) -> List[str]:
    hint = (domain_hint or "").strip().lower()
    if hint in {"dialogue", "story", "narrative", "narration", "dialog"}:
        return ["pkuseg", "lac", "thulac", "jieba", "heuristic"]
    return ["pkuseg", "thulac", "lac", "jieba", "heuristic"]


def build_segmenter_chain(
    backend_request: Optional[str] = None,
    fallback: bool = True,
    domain_hint: Optional[str] = None,
) -> List[Segmenter]:
    """
    Build a segmentation fallback chain.

    backend_request 可写 "pkuseg", "thulac,lac,jieba" 等逗号序列。
    如果 fallback=True，会自动补齐标准后端并兜底 heuristic。
    """
    requested = _normalize_request(backend_request or "")
    chain_names = requested if requested else []
    if not chain_names:
        chain_names = _default_chain_for_domain(domain_hint)
    else:
        # 兼容用户只写单个引擎的场景；按默认语义补齐常见模型链路
        if fallback:
            for fallback_backend in _default_chain_for_domain(domain_hint):
                if fallback_backend not in chain_names:
                    chain_names.append(fallback_backend)
        if fallback and "heuristic" not in chain_names:
            chain_names.append("heuristic")

    out: List[Segmenter] = []
    seen = set()
    for n in chain_names:
        if n in seen:
            continue
        seen.add(n)
        seg = _backend_factory(n)
        out.append(seg)
    return out


def segment_text(text: str, backend_request: Optional[str] = None, domain_hint: Optional[str] = None) -> List[str]:
    """
    根据回退链返回第一套成功分词结果（非空数组）。
    """
    for seg in build_segmenter_chain(backend_request, domain_hint=domain_hint):
        if not seg.is_available():
            continue
        result = seg.segment(text, domain_hint=domain_hint)
        if result:
            return result
    # 全部失败时返回启发式拆解（至少保证不崩）
    return HeuristicSegmenter().segment(text)


def describe_chain() -> Dict[str, List[str]]:
    """辅助输出：当前可用引擎。"""
    backends = [PkusegSegmenter(), ThulacSegmenter(), LacSegmenter(), JiebaSegmenter(), HeuristicSegmenter()]
    return {
        "available": [b.name for b in backends if b.is_available()],
        "all": [b.name for b in backends]
    }
