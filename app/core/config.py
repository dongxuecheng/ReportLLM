"""
配置管理模块
使用 pydantic-settings 从环境变量加载配置
"""

from pydantic import Field, HttpUrl
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """应用配置类"""

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=False, extra="ignore"
    )

    # vLLM 配置
    vllm_api_url: str = Field(
        default="http://vllm-service:8000/v1", description="vLLM 服务地址"
    )
    vllm_model_name: str = Field(
        default="Qwen/Qwen2.5-7B-Instruct", description="使用的模型名称"
    )
    vllm_max_tokens: int = Field(
        default=1000, ge=100, le=4096, description="生成报告的最大 token 数"
    )
    vllm_temperature: float = Field(
        default=0.1, ge=0.0, le=2.0, description="生成温度，越低越稳定"
    )

    # 后端 B 配置
    backend_b_callback_url: str = Field(description="后端 B 的回调地址")
    backend_b_timeout: int = Field(
        default=30, ge=5, le=300, description="调用后端 B 的超时时间（秒）"
    )

    # API 服务配置
    api_host: str = Field(default="0.0.0.0", description="API 监听地址")
    api_port: int = Field(default=8000, ge=1024, le=65535, description="API 监听端口")
    api_workers: int = Field(default=1, ge=1, le=16, description="API 工作进程数")


# 全局配置实例（单例）
settings = Settings()
