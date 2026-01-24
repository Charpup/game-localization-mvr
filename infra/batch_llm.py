"""
Batch LLM 批量调用模块
用于高效处理批量 LLM 请求
"""
from typing import List, Dict, Any
from concurrent.futures import ThreadPoolExecutor, as_completed
from .llm_runtime import get_llm_adapter

class BatchLLMProcessor:
    """批量 LLM 处理器"""

    def __init__(self, max_workers: int = 5):
        self.adapter = get_llm_adapter()
        self.max_workers = max_workers

    def process_batch(
        self,
        prompts: List[str],
        task_type: str = "default",
        **kwargs
    ) -> List[str]:
        """
        批量处理 LLM 请求

        Args:
            prompts: 提示词列表
            task_type: 任务类型
            **kwargs: LLM 参数

        Returns:
            响应列表(顺序与输入一致)
        """
        results = [None] * len(prompts)

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_idx = {
                executor.submit(
                    self.adapter.call,
                    prompt,
                    task_type,
                    **kwargs
                ): idx
                for idx, prompt in enumerate(prompts)
            }

            for future in as_completed(future_to_idx):
                idx = future_to_idx[future]
                try:
                    results[idx] = future.result()
                except Exception as e:
                    results[idx] = f"ERROR: {str(e)}"

        return results

def batch_call(prompts: List[str], **kwargs) -> List[str]:
    """批量调用快捷函数"""
    processor = BatchLLMProcessor()
    return processor.process_batch(prompts, **kwargs)
