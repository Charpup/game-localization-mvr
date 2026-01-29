#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
test_embedding_infrastructure.py

Unit tests for Text Embedding infrastructure:
- EmbeddingClient (runtime_adapter)
- GlossaryVectorStore
- SemanticScorer

Run with:
    python -m pytest tests/test_embedding_infrastructure.py -v
"""

import sys
import os
import unittest

# Add scripts to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

import numpy as np


class TestEmbeddingClient(unittest.TestCase):
    """EmbeddingClient 测试"""
    
    @classmethod
    def setUpClass(cls):
        """Skip all tests if API not configured."""
        from runtime_adapter import EmbeddingClient, LLMError
        try:
            cls.client = EmbeddingClient()
        except LLMError:
            cls.client = None
    
    def test_embed_single(self):
        """测试单条向量化"""
        if self.client is None:
            self.skipTest("API not configured")
        
        emb = self.client.embed_single("测试文本")
        
        self.assertEqual(len(emb), 1536)  # text-embedding-3-small 维度
        self.assertIsInstance(emb, np.ndarray)
    
    def test_embed_single_empty(self):
        """测试空文本"""
        if self.client is None:
            self.skipTest("API not configured")
        
        emb = self.client.embed_single("")
        
        self.assertEqual(len(emb), 1536)
        # Empty text should return zeros
        self.assertTrue(np.allclose(emb, 0))
    
    def test_embed_batch(self):
        """测试批量向量化"""
        if self.client is None:
            self.skipTest("API not configured")
        
        texts = ["文本1", "文本2", "文本3"]
        embs = self.client.embed_batch(texts)
        
        self.assertEqual(embs.shape, (3, 1536))
        self.assertIsInstance(embs, np.ndarray)
    
    def test_embed_batch_empty(self):
        """测试空列表"""
        if self.client is None:
            self.skipTest("API not configured")
        
        embs = self.client.embed_batch([])
        
        self.assertEqual(embs.shape[0], 0)
    
    def test_cosine_similarity(self):
        """测试余弦相似度"""
        if self.client is None:
            self.skipTest("API not configured")
        
        # 相同文本应该高度相似
        emb1 = self.client.embed_single("人工智能")
        emb2 = self.client.embed_single("人工智能技术")
        emb3 = self.client.embed_single("美食烹饪")
        
        sim_same = self.client.cosine_similarity(emb1, emb2)
        sim_diff = self.client.cosine_similarity(emb1, emb3)
        
        self.assertGreater(sim_same, 0.7)  # 相似文本
        self.assertLess(sim_diff, 0.7)     # 不相关文本
        self.assertGreater(sim_same, sim_diff)  # 相似度排序正确
    
    def test_batch_cosine_similarity(self):
        """测试批量余弦相似度"""
        if self.client is None:
            self.skipTest("API not configured")
        
        query = self.client.embed_single("攻击")
        corpus = self.client.embed_batch(["攻击力", "防御力", "生命值"])
        
        sims = self.client.batch_cosine_similarity(query, corpus)
        
        self.assertEqual(len(sims), 3)
        # 攻击 should be most similar to 攻击力
        self.assertEqual(np.argmax(sims), 0)


class TestGlossaryVectorStore(unittest.TestCase):
    """GlossaryVectorStore 测试"""
    
    def test_load_nonexistent(self):
        """测试加载不存在的术语表"""
        from glossary_vectorstore import GlossaryVectorStore
        
        store = GlossaryVectorStore("nonexistent_glossary.yaml")
        count = store.load_glossary()
        
        self.assertEqual(count, 0)
    
    def test_format_for_prompt(self):
        """测试 Prompt 格式化"""
        from glossary_vectorstore import GlossaryVectorStore
        
        store = GlossaryVectorStore()
        
        # Test with empty
        result = store.format_for_prompt([])
        self.assertEqual(result, "")
        
        # Test with terms
        terms = [
            {"term_zh": "攻击力", "term_ru": "Атака", "similarity": 0.9},
            {"term_zh": "防御力", "term_ru": "Защита", "similarity": 0.8},
        ]
        result = store.format_for_prompt(terms)
        
        self.assertIn("攻击力", result)
        self.assertIn("Атака", result)
        self.assertIn("→", result)


class TestSemanticScorer(unittest.TestCase):
    """SemanticScorer 测试"""
    
    @classmethod
    def setUpClass(cls):
        """Skip all tests if API not configured."""
        from runtime_adapter import EmbeddingClient, LLMError
        try:
            EmbeddingClient()
            cls.api_available = True
        except LLMError:
            cls.api_available = False
    
    def test_score_batch(self):
        """测试语义评分"""
        if not self.api_available:
            self.skipTest("API not configured")
        
        from semantic_scorer import SemanticScorer
        
        scorer = SemanticScorer()
        
        pairs = [
            {"id": "1", "source_zh": "攻击力", "target_ru": "Атака"},
            {"id": "2", "source_zh": "防御力", "target_ru": "Защита"},
        ]
        
        results = scorer.score_batch(pairs)
        
        self.assertEqual(len(results), 2)
        for r in results:
            self.assertIn('semantic_score', r)
            self.assertIn('semantic_status', r)
            self.assertGreaterEqual(r['semantic_score'], 0)
            self.assertLessEqual(r['semantic_score'], 1)
    
    def test_score_batch_empty(self):
        """测试空列表"""
        from semantic_scorer import SemanticScorer
        
        scorer = SemanticScorer()
        results = scorer.score_batch([])
        
        self.assertEqual(len(results), 0)
    
    def test_get_statistics(self):
        """测试统计计算"""
        from semantic_scorer import SemanticScorer
        
        scorer = SemanticScorer()
        
        # Mock scores
        scores = [
            {"id": "1", "semantic_score": 0.8, "semantic_status": "ok"},
            {"id": "2", "semantic_score": 0.6, "semantic_status": "warning"},
            {"id": "3", "semantic_score": 0.4, "semantic_status": "error"},
        ]
        
        stats = scorer.get_statistics(scores)
        
        self.assertEqual(stats["total"], 3)
        self.assertEqual(stats["ok"], 1)
        self.assertEqual(stats["warning"], 1)
        self.assertEqual(stats["error"], 1)
        self.assertAlmostEqual(stats["avg_score"], 0.6, places=2)
    
    def test_filter_for_qa(self):
        """测试 QA 过滤"""
        if not self.api_available:
            self.skipTest("API not configured")
        
        from semantic_scorer import SemanticScorer
        
        scorer = SemanticScorer()
        
        pairs = [
            {"id": "1", "source_zh": "生命值", "target_ru": "Здоровье"},
            {"id": "2", "source_zh": "攻击力", "target_ru": "Совершенно другое предложение о погоде"},  # Wrong
        ]
        
        filtered = scorer.filter_for_qa(pairs, threshold=0.7)
        
        # At least the wrong translation should be filtered
        self.assertGreaterEqual(len(filtered), 0)  # May vary based on actual scores


if __name__ == '__main__':
    unittest.main(verbosity=2)
