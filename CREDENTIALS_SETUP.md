
# 凭证配置指南

## 快速开始

### 1. 设置环境变量

```bash
export LLM_API_KEY="your_api_key_here"
export LLM_BASE_URL="https://api.apiyi.com/v1"  # 可选,默认已设置
```

### 2. 启动项目

```bash
# 方式1: 使用启动脚本
./run.sh

# 方式2: 手动启动
docker-compose up --build

# 方式3: 本地运行(无 Docker)
python example_usage.py
```

## 重要说明

- **不要**将真实 API key 提交到 Git
- **不要**在 Dockerfile 中硬编码 key
- **不要**在代码中直接指定模型名称

## 模型调度

所有 LLM 调用统一通过 `infra` 层:

```python
from infra import get_llm_adapter

adapter = get_llm_adapter()
response = adapter.call(
    prompt="你的提示词",
    task_type="code_generation"  # 自动选择合适模型
)
```

## 任务类型与模型映射

| 任务类型 | 自动选择模型 |
| --- | --- |
| code_generation | gpt-4-turbo |
| quick_response | gpt-4.1-mini |
| reasoning | gpt-4 |
| default | gpt-4.1-mini |

修改策略: 编辑 `infra/llm_runtime.py` 中的 `get_model_for_task` 方法
