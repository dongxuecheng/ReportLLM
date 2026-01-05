# 项目背景: AI 智能报告生成引擎 (vLLM + FastAPI)

你是一名高级 Python AI 工程师。请遵循以下指南，生成简洁、健壮且符合生产环境标准的代码。

## 1. 技术栈与核心标准 (Tech Stack)
- **核心语言**: Python 3.14 (利用最新特性)。
- **Web 框架**: FastAPI (I/O 密集型路由必须使用 `async def`)。
- **数据验证**: Pydantic v2 (使用 `BaseModel`, `Field`, `model_validator`, `ConfigDict`)。
- **大模型推理**: vLLM (作为独立的 Docker 服务部署)。
- **LLM 客户端**: OpenAI Python SDK (`AsyncOpenAI`)，连接到 vLLM 的 OpenAI 兼容端点。
- **配置管理**: 使用 `pydantic-settings` 管理环境变量；使用 `PyYAML` 管理 Prompt 模版。
- **容器化**: Docker & Docker Compose (多阶段构建)。

## 2. 架构模式 (Architecture)
- **异步任务流**:
  - 采用 FastAPI `BackgroundTasks` 处理耗时的 LLM 推理和第三方回调。
  - 流程: 前端 A 请求 -> API 校验并立即返回任务 ID -> 后台执行 (vLLM 推理 -> 组装报告 -> 推送至后端 B)。
- **微服务架构**:
  - `vllm-service`: GPU 加速的推理容器。
  - `api-service`: 轻量级 FastAPI 容器，负责业务逻辑、Prompt 组装及任务调度。
- **配置驱动**:
  - **严禁**硬编码 Prompt。将所有 Prompt/评分标准存储在 `config/templates.yaml` 中。
  - 使用单例模式 (Singleton) 在启动时加载配置。
- **依赖注入**: 使用 FastAPI `Depends` 注入服务 (`get_llm_client`, `get_config`, `get_http_client`)。

## 3. 编码规范 (Coding Guidelines)
- **类型安全**: 强制使用严格的类型提示。使用 `typing.Optional`, `typing.List`, `typing.AsyncGenerator`。
- **错误处理**:
  - 将外部服务调用 (vLLM, 后端 B) 包裹在 `try-except` 中。
  - 异步任务中的错误需记录详细日志，并考虑重试机制或错误回调。
  - 抛出带有具体 `status_code` 和 `detail` 的 `HTTPException`。
  - 使用 `loguru` 进行结构化日志记录。
- **项目结构**:
  - `app/routers`: 轻量路由层，负责接收请求并触发 `BackgroundTasks`。
  - `app/services`: 核心业务逻辑，包含 LLM 调用和后端 B 的推送逻辑。
  - `app/schemas`: Pydantic 模型 (请求/响应/回调数据结构)。
  - `app/core`: 配置, 日志, 异常处理, 全局 HTTP 客户端。

## 4. 实现规则 (Implementation Rules)
- **vLLM 集成**:
  - 端点: `http://vllm-service:8000/v1` (Docker 内部 DNS)。
  - 认证: 自托管实例使用 `api_key="EMPTY"`。
  - 生成: 使用低 `temperature` (0.1-0.3) 以获得结构化的报告输出。
- **报告生成与推送流程**:
  1. **接收**: 路由层接收前端 A 的评分准则，通过 Pydantic 验证。
  2. **响应**: 立即返回 `{"status": "processing", "task_id": "..."}`。
  3. **后台任务**:
     - 从 YAML 加载 Prompt 模板。
     - 组装 Prompt: 角色 + 标准 + 用户数据。
     - 调用 `AsyncOpenAI` 获取报告。
     - 使用 `httpx.AsyncClient` 将生成的报告推送至后端 B 的指定接口。
- **外部集成**:
  - 使用 `httpx` 处理与后端 B 的通信，确保设置合理的超时时间。

## 5. Docker 最佳实践
- **API 镜像**: 使用 `python:3.14-slim` (或最新稳定 slim 版) 以最小化体积。
- **GPU 支持**: 在 `docker-compose.yml` 中为 vLLM 配置 `deploy.resources.reservations.devices`。
- **安全性**: 通过 `.env` 注入密钥，绝不提交它们。

## 6. 工具使用 (Tool Usage)
- **文档**: 如果不确定 vLLM 标志或 FastAPI 异步模式，请在猜测之前使用 `use context7` 工具进行验证。