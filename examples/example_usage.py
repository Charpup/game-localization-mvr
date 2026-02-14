"""
使用示例:展示如何通过 infra 层调用 LLM
"""
from infra import get_llm_adapter, batch_call

def example_single_call():
    """单次调用示例"""
    adapter = get_llm_adapter()

    response = adapter.call(
        prompt="解释什么是 MVP (Minimal Viable Product)",
        task_type="quick_response"
    )

    print("--- Single Call Response ---")
    print(response)
    print("---------------------------")

def example_batch_call():
    """批量调用示例"""
    prompts = [
        "什么是敏捷开发?",
        "什么是持续集成 (CI)?",
        "什么是 Docker 容器?"
    ]

    print("\n--- Batch Call Responses ---")
    responses = batch_call(prompts, task_type="quick_response")

    for q, a in zip(prompts, responses):
        print(f"Q: {q}\nA: {a}\n---")
    print("----------------------------")

if __name__ == "__main__":
    # 运行前需设置环境变量:
    # export LLM_API_KEY="your_key"
    # export LLM_BASE_URL="https://api.apiyi.com/v1"
    
    try:
        example_single_call()
        # example_batch_call()
    except Exception as e:
        print(f"Error: {e}")
        print("请检查环境变量 LLM_API_KEY 是否已正确设置。")
