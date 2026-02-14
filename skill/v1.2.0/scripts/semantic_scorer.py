#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
semantic_scorer.py (v1.0)

翻译语义一致性评分

通过计算源文本与译文的向量余弦相似度，评估翻译的语义保真度。
可用于：
1. Soft QA 前置过滤 (优先检查低分翻译)
2. 全量翻译质量评估
3. Round2 Refresh 验证

Usage:
    from semantic_scorer import SemanticScorer
    
    scorer = SemanticScorer()
    pairs = [
        {"id": "1", "source_zh": "攻击力", "target_ru": "Атака"},
        {"id": "2", "source_zh": "防御力", "target_ru": "Защита"},
    ]
    results = scorer.score_batch(pairs)
    # [{"id": "1", "semantic_score": 0.85, "semantic_status": "ok"}, ...]
"""

import os
import sys
from typing import List, Dict

# Ensure scripts directory is in path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    import numpy as np
except ImportError:
    print("ERROR: numpy is required. Install with: pip install numpy")
    sys.exit(1)

from runtime_adapter import EmbeddingClient, LLMError

# Threshold configuration
SEMANTIC_WARNING_THRESHOLD = 0.65  # 低于此值标记为 warning
SEMANTIC_ERROR_THRESHOLD = 0.50    # 低于此值标记为 error


class SemanticScorer:
    """
    语义一致性评分器
    
    计算翻译对的跨语言语义相似度。
    """
    
    def __init__(self):
        """Initialize scorer with embedding client."""
        self.client: EmbeddingClient = None
    
    def _get_client(self) -> EmbeddingClient:
        """Lazy initialization of embedding client."""
        if self.client is None:
            self.client = EmbeddingClient()
        return self.client
    
    def score_batch(self, pairs: List[Dict]) -> List[Dict]:
        """
        批量计算翻译对的语义一致性评分
        
        Args:
            pairs: 翻译对列表，每项包含:
                   - id: 标识符
                   - source_zh: 中文源文
                   - target_ru: 俄文译文
                   
        Returns:
            评分结果列表，每项包含:
                - id: 标识符
                - semantic_score: 相似度分数 [0, 1]
                - semantic_status: "ok" | "warning" | "error"
        """
        if not pairs:
            return []
        
        # Extract texts
        source_texts = [p.get('source_zh', '') or '' for p in pairs]
        target_texts = [p.get('target_ru', '') or '' for p in pairs]
        
        # Batch embed
        client = self._get_client()
        try:
            source_embeddings = client.embed_batch(source_texts)
            target_embeddings = client.embed_batch(target_texts)
        except LLMError as e:
            print(f"[Error] Embedding failed: {e}")
            # Return error status for all
            return [{"id": p.get("id", str(i)), "semantic_score": 0.0, "semantic_status": "error"}
                    for i, p in enumerate(pairs)]
        
        # Calculate scores
        results = []
        for i, pair in enumerate(pairs):
            score = client.cosine_similarity(
                source_embeddings[i],
                target_embeddings[i]
            )
            
            # Determine status
            if score < SEMANTIC_ERROR_THRESHOLD:
                status = "error"
            elif score < SEMANTIC_WARNING_THRESHOLD:
                status = "warning"
            else:
                status = "ok"
            
            results.append({
                "id": pair.get("id", str(i)),
                "semantic_score": round(score, 4),
                "semantic_status": status
            })
        
        return results
    
    def filter_for_qa(self, pairs: List[Dict], threshold: float = SEMANTIC_WARNING_THRESHOLD) -> List[Dict]:
        """
        过滤出需要 LLM QA 的低分翻译对
        
        Args:
            pairs: 翻译对列表 (同 score_batch)
            threshold: 过滤阈值 (低于此值的翻译对会被返回)
            
        Returns:
            仅返回语义分数低于阈值的翻译对 (附带 semantic_score 字段)
        """
        scores = self.score_batch(pairs)
        
        filtered = []
        for pair, score_info in zip(pairs, scores):
            if score_info['semantic_score'] < threshold:
                pair_copy = pair.copy()
                pair_copy['semantic_score'] = score_info['semantic_score']
                pair_copy['semantic_status'] = score_info['semantic_status']
                filtered.append(pair_copy)
        
        return filtered
    
    def get_statistics(self, scores: List[Dict]) -> Dict:
        """
        计算评分统计信息
        
        Args:
            scores: score_batch() 的返回结果
            
        Returns:
            统计信息字典
        """
        if not scores:
            return {"total": 0, "ok": 0, "warning": 0, "error": 0, "avg_score": 0.0}
        
        ok_count = sum(1 for s in scores if s['semantic_status'] == 'ok')
        warning_count = sum(1 for s in scores if s['semantic_status'] == 'warning')
        error_count = sum(1 for s in scores if s['semantic_status'] == 'error')
        avg_score = sum(s['semantic_score'] for s in scores) / len(scores)
        
        return {
            "total": len(scores),
            "ok": ok_count,
            "warning": warning_count,
            "error": error_count,
            "avg_score": round(avg_score, 4)
        }


if __name__ == "__main__":
    # Quick test
    scorer = SemanticScorer()
    
    pairs = [
        {"id": "1", "source_zh": "生命值", "target_ru": "Здоровье"},
        {"id": "2", "source_zh": "攻击力", "target_ru": "Атака"},
        {"id": "3", "source_zh": "防御力", "target_ru": "Совершенно другое предложение"},  # Intentionally wrong
    ]
    
    print("Testing SemanticScorer...")
    results = scorer.score_batch(pairs)
    
    for r in results:
        print(f"  ID={r['id']}: score={r['semantic_score']:.3f}, status={r['semantic_status']}")
    
    stats = scorer.get_statistics(results)
    print(f"\nStatistics: {stats}")
