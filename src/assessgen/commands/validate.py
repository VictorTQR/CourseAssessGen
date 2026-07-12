"""validate 命令实现。"""
from pathlib import Path
from typing import Optional

import typer
from loguru import logger

from assessgen.presets.loader import load_preset, get_preset_dir
from assessgen.schemas.validator import validate_content, validate_json_syntax
from assessgen.utils.io import read_json


def validate_cmd(
    content_path: Path = typer.Argument(help="教案/授课计划 JSON 文件路径"),
    preset: Optional[str] = typer.Option(None, "--preset", "-p", help="用指定 preset 校验"),
):
    """校验 JSON 文件的 schema 合规性。"""
    # 基本语法校验
    data, syntax_errors = validate_json_syntax(content_path)
    if syntax_errors:
        typer.secho(f"[FAIL] {content_path}", fg=typer.colors.RED)
        for err in syntax_errors:
            typer.echo(f"  {err}")
        raise typer.Exit(1)

    # 无 preset 只做语法校验
    if not preset:
        typer.secho(f"[OK] JSON 语法校验通过: {content_path}", fg=typer.colors.GREEN)
        typer.echo(f"  共 {len(data)} 个顶级键")
        return

    # 带 preset 的结构校验
    try:
        config = load_preset(preset)
    except FileNotFoundError as e:
        typer.echo(f"错误: {e}", err=True)
        raise typer.Exit(1)

    preset_dir = get_preset_dir(preset)
    example = None
    if config.example_file:
        example_path = preset_dir / config.example_file
        if example_path.exists():
            example = read_json(example_path)
        else:
            typer.secho(f"[WARN] 示例文件不存在: {example_path}", fg=typer.colors.YELLOW)

    if example:
        errors = validate_content(data, example, config.required_fields)
    else:
        # 无 example，只校验 required_fields
        from assessgen.schemas.validator import get_value_by_path
        errors = []
        for field_path in config.required_fields:
            val = get_value_by_path(data, field_path)
            if val is None:
                errors.append(f"缺少必填字段: {field_path}")

    if errors:
        typer.secho(f"[FAIL] 校验不通过: {content_path} (preset: {preset})", fg=typer.colors.RED)
        for err in errors:
            typer.echo(f"  {err}")
        raise typer.Exit(1)
    else:
        typer.secho(f"[OK] 校验通过: {content_path} (preset: {preset})", fg=typer.colors.GREEN)
