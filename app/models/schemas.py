"""
数据模型定义
使用 Pydantic v2 进行请求/响应验证
"""

from typing import Dict, Literal
from pydantic import BaseModel, Field


class ReportRequest(BaseModel):
    """前端 A 的报告生成请求"""

    scores: Dict[str, float] = Field(
        description="多维度分数字典，如 {'creativity': 85.0, 'completeness': 90.0}",
        examples=[{"creativity": 85.0, "completeness": 90.0, "accuracy": 88.5}],
    )
    student_id: str = Field(
        min_length=1,
        max_length=100,
        description="学员唯一标识符",
        examples=["STU20260105001"],
    )
    template_type: Literal["template_a", "template_b"] = Field(
        default="template_a",
        description="模板类型：template_a(通用项目评估) 或 template_b(技能专项评估)",
        examples=["template_a"],
    )

    class Config:
        json_schema_extra = {
            "example": {
                "scores": {
                    "creativity": 85.0,
                    "completeness": 90.0,
                    "accuracy": 88.5,
                    "collaboration": 92.0,
                },
                "student_id": "STU20260105001",
                "template_type": "template_a",
            }
        }


class ReportResponse(BaseModel):
    """立即返回的 202 响应"""

    trace_id: str = Field(
        description="任务追踪 ID，用于日志查询和问题定位",
        examples=["a1b2c3d4-e5f6-7890-abcd-ef1234567890"],
    )
    message: str = Field(
        default="报告生成任务已提交，正在后台处理", description="响应消息"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "trace_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
                "message": "报告生成任务已提交，正在后台处理",
            }
        }


class BackendBCallback(BaseModel):
    """回调给后端 B 的数据"""

    student_id: str = Field(description="学员 ID", examples=["STU20260105001"])
    report: str = Field(
        description="vLLM 生成的评估报告内容",
        examples=["该学员在本次项目中表现优异..."],
    )
    status: str = Field(
        default="success",
        description="任务状态：success 或 failed",
        pattern="^(success|failed)$",
    )
    trace_id: str = Field(
        description="任务追踪 ID，便于后端 B 关联日志",
        examples=["a1b2c3d4-e5f6-7890-abcd-ef1234567890"],
    )

    class Config:
        json_schema_extra = {
            "example": {
                "student_id": "STU20260105001",
                "report": "该学员在本次项目中表现优异，创造力和完成度均达到优秀水平...",
                "status": "success",
                "trace_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
            }
        }
