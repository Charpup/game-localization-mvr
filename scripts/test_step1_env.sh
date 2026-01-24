#!/bin/bash
# Step 1: Environment Check
echo "=== Environment Check ==="
python --version
pip list | grep -E 'openai|numpy'

echo ""
echo "=== File Check ==="
ls -la scripts/runtime_adapter.py scripts/glossary_vectorstore.py scripts/semantic_scorer.py tests/test_embedding_infrastructure.py

echo ""
echo "=== API Key Check ==="
python -c "import os; print('LLM_API_KEY:', 'SET' if os.getenv('LLM_API_KEY') else 'NOT SET')"
python -c "import os; print('LLM_BASE_URL:', os.getenv('LLM_BASE_URL', 'NOT SET'))"
