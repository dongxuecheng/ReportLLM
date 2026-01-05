"""
报告生成业务逻辑服务
负责完整的报告生成和回调流程
"""

from pathlib import Path
from typing import Dict

import httpx
import yaml
from jinja2 import Template
from loguru import logger
from openai import AsyncOpenAI

from app.core.config import settings
from app.models.schemas import BackendBCallback


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

    def _load_prompt_template(self) -> Dict[str, str]:
        """
        加载 YAML 中的 Prompt 模板

        Returns:
            包含 system_prompt 和 user_prompt 的字典
        """
        try:
            with open(self.template_path, "r", encoding="utf-8") as f:
                templates = yaml.safe_load(f)
            return templates["report_generation"]
        except Exception as e:
            logger.error(f"加载 Prompt 模板失败: {e}")
            raise

    def _render_prompt(self, scores: Dict[str, float]) -> tuple[str, str]:
        """
        使用 Jinja2 渲染 Prompt

        Args:
            scores: 多维度分数字典

        Returns:
            (system_prompt, user_prompt) 元组
        """
        template_data = self._load_prompt_template()

        # 渲染 system prompt（通常不需要变量）
        system_prompt = template_data["system_prompt"].strip()

        # 渲染 user prompt（传入 scores）
        user_template = Template(template_data["user_prompt"])
        user_prompt = user_template.render(scores=scores).strip()

        return system_prompt, user_prompt

    async def _generate_report_from_vllm(
        self,
        scores: Dict[str, float],
        trace_id: str,
    ) -> str:
        """
        调用 vLLM 生成报告

        Args:
            scores: 多维度分数字典
            trace_id: 追踪 ID

        Returns:
            生成的报告文本
        """
        logger.bind(trace_id=trace_id).info(
            f"开始渲染 Prompt，分数维度: {list(scores.keys())}"
        )
        system_prompt, user_prompt = self._render_prompt(scores)

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
        scores: Dict[str, float],
        student_id: str,
        trace_id: str,
    ) -> None:
        """
        完整的报告生成和回调流程（异步后台任务）

        Args:
            scores: 多维度分数字典
            student_id: 学员 ID
            trace_id: 追踪 ID
        """
        logger.bind(trace_id=trace_id).info(
            f"开始处理报告生成任务，学员 ID: {student_id}, " f"分数维度: {len(scores)}"
        )

        try:
            # 步骤 1: 调用 vLLM 生成报告
            report = await self._generate_report_from_vllm(scores, trace_id)

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
