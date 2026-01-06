"""
报告生成 API 路由
处理前端 A 的请求，触发后台任务
"""

from typing import Literal, Union
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, Body, Depends, Query, status
from loguru import logger
import httpx
from openai import AsyncOpenAI

from app.core.dependencies import get_http_client, get_openai_client
from app.models.schemas import (
    ReportRequestA,
    ReportRequestB,
    ReportResponse,
    QuestionStat,
)
from app.services.report_service import ReportService


router = APIRouter()


@router.post(
    "/generate-report",
    response_model=ReportResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="生成学员评估报告",
    description="接收学员的评估数据，异步生成评估报告并回调后端 B",
)
async def generate_report(
    background_tasks: BackgroundTasks,
    body: dict = Body(
        ...,
        openapi_examples={
            "template_a_example": {
                "summary": "模板 A - 项目评估",
                "description": "使用 template_a 模板，传入多维度分数进行项目评估",
                "value": {
                    "student_id": "STU20260106001",
                    "scores": {
                        "creativity": 85.0,
                        "completeness": 90.0,
                        "accuracy": 88.5,
                        "collaboration": 92.0,
                    },
                },
            },
            "template_b_example": {
                "summary": "模板 B - 题目统计",
                "description": "使用 template_b 模板，传入题目答题统计数据",
                "value": {
                    "student_id": "STU20260106002",
                    "question_stats": {
                        "选择题": {"total": 10, "correct": 8},
                        "判断题": {"total": 5, "correct": 4},
                        "简答题": {"total": 3, "correct": 2},
                    },
                },
            },
        },
    ),
    template_type: Literal["template_a", "template_b"] = Query(
        default="template_a",
        description="模板类型：template_a(项目评估，传入scores) 或 template_b(题目统计，传入question_stats)",
    ),
    openai_client: AsyncOpenAI = Depends(get_openai_client),
    http_client: httpx.AsyncClient = Depends(get_http_client),
) -> ReportResponse:
    """
    生成报告端点

    工作流程:
    1. 根据 template_type 查询参数解析对应的请求体
    2. 生成 trace_id 用于全链路追踪
    3. 将报告生成任务加入后台队列
    4. 立即返回 202 Accepted 和 trace_id
    5. 后台任务: 渲染 Prompt -> 调用 vLLM -> 回调后端 B

    Args:
        template_type: 模板类型（查询参数）
        body: 请求体，根据 template_type 解析为不同模型
        background_tasks: FastAPI 后台任务管理器
        openai_client: 全局 OpenAI 客户端
        http_client: 全局 HTTP 客户端

    Returns:
        ReportResponse: 包含 trace_id 的响应
    """
    # 根据模板类型解析请求体
    if template_type == "template_a":
        request = ReportRequestA(**body)
        data_info = f"分数维度: {list(request.scores.keys())}, 分数值: {request.scores}"
    else:  # template_b
        request = ReportRequestB(**body)
        stats_summary = {
            k: f"{v.correct}/{v.total}" for k, v in request.question_stats.items()
        }
        data_info = f"题目统计: {stats_summary}"

    # 生成唯一追踪 ID
    trace_id = str(uuid4())

    # 绑定 trace_id 到日志上下文
    logger.bind(trace_id=trace_id).info(
        f"收到报告生成请求，学员 ID: {request.student_id}, "
        f"模板类型: {template_type}, {data_info}"
    )

    # 创建服务实例
    service = ReportService(
        openai_client=openai_client,
        http_client=http_client,
    )

    # 将任务加入后台队列
    if template_type == "template_a":
        background_tasks.add_task(
            service.generate_and_callback,
            student_id=request.student_id,
            trace_id=trace_id,
            template_type=template_type,
            scores=request.scores,
        )
    else:  # template_b
        background_tasks.add_task(
            service.generate_and_callback,
            student_id=request.student_id,
            trace_id=trace_id,
            template_type=template_type,
            question_stats=request.question_stats,
        )

    logger.bind(trace_id=trace_id).info("报告生成任务已加入后台队列")

    # 立即返回 202 Accepted
    return ReportResponse(trace_id=trace_id, message="报告生成任务已提交，正在后台处理")
