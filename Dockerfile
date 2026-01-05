# Multi-stage build for production
FROM python:3.12-slim AS builder

WORKDIR /build

# 安装依赖
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Production stage
FROM python:3.12-slim

WORKDIR /app

# 复制 Python 包
COPY --from=builder /root/.local /root/.local

# 复制应用代码
COPY app/ ./app/
COPY config/ ./config/
COPY .env .env

# 创建日志目录
RUN mkdir -p logs

# 设置 Python 路径
ENV PATH=/root/.local/bin:$PATH
ENV PYTHONUNBUFFERED=1

# 暴露端口
EXPOSE 8000

# 启动命令
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
