"""
全局依赖注入模块
提供访问全局单例资源的接口
"""

from typing import TYPE_CHECKING
from fastapi import Request
import httpx
from openai import AsyncOpenAI

if TYPE_CHECKING:
    from fastapi import FastAPI


def get_http_client(request: Request) -> httpx.AsyncClient:
    """
    获取全局 HTTP 客户端单例
    用于调用后端 B 的回调接口

    Args:
        request: FastAPI 请求对象

    Returns:
        httpx.AsyncClient: 全局 HTTP 客户端
    """
    return request.app.state.http_client


def get_openai_client(request: Request) -> AsyncOpenAI:
    """
    获取全局 OpenAI 客户端单例
    用于调用 vLLM 服务

    Args:
        request: FastAPI 请求对象

    Returns:
        AsyncOpenAI: 全局 OpenAI 客户端
    """
    return request.app.state.openai_client
