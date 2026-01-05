"""
日志配置模块
使用 loguru 配置全局日志，支持 trace_id 上下文绑定
"""

import sys
from loguru import logger


def setup_logging() -> None:
    """配置 loguru 日志格式和输出"""

    # 移除默认的 handler
    logger.remove()

    # 添加控制台输出（带颜色）
    logger.add(
        sys.stdout,
        format="<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{extra[trace_id]}</cyan> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
        "<level>{message}</level>",
        level="INFO",
        colorize=True,
    )

    # 添加文件输出（JSON 格式，便于日志收集）
    logger.add(
        "logs/app_{time:YYYY-MM-DD}.log",
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level} | {extra[trace_id]} | {name}:{function}:{line} | {message}",
        level="INFO",
        rotation="00:00",  # 每天零点轮转
        retention="30 days",  # 保留 30 天
        compression="zip",  # 压缩旧日志
        encoding="utf-8",
        enqueue=True,  # 异步写入
    )

    # 错误日志单独文件
    logger.add(
        "logs/error_{time:YYYY-MM-DD}.log",
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level} | {extra[trace_id]} | {name}:{function}:{line} | {message}",
        level="ERROR",
        rotation="00:00",
        retention="90 days",  # 错误日志保留更久
        compression="zip",
        encoding="utf-8",
        enqueue=True,
        backtrace=True,  # 记录完整堆栈
        diagnose=True,  # 诊断信息
    )

    logger.info("日志系统初始化完成")


# 为没有 trace_id 的日志提供默认值
logger.configure(extra={"trace_id": "SYSTEM"})
