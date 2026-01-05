# AI 智能报告生成引擎

基于 vLLM + FastAPI 的异步报告生成微服务，支持接收多维度分数数据，调用大模型生成激励性/诊断性评估报告。

## 技术栈

- **语言**: Python 3.12+
- **Web 框架**: FastAPI（完全异步）
- **数据验证**: Pydantic v2
- **大模型推理**: vLLM（独立 Docker 服务）
- **LLM 客户端**: openai.AsyncOpenAI
- **配置管理**: pydantic-settings + PyYAML + Jinja2
- **容器化**: Docker + Docker Compose

## 项目结构

```
ReportLLM/
├── app/
│   ├── __init__.py
│   ├── main.py                 # FastAPI 应用入口（Lifespan 管理）
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py           # 配置管理（Pydantic Settings）
│   │   ├── logging.py          # 日志配置（loguru）
│   │   └── dependencies.py     # 全局依赖注入
│   ├── models/
│   │   ├── __init__.py
│   │   └── schemas.py          # Pydantic 数据模型
│   ├── routers/
│   │   ├── __init__.py
│   │   └── report.py           # 报告生成路由
│   └── services/
│       ├── __init__.py
│       └── report_service.py   # 业务逻辑（Prompt 渲染、vLLM 调用、回调）
├── config/
│   └── templates.yaml          # Jinja2 Prompt 模板
├── logs/                       # 日志目录（自动创建）
├── .env                        # 环境变量配置
├── .gitignore
├── requirements.txt            # Python 依赖
├── Dockerfile                  # API 服务镜像
├── docker-compose.yml          # 微服务编排
└── README.md
```

## 快速开始

### 1. 环境准备

确保已安装：
- Docker 20.10+
- Docker Compose 2.0+
- NVIDIA Docker Runtime（用于 GPU 支持）

### 2. 配置环境变量

编辑 `.env` 文件，配置以下参数：

```bash
# vLLM 服务配置
VLLM_API_URL=http://vllm-service:8000/v1
VLLM_MODEL_NAME=Qwen/Qwen2.5-7B-Instruct
VLLM_MAX_TOKENS=1000
VLLM_TEMPERATURE=0.1

# 后端 B 回调配置
BACKEND_B_CALLBACK_URL=http://backend-b:8080/api/callback
BACKEND_B_TIMEOUT=30

# API 服务配置
API_HOST=0.0.0.0
API_PORT=8000
API_WORKERS=1
```

**重要**: 请根据实际情况修改：
- `VLLM_MODEL_NAME`: 使用的模型名称
- `BACKEND_B_CALLBACK_URL`: 后端 B 的实际回调地址
- `MODEL_PATH`: 在 `docker-compose.yml` 中配置模型存储路径

### 3. 一键启动

```bash
# 启动所有服务（vLLM + API）
docker compose up -d

# 查看日志
docker compose logs -f

# 检查服务状态
docker compose ps
```

**注意**: vLLM 服务首次启动需要加载模型，可能需要 1-3 分钟。

### 4. 验证服务

```bash
# 检查 API 健康状态
curl http://localhost:8000/health

# 查看 API 文档
open http://localhost:8000/docs
```

## API 使用

### 生成报告

**端点**: `POST /api/v1/generate-report`

**请求示例**:

```bash
curl -X POST "http://localhost:8000/api/v1/generate-report" \
  -H "Content-Type: application/json" \
  -d '{
    "student_id": "STU20260105001",
    "scores": {
      "creativity": 85.0,
      "completeness": 90.0,
      "accuracy": 88.5,
      "collaboration": 92.0
    }
  }'
```

**响应示例** (HTTP 202 Accepted):

```json
{
  "trace_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "message": "报告生成任务已提交，正在后台处理"
}
```

### 工作流程

1. 前端 A 调用 `/api/v1/generate-report`，传入分数和学员 ID
2. API 立即返回 `trace_id`（用于追踪）
3. 后台异步执行：
   - 使用 Jinja2 渲染 Prompt 模板
   - 调用 vLLM 生成报告（4-5 段话）
   - 将报告和学员 ID 回调给后端 B
4. 全程日志记录（带 `trace_id`）

### 日志追踪

所有操作都携带 `trace_id`，可在日志中查询完整链路：

```bash
# 查看特定 trace_id 的日志
docker compose logs api-service | grep "a1b2c3d4-e5f6-7890-abcd-ef1234567890"

# 实时查看错误日志
tail -f logs/error_$(date +%Y-%m-%d).log
```

## 开发指南

### 本地开发（不使用 Docker）

```bash
# 1. 创建虚拟环境
python3.12 -m venv .venv
source .venv/bin/activate

# 2. 安装依赖
pip install -r requirements.txt

# 3. 配置 .env（修改 vLLM 地址为本地或远程 URL）
VLLM_API_URL=http://your-vllm-server:8000/v1

# 4. 启动 API 服务
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 修改 Prompt 模板

编辑 `config/templates.yaml`：

```yaml
report_generation:
  system_prompt: |
    你是一位资深的教育评估专家...
  
  user_prompt: |
    请根据以下学员的多维度表现分数，生成一份综合评估报告：
    {% for dimension, score in scores.items() %}
    - {{ dimension }}: {{ score }} 分
    {% endfor %}
```

修改后无需重启服务，下次请求自动加载新模板。

## 生产环境部署

### 1. 安全加固

- 修改 `.env` 中的敏感配置
- 在 `docker-compose.yml` 中限制 CORS 域名：
  ```python
  allow_origins=["https://your-frontend.com"]
  ```

### 2. 性能优化

- 根据硬件调整 `API_WORKERS`（建议 CPU 核心数）
- vLLM 参数调优：
  ```yaml
  --gpu-memory-utilization 0.95  # GPU 利用率
  --max-model-len 16384          # 上下文长度
  ```

### 3. 监控和告警

- 日志持久化已配置（`logs/` 目录）
- 建议接入 Prometheus + Grafana 监控
- 配置日志收集（ELK/Loki）

## 常见问题

### vLLM 服务无法启动

1. 检查 GPU 驱动：`nvidia-smi`
2. 检查 NVIDIA Docker Runtime：`docker run --rm --gpus all nvidia/cuda:11.8.0-base-ubuntu22.04 nvidia-smi`
3. 查看 vLLM 日志：`docker compose logs vllm-service`

### API 调用超时

- 检查 vLLM 是否正常：`curl http://localhost:8001/health`
- 调整 `VLLM_MAX_TOKENS` 减少生成时间
- 增加 `BACKEND_B_TIMEOUT`

### 后端 B 回调失败

- 检查网络连通性
- 确认 `BACKEND_B_CALLBACK_URL` 正确
- 查看错误日志：`logs/error_*.log`

## 许可证

MIT License

## 贡献指南

欢迎提交 Issue 和 Pull Request！
