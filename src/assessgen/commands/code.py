"""cagen code 命令 - CLI 薄壳。"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from loguru import logger
import typer

from assessgen.assessment.runner import run_assessment
from assessgen.llm import resolve_llm_config

# code 命令默认温度低于 llm.py 的 0.7：结构化 JSON 需更低温度
_DEFAULT_CODE_TEMPERATURE = 0.5


def code_cmd(
    path: Path = typer.Argument(exists=True, help="学生代码路径（文件或目录）"),
    context: Optional[str] = typer.Option(
        None, "--context", "-c", help="背景信息文本"
    ),
    output: Optional[Path] = typer.Option(
        None, "--output", "-o", help="输出 MD 文件路径"
    ),
    api_key: Optional[str] = typer.Option(
        None, "--api-key", help="覆盖 OPENAI_API_KEY"
    ),
    base_url: Optional[str] = typer.Option(
        None, "--api-base", help="覆盖 OPENAI_BASE_URL"
    ),
    model: Optional[str] = typer.Option(
        None, "--model", help="覆盖 ASSESSGEN_MODEL"
    ),
    temperature: Optional[float] = typer.Option(
        None, "--temperature", help="生成温度（默认 0.5）"
    ),
):
    """分析学生代码，生成分层答辩问题 + 诊断报告（MD）。"""
    resolved_temp = temperature if temperature is not None else _DEFAULT_CODE_TEMPERATURE
    try:
        config = resolve_llm_config(api_key, base_url, model, resolved_temp)
    except ValueError as e:
        logger.error(str(e))
        raise typer.Exit(1)

    try:
        result = run_assessment(str(path), context, config)
    except ValueError as e:
        logger.error(f"评估失败: {e}")
        raise typer.Exit(1)

    if output:
        output.write_text(result.markdown, encoding="utf-8")
        logger.info(f"报告已写入: {output}")
    else:
        typer.echo(result.markdown)
