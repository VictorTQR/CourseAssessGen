"""编排层 - 串联 code_reader -> 双 LLM 调用 -> renderer。"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from loguru import logger
from pydantic import ValidationError

from assessgen.assessment.code_reader import CodeAggregation, read_code
from assessgen.assessment.models import DiagnosisReport, QuestionSet
from assessgen.assessment.prompts import Prompt, build_diagnosis_prompt, build_questions_prompt
from assessgen.assessment.renderer import ReportMeta, render_report
from assessgen.llm import LLMConfig, call_llm

_SOFT_CHAR_LIMIT = 80_000


@dataclass(frozen=True)
class AssessmentResult:
    """评估完整结果。"""
    markdown: str
    diagnosis: DiagnosisReport
    questions: QuestionSet


def _warn_if_huge(agg: CodeAggregation) -> None:
    """代码过大时软告警。"""
    if len(agg.text) > _SOFT_CHAR_LIMIT:
        logger.warning(
            f"代码聚合后 {len(agg.text)} 字符（约 {len(agg.text) // 4} tokens），"
            f"可能接近模型上下文上限，输出质量可能下降。"
        )


def _validate_or_retry(
    raw: dict,
    model_cls: type,
    config: LLMConfig,
    prompt: Prompt,
):
    """model_validate；失败重试 1 次；仍失败抛 ValueError。"""
    try:
        return model_cls.model_validate(raw)
    except ValidationError as e:
        logger.warning(f"LLM 输出 schema 校验失败，重试 1 次: {e}")
        raw2 = call_llm(prompt.system, prompt.user, config)
        try:
            return model_cls.model_validate(raw2)
        except ValidationError as e2:
            raise ValueError(
                f"LLM 两次输出均不符合 schema。最后一次错误: {e2}"
            ) from e2


def run_assessment(
    code_path: str,
    context: str | None,
    config: LLMConfig,
) -> AssessmentResult:
    """完整评估流程：读代码 -> 诊断 -> 出题 -> 渲染。"""
    # 1. 读代码
    agg = read_code(code_path)

    # 2. 软告警
    _warn_if_huge(agg)

    # 3. 调用 1：诊断
    p1 = build_diagnosis_prompt(agg, context)
    raw1 = call_llm(p1.system, p1.user, config)
    diagnosis = _validate_or_retry(raw1, DiagnosisReport, config, p1)

    # 4. 调用 2：出题
    p2 = build_questions_prompt(diagnosis, agg, context)
    raw2 = call_llm(p2.system, p2.user, config)
    questions = _validate_or_retry(raw2, QuestionSet, config, p2)

    # 5. 渲染
    meta = ReportMeta(
        code_path=code_path,
        generated_at=datetime.now().isoformat(timespec="minutes"),
        context=context,
    )
    markdown = render_report(diagnosis, questions, meta)

    return AssessmentResult(markdown=markdown, diagnosis=diagnosis, questions=questions)
