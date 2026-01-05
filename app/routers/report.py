"""
报告生成 API 路由
处理前端 A 的请求，触发后台任务
"""

from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, status
from loguru import logger
import httpx
from openai import AsyncOpenAI

from app.core.dependencies import get_http_client, get_openai_client
from app.models.schemas import ReportRequest, ReportResponse
from app.services.report_service import ReportService


router = APIRouter()


@router.post(
    "/generate-report",
    response_model=ReportResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="生成学员评估报告",
    description="接收学员的多维度分数，异步生成评估报告并回调后端 B",
)
async def generate_report(
    request: ReportRequest,
    background_tasks: BackgroundTasks,
    openai_client: AsyncOpenAI = Depends(get_openai_client),
    http_client: httpx.AsyncClient = Depends(get_http_client),
) -> ReportResponse:
    """
    生成报告端点

    工作流程:
    1. 生成 trace_id 用于全链路追踪
    2. 将报告生成任务加入后台队列
    3. 立即返回 202 Accepted 和 trace_id
    4. 后台任务: 渲染 Prompt -> 调用 vLLM -> 回调后端 B

    Args:
        request: 包含 scores 和 student_id 的请求体
        background_tasks: FastAPI 后台任务管理器
        openai_client: 全局 OpenAI 客户端
        http_client: 全局 HTTP 客户端

    Returns:
        ReportResponse: 包含 trace_id 的响应
    """
    # 生成唯一追踪 ID
    trace_id = str(uuid4())

    # 绑定 trace_id 到日志上下文
    logger.bind(trace_id=trace_id).info(
        f"收到报告生成请求，学员 ID: {request.student_id}, "
        f"分数维度: {list(request.scores.keys())}, "
        f"分数值: {request.scores}"
    )

    # 创建服务实例
    service = ReportService(
        openai_client=openai_client,
        http_client=http_client,
    )

    # 将任务加入后台队列
    background_tasks.add_task(
        service.generate_and_callback,
        scores=request.scores,
        student_id=request.student_id,
        trace_id=trace_id,
    )

    logger.bind(trace_id=trace_id).info("报告生成任务已加入后台队列")

    # 立即返回 202 Accepted
    return ReportResponse(trace_id=trace_id, message="报告生成任务已提交，正在后台处理")
