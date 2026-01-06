"""
报告生成业务逻辑服务
负责完整的报告生成和回调流程
"""

from pathlib import Path
from typing import Dict, Optional

import httpx
import yaml
from jinja2 import Template
from loguru import logger
from openai import AsyncOpenAI

from app.core.config import settings
from app.models.schemas import BackendBCallback, QuestionStat


class ReportService:
    """报告生成服务类"""

    def __init__(
        self,
        openai_client: AsyncOpenAI,
        http_client: httpx.AsyncClient,
    ):
        """
        初始化服务

        Args:
            openai_client: OpenAI 客户端（连接 vLLM）
            http_client: HTTP 客户端（调用后端 B）
        """
        self.openai_client = openai_client
        self.http_client = http_client
        self.template_path = Path("config/templates.yaml")

    def _load_prompt_template(
        self, template_type: str = "template_a"
    ) -> Dict[str, str]:
        """
        加载 YAML 中的 Prompt 模板

        Args:
            template_type: 模板类型，可选 template_a 或 template_b

        Returns:
            包含 system_prompt 和 user_prompt 的字典
        """
        try:
            with open(self.template_path, "r", encoding="utf-8") as f:
                templates = yaml.safe_load(f)
            if template_type not in templates:
                logger.error(f"模板类型 {template_type} 不存在，回退到 template_a")
                template_type = "template_a"
            return templates[template_type]
        except Exception as e:
            logger.error(f"加载 Prompt 模板失败: {e}")
            raise

    def _render_prompt(
        self,
        template_type: str = "template_a",
        scores: Optional[Dict[str, float]] = None,
        question_stats: Optional[Dict[str, QuestionStat]] = None,
    ) -> tuple[str, str]:
        """
        使用 Jinja2 渲染 Prompt

        Args:
            template_type: 模板类型
            scores: 多维度分数字典（template_a 使用）
            question_stats: 题目统计字典（template_b 使用）

        Returns:
            (system_prompt, user_prompt) 元组
        """
        template_data = self._load_prompt_template(template_type)

        # 渲染 system prompt（通常不需要变量）
        system_prompt = template_data["system_prompt"].strip()

        # 渲染 user prompt
        user_template = Template(template_data["user_prompt"])

        if template_type == "template_a":
            user_prompt = user_template.render(scores=scores).strip()
        else:  # template_b
            # 计算正确率并构造渲染数据
            stats_with_rate = {}
            for q_type, stat in question_stats.items():
                stats_with_rate[q_type] = {
                    "total": stat.total,
                    "correct": stat.correct,
                    "rate": (
                        round(stat.correct / stat.total * 100, 1)
                        if stat.total > 0
                        else 0
                    ),
                }
            user_prompt = user_template.render(question_stats=stats_with_rate).strip()

        return system_prompt, user_prompt

    async def _generate_report_from_vllm(
        self,
        trace_id: str,
        template_type: str = "template_a",
        scores: Optional[Dict[str, float]] = None,
        question_stats: Optional[Dict[str, QuestionStat]] = None,
    ) -> str:
        """
        调用 vLLM 生成报告

        Args:
            trace_id: 追踪 ID
            template_type: 模板类型
            scores: 多维度分数字典（template_a 使用）
            question_stats: 题目统计字典（template_b 使用）

        Returns:
            生成的报告文本
        """
        if template_type == "template_a":
            data_info = f"分数维度: {list(scores.keys())}"
        else:
            data_info = f"题目类型: {list(question_stats.keys())}"

        logger.bind(trace_id=trace_id).info(
            f"开始渲染 Prompt，{data_info}，模板类型: {template_type}"
        )
        system_prompt, user_prompt = self._render_prompt(
            template_type=template_type, scores=scores, question_stats=question_stats
        )

        logger.bind(trace_id=trace_id).info(
            f"调用 vLLM 生成报告，模型: {settings.vllm_model_name}, "
            f"max_tokens: {settings.vllm_max_tokens}, "
            f"temperature: {settings.vllm_temperature}"
        )

        try:
            response = await self.openai_client.chat.completions.create(
                model=settings.vllm_model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                max_tokens=settings.vllm_max_tokens,
                temperature=settings.vllm_temperature,
                stream=False,
            )

            report = response.choices[0].message.content.strip()
            logger.bind(trace_id=trace_id).info(
                f"vLLM 报告生成成功，长度: {len(report)} 字符"
            )
            logger.bind(trace_id=trace_id).info(f"生成的报告内容:\n{report}")
            return report

        except Exception as e:
            logger.bind(trace_id=trace_id).error(f"vLLM 调用失败: {e}", exc_info=True)
            raise

    async def _callback_to_backend_b(
        self,
        callback_data: BackendBCallback,
        trace_id: str,
    ) -> None:
        """
        回调后端 B 推送报告

        Args:
            callback_data: 回调数据
            trace_id: 追踪 ID
        """
        logger.bind(trace_id=trace_id).info(
            f"准备回调后端 B: {settings.backend_b_callback_url}, "
            f"学员 ID: {callback_data.student_id}, "
            f"状态: {callback_data.status}"
        )

        try:
            response = await self.http_client.post(
                settings.backend_b_callback_url,
                json=callback_data.model_dump(),
                headers={
                    "Content-Type": "application/json",
                    "X-Trace-ID": trace_id,
                },
            )
            response.raise_for_status()

            logger.bind(trace_id=trace_id).info(
                f"后端 B 回调成功，HTTP 状态: {response.status_code}"
            )

        except httpx.HTTPStatusError as e:
            logger.bind(trace_id=trace_id).error(
                f"后端 B 回调失败，HTTP 状态: {e.response.status_code}, "
                f"响应内容: {e.response.text}",
                exc_info=True,
            )
        except httpx.RequestError as e:
            logger.bind(trace_id=trace_id).error(
                f"后端 B 回调网络错误: {e}", exc_info=True
            )
        except Exception as e:
            logger.bind(trace_id=trace_id).error(
                f"后端 B 回调未知错误: {e}", exc_info=True
            )

    async def generate_and_callback(
        self,
        student_id: str,
        trace_id: str,
        template_type: str = "template_a",
        scores: Optional[Dict[str, float]] = None,
        question_stats: Optional[Dict[str, QuestionStat]] = None,
    ) -> None:
        """
        完整的报告生成和回调流程（异步后台任务）

        Args:
            student_id: 学员 ID
            trace_id: 追踪 ID
            template_type: 模板类型
            scores: 多维度分数字典（template_a 使用）
            question_stats: 题目统计字典（template_b 使用）
        """
        if template_type == "template_a":
            data_count = len(scores) if scores else 0
        else:
            data_count = len(question_stats) if question_stats else 0

        logger.bind(trace_id=trace_id).info(
            f"开始处理报告生成任务，学员 ID: {student_id}, "
            f"数据项数: {data_count}，模板类型: {template_type}"
        )

        try:
            # 步骤 1: 调用 vLLM 生成报告
            report = await self._generate_report_from_vllm(
                trace_id=trace_id,
                template_type=template_type,
                scores=scores,
                question_stats=question_stats,
            )
            report = await self._generate_report_from_vllm(
                scores, trace_id, template_type
            )

            # 步骤 2: 回调后端 B（成功状态）
            callback_data = BackendBCallback(
                student_id=student_id,
                report=report,
                status="success",
                trace_id=trace_id,
            )
            await self._callback_to_backend_b(callback_data, trace_id)

            logger.bind(trace_id=trace_id).info("报告生成和回调流程完成")

        except Exception as e:
            logger.bind(trace_id=trace_id).error(
                f"报告生成流程失败: {e}", exc_info=True
            )

            # 推送失败状态给后端 B
            try:
                failure_callback = BackendBCallback(
                    student_id=student_id,
                    report=f"报告生成失败: {str(e)}",
                    status="failed",
                    trace_id=trace_id,
                )
                await self._callback_to_backend_b(failure_callback, trace_id)
            except Exception as callback_error:
                logger.bind(trace_id=trace_id).error(
                    f"失败状态回调也失败了: {callback_error}", exc_info=True
                )
