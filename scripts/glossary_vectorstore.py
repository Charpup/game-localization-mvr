#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
glossary_vectorstore.py (v1.0)

术语表向量化存储与检索

Features:
- 加载术语表并计算向量
- 缓存向量到本地 .npz 文件
- 检索与源文本相关的术语 (Top-K)
- 格式化为 Prompt 注入格式

Usage:
    from glossary_vectorstore import GlossaryVectorStore
    
    store = GlossaryVectorStore("workflow/glossary_approved.yaml")
    store.load_glossary()
    store.build_index()
    
    terms = store.retrieve_relevant_terms(["攻击力提升50%"], top_k=15)
    prompt_section = store.format_for_prompt(terms)
"""

import os
import sys
from typing import List, Dict, Optional

# Ensure scripts directory is in path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    import numpy as np
except ImportError:
    print("ERROR: numpy is required. Install with: pip install numpy")
    sys.exit(1)

try:
    import yaml
except ImportError:
    yaml = None

from runtime_adapter import EmbeddingClient, LLMError

# Configuration
DEFAULT_TOP_K = 15
SIMILARITY_THRESHOLD = 0.3  # Minimum similarity to include
GLOSSARY_CACHE_FILE = "cache/glossary_embeddings.npz"


class GlossaryVectorStore:
    """
    术语表向量存储
    
    Manages glossary embeddings for RAG-based term retrieval.
    """
    
    def __init__(self, glossary_path: str = "workflow/glossary_approved.yaml"):
        """
        Initialize vector store.
        
        Args:
            glossary_path: Path to glossary YAML file
        """
        self.client: Optional[EmbeddingClient] = None
        self.glossary_path = glossary_path
        self.terms: List[Dict] = []
        self.term_texts: List[str] = []
        self.embeddings: Optional[np.ndarray] = None
    
    def _get_client(self) -> EmbeddingClient:
        """Lazy initialization of embedding client."""
        if self.client is None:
            self.client = EmbeddingClient()
        return self.client
    
    def load_glossary(self) -> int:
        """
        加载术语表
        
        Returns:
            int: 加载的术语数量
        """
        if yaml is None:
            print("[Warning] PyYAML not installed. Cannot load glossary.")
            return 0
        
        if not os.path.exists(self.glossary_path):
            print(f"[Warning] Glossary not found: {self.glossary_path}")
            return 0
        
        try:
            with open(self.glossary_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
        except Exception as e:
            print(f"[Error] Failed to load glossary: {e}")
            return 0
        
        # Extract approved entries
        entries = data.get('entries', [])
        self.terms = [e for e in entries if e.get('status', '').lower() == 'approved']
        
        # If no status field, include all entries
        if not self.terms and entries:
            self.terms = entries
        
        self.term_texts = [t.get('term_zh', '') for t in self.terms]
        
        print(f"[GlossaryVectorStore] Loaded {len(self.terms)} terms from {self.glossary_path}")
        return len(self.terms)
    
    def build_index(self, force_rebuild: bool = False) -> None:
        """
        构建向量索引
        
        Args:
            force_rebuild: 强制重建 (忽略缓存)
        """
        cache_path = GLOSSARY_CACHE_FILE
        os.makedirs(os.path.dirname(cache_path) or ".", exist_ok=True)
        
        # Check cache validity
        if not force_rebuild and os.path.exists(cache_path):
            try:
                cached = np.load(cache_path, allow_pickle=True)
                cached_texts = cached['texts'].tolist()
                
                # Validate cache matches current glossary
                if cached_texts == self.term_texts:
                    self.embeddings = cached['embeddings']
                    print(f"[GlossaryVectorStore] Loaded cached embeddings ({len(self.terms)} terms)")
                    return
            except Exception as e:
                print(f"[GlossaryVectorStore] Cache load error, rebuilding: {e}")
        
        # Build new index
        if not self.term_texts:
            self.embeddings = np.array([]).reshape(0, 1536)
            return
        
        print(f"[GlossaryVectorStore] Computing embeddings for {len(self.term_texts)} terms...")
        
        try:
            client = self._get_client()
            self.embeddings = client.embed_batch(self.term_texts, use_cache=False)
        except LLMError as e:
            print(f"[Error] Embedding API failed: {e}")
            self.embeddings = np.array([]).reshape(0, 1536)
            return
        
        # Save cache
        try:
            np.savez(cache_path,
                     texts=np.array(self.term_texts, dtype=object),
                     embeddings=self.embeddings)
            print(f"[GlossaryVectorStore] Cached embeddings to {cache_path}")
        except Exception as e:
            print(f"[Warning] Failed to cache embeddings: {e}")
    
    def retrieve_relevant_terms(self, source_texts: List[str], top_k: int = DEFAULT_TOP_K) -> List[Dict]:
        """
        检索与源文本相关的术语
        
        Args:
            source_texts: 源文本列表
            top_k: 返回最相关的 K 个术语
            
        Returns:
            去重后的相关术语列表，包含 term_zh, term_ru, similarity
        """
        if self.embeddings is None or len(self.embeddings) == 0:
            return []
        
        if not source_texts:
            return []
        
        # Compute source embeddings
        client = self._get_client()
        try:
            source_embeddings = client.embed_batch(source_texts)
        except LLMError as e:
            print(f"[Error] Failed to embed source texts: {e}")
            return []
        
        # Aggregate similarities (max similarity for each term across all sources)
        all_similarities = np.zeros(len(self.terms))
        
        for src_emb in source_embeddings:
            similarities = client.batch_cosine_similarity(src_emb, self.embeddings)
            all_similarities = np.maximum(all_similarities, similarities)
        
        # Get Top-K indices
        top_indices = np.argsort(all_similarities)[::-1][:top_k]
        
        results = []
        for idx in top_indices:
            sim = all_similarities[idx]
            if sim > SIMILARITY_THRESHOLD:
                term = self.terms[idx]
                results.append({
                    'term_zh': term.get('term_zh', ''),
                    'term_ru': term.get('term_ru', ''),
                    'similarity': float(sim)
                })
        
        return results
    
    def format_for_prompt(self, relevant_terms: List[Dict]) -> str:
        """
        格式化为 Prompt 注入格式
        
        Args:
            relevant_terms: retrieve_relevant_terms() 的返回结果
            
        Returns:
            可直接注入到 System Prompt 的字符串
        """
        if not relevant_terms:
            return ""
        
        lines = ["## Relevant Glossary Terms (Use these translations):"]
        for t in relevant_terms:
            lines.append(f"- {t['term_zh']} → {t['term_ru']}")
        
        return "\n".join(lines)


if __name__ == "__main__":
    # Quick test
    store = GlossaryVectorStore()
    count = store.load_glossary()
    
    if count > 0:
        store.build_index()
        terms = store.retrieve_relevant_terms(["攻击力提升"], top_k=5)
        print(f"\nRetrieved {len(terms)} terms:")
        for t in terms:
            print(f"  {t['term_zh']} -> {t['term_ru']} (sim={t['similarity']:.3f})")
    else:
        print("No glossary loaded for testing.")
