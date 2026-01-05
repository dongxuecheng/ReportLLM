# 项目背景: AI 智能报告生成引擎 (vLLM + FastAPI)

你是一名高级 Python AI 工程师。请遵循以下指南，生成简洁、健壮、高并发且符合生产环境标准的代码。

## 1. 技术栈与核心标准 (Tech Stack)
- **核心语言**: Python 3.12+ (兼顾性能与生态稳定性)。
- **Web 框架**: FastAPI (完全异步 `async def`，使用 `Lifespan` 管理资源)。
- **数据验证**: Pydantic v2 (严禁 v1 语法，使用 `model_validator(mode='after')`)。
- **大模型推理**: vLLM (独立 Docker 服务)。
- **LLM 客户端**: `openai.AsyncOpenAI`。
- **配置管理**: `pydantic-settings` (环境变量) + `PyYAML` (Prompt 存储) + `Jinja2` (Prompt 渲染)。
- **容器化**: Docker (Multi-stage builds) & Docker Compose。

## 2. 架构模式 (Architecture)
- **异步任务编排**:
  - 流程: 请求 -> 生成 `trace_id` -> `BackgroundTasks` -> 立即响应 202。
  - **资源复用**: HTTP 客户端 (`httpx.AsyncClient`) 和 LLM 客户端必须是**全局单例**，在 FastAPI `lifespan` 中初始化和关闭，严禁在每个请求中频繁创建。
- **微服务**: `vllm-service` (GPU) + `api-service` (CPU/IO)。
- **配置驱动**:
  - Prompt 模板存储在 `config/templates.yaml`。
  - 使用 Jinja2 语法 (e.g., `{{ user_input }}`) 增强模版灵活性。
- **可观测性**:
  - 所有日志必须包含 `trace_id`。
  - 异常捕获后必须记录堆栈信息。

## 3. 编码规范 (Coding Guidelines)
- **代码风格**: 简洁优雅，注释使用中文。遵循 PEP 8。
- **类型安全**: 100% 类型覆盖。使用 `typing` 模块的高级特性。
- **项目结构**:
  - `app/routers`: 仅处理参数校验、生成 ID、触发任务、返回响应。
  - `app/services`: 业务逻辑闭环（Prompt 渲染 -> LLM 交互 -> 回调）。
  - `app/core`: 生命周期管理、全局单例、中间件。
- **错误处理**:
  - 外部调用 (vLLM/后端B) 必须有**超时控制 (Timeout)** 和 **重试策略 (Tenacity)**。
  - 遇到错误时，不仅要记录日志，还需向后端 B 推送一个“失败状态”的回调，防止死链。

## 4. 实现规则 (Implementation Rules)
- **vLLM 集成**:
  - 地址: `http://vllm-service:8000/v1`。
  - 参数: `temperature=0.1` (保证格式稳定), `max_tokens` 需根据报告长度预设。
- **全链路追踪 (Traceability)**:
  1. **入口**: 生成 UUID `trace_id`。
  2. **日志**: 使用 `loguru` 的 `context` 绑定 `trace_id`。
  3. **透传**: 调用 vLLM 和 后端 B 时，将 `trace_id` 放入 HTTP Header 或 Payload 中。
- **回调机制**:
  - 使用全局的 `httpx.AsyncClient` 推送结果。
  - 必须处理后端 B 的网络异常，确保任务最终的一致性。

## 5. Docker 编排最佳实践 (Docker Compose)
- **目标**: 实现 `docker compose up -d` 一键启动整个系统。
- **服务定义**:
  - **`vllm-service`**:
    - 必须配置 `deploy.resources.reservations.devices` 以透传 GPU。
    - 暴露端口 8000 给宿主机以便调试 (可选)，容器间通过 `vllm-service:8000` 通信。
  - **`api-service`**:
    - 依赖配置: 使用 `depends_on` 确保 API 在 vLLM 容器启动后启动。
    - 环境变量: 通过 `.env` 注入关键配置 (如 `VLLM_API_URL`)。
- **网络**: 两个服务必须在同一个 Docker Bridge 网络中。

## 6. 工具使用 (Tool Usage)
- 遇到不确定的 FastAPI 写法或 vLLM 参数时，优先使用 `use context7` (如果可用) 查阅最新文档，拒绝幻觉。