"""
LLM Runtime Adapter
负责统一调度 LLM 调用,避免模型硬编码
"""
import os
from typing import Optional, Dict, Any

class LLMRuntimeConfig:
    """运行时 LLM 配置"""

    def __init__(self):
        self.api_key = os.getenv("LLM_API_KEY")
        self.base_url = os.getenv("LLM_BASE_URL", "https://api.apiyi.com/v1")

        if not self.api_key:
            raise ValueError("LLM_API_KEY 环境变量未设置")

    def validate(self) -> bool:
        """验证配置完整性"""
        return bool(self.api_key and self.base_url)

class LLMAdapter:
    """LLM 调用适配器"""

    def __init__(self, config: LLMRuntimeConfig):
        self.config = config
        self.client = None  # 实际 client 实例(OpenAI/Anthropic)

    def init_client(self):
        """初始化 LLM 客户端"""
        # 根据 base_url 判断使用哪个 SDK
        import openai
        self.client = openai.OpenAI(
            api_key=self.config.api_key,
            base_url=self.config.base_url
        )

    def get_model_for_task(self, task_type: str) -> str:
        """
        根据任务类型动态选择模型
        MVP: 简单映射,后续可扩展为配置文件或策略模式
        """
        model_map = {
            "code_generation": "gpt-4-turbo",
            "quick_response": "gpt-4.1-mini",
            "reasoning": "gpt-4",
            "default": "gpt-4.1-mini"
        }
        return model_map.get(task_type, model_map["default"])

    def call(
        self,
        prompt: str,
        task_type: str = "default",
        **kwargs
    ) -> str:
        """
        统一 LLM 调用入口

        Args:
            prompt: 用户提示词
            task_type: 任务类型(用于模型选择)
            **kwargs: 其他 LLM 参数

        Returns:
            LLM 响应文本
        """
        if not self.client:
            self.init_client()

        model = self.get_model_for_task(task_type)

        response = self.client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            **kwargs
        )

        return response.choices[0].message.content

# 全局单例
_runtime_config = None
_llm_adapter = None

def get_llm_adapter() -> LLMAdapter:
    """获取全局 LLM 适配器实例"""
    global _runtime_config, _llm_adapter

    if _llm_adapter is None:
        _runtime_config = LLMRuntimeConfig()
        _llm_adapter = LLMAdapter(_runtime_config)

    return _llm_adapter
