"""
数据模型定义
使用 Pydantic v2 进行请求/响应验证
"""

from typing import Dict
from pydantic import BaseModel, Field, model_validator


class ReportRequestA(BaseModel):
    """模板 A：项目评估请求"""

    student_id: str = Field(
        min_length=1,
        max_length=100,
        description="学员唯一标识符",
        examples=["STU20260105001"],
    )
    scores: Dict[str, float] = Field(
        description="多维度分数字典，如 {'creativity': 85.0, 'completeness': 90.0}",
        examples=[{"creativity": 85.0, "completeness": 90.0, "accuracy": 88.5}],
    )

    class Config:
        json_schema_extra = {
            "example": {
                "student_id": "STU20260105001",
                "scores": {
                    "creativity": 85.0,
                    "completeness": 90.0,
                    "accuracy": 88.5,
                    "collaboration": 92.0,
                },
            }
        }


class QuestionStat(BaseModel):
    """题目统计信息"""

    total: int = Field(ge=0, description="该题型的总题数")
    correct: int = Field(ge=0, description="答对的题数")

    @model_validator(mode="after")
    def validate_correct_not_exceed_total(self):
        """验证答对数不超过总题数"""
        if self.correct > self.total:
            raise ValueError(f"答对数({self.correct})不能超过总题数({self.total})")
        return self


class ReportRequestB(BaseModel):
    """模板 B：题目统计请求"""

    student_id: str = Field(
        min_length=1,
        max_length=100,
        description="学员唯一标识符",
        examples=["STU20260105001"],
    )
    question_stats: Dict[str, QuestionStat] = Field(
        description="题目类型统计字典，key为题型名称，value为统计信息",
        examples=[
            {
                "选择题": {"total": 10, "correct": 8},
                "判断题": {"total": 5, "correct": 4},
            }
        ],
    )

    class Config:
        json_schema_extra = {
            "example": {
                "student_id": "STU20260105001",
                "question_stats": {
                    "选择题": {"total": 10, "correct": 8},
                    "判断题": {"total": 5, "correct": 4},
                    "简答题": {"total": 3, "correct": 2},
                },
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
