FROM python:3.11-slim

WORKDIR /app

# 安装依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制代码(不包含 .env)
COPY . .

# 不设置任何 ENV 硬编码的 key
# ENV LLM_API_KEY="" # 已删除

# 运行时从宿主机注入环境变量
CMD ["python", "example_usage.py"]
