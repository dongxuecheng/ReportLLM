"""
FastAPI 主应用入口
实现 Lifespan 管理全局资源（HTTP 客户端和 OpenAI 客户端）
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from openai import AsyncOpenAI
from loguru import logger

from app.core.config import settings
from app.core.logging import setup_logging
from app.routers import report


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    应用生命周期管理
    启动时初始化全局客户端，关闭时清理资源
    """
    # 初始化日志系统
    setup_logging()
    logger.info("应用启动中...")

    # 初始化全局 HTTP 客户端（用于调用后端 B）
    app.state.http_client = httpx.AsyncClient(
        timeout=httpx.Timeout(settings.backend_b_timeout),
        limits=httpx.Limits(max_keepalive_connections=20, max_connections=100),
        follow_redirects=True,
    )
    logger.info(f"HTTP 客户端初始化完成，超时设置: {settings.backend_b_timeout}s")

    # 初始化全局 OpenAI 客户端（用于调用 vLLM）
    app.state.openai_client = AsyncOpenAI(
        api_key="EMPTY",  # vLLM 不需要真实 API Key
        base_url=settings.vllm_api_url,
        timeout=httpx.Timeout(300.0),  # vLLM 生成可能较慢
    )
    logger.info(f"OpenAI 客户端初始化完成，vLLM 地址: {settings.vllm_api_url}")

    logger.info("应用启动完成，所有资源已就绪")

    yield  # 应用运行中

    # 应用关闭，清理资源
    logger.info("应用关闭中，清理资源...")
    await app.state.http_client.aclose()
    logger.info("HTTP 客户端已关闭")
    await app.state.openai_client.close()
    logger.info("OpenAI 客户端已关闭")
    logger.info("应用已安全关闭")


# 创建 FastAPI 应用实例
app = FastAPI(
    title="AI 智能报告生成引擎",
    description="基于 vLLM 的异步报告生成服务",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# 配置 CORS（允许前端 A 跨域调用）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境建议配置具体域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(report.router, prefix="/api/v1", tags=["报告生成"])


@app.get("/health", tags=["健康检查"])
async def health_check() -> dict:
    """健康检查端点"""
    return {
        "status": "healthy",
        "service": "report-generation-api",
        "vllm_url": settings.vllm_api_url,
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.api_host,
        port=settings.api_port,
        workers=settings.api_workers,
        log_level="info",
        access_log=True,
    )
