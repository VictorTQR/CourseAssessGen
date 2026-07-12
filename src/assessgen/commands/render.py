"""render 命令实现。"""
from pathlib import Path
from typing import Optional

import typer
from loguru import logger

from assessgen.presets.loader import load_preset, get_preset_dir
from assessgen.renderers import get_renderer
from assessgen.utils.io import read_json


def render_cmd(
    content_path: Path = typer.Argument(help="教案/授课计划 JSON 文件路径"),
    preset: Optional[str] = typer.Option(None, "--preset", "-p", help="预设名称"),
    template: Optional[Path] = typer.Option(None, "--template", "-t", help="自定义模板文件路径（跳过 preset）"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="输出文件路径"),
    doc_type: Optional[str] = typer.Option(None, "--doc-type", help="文档类型（lesson-plan / schedule）"),
    engine: Optional[str] = typer.Option(None, "--engine", help="渲染引擎"),
):
    """渲染教学文档。--preset 或 --template 二选一。"""
    if not preset and not template:
        typer.echo("错误: 必须指定 --preset 或 --template", err=True)
        raise typer.Exit(1)

    # 加载 JSON 数据（不在此处 sanitize，由渲染器按需处理）
    content = _load_content(content_path)
    if content is None:
        raise typer.Exit(1)

    if preset:
        # 通过 preset 加载
        try:
            config = load_preset(preset)
        except FileNotFoundError as e:
            typer.echo(f"错误: {e}", err=True)
            raise typer.Exit(1)

        preset_dir = get_preset_dir(preset)

        # CLI 参数覆盖 preset 配置
        if doc_type:
            config.doc_type = doc_type
        if engine:
            config.engine = engine

        # 确定输出路径
        if not output:
            suffix = ".docx" if config.doc_type == "lesson-plan" else ".xlsx"
            output = content_path.with_suffix(suffix)

        # 获取渲染器并渲染
        renderer = get_renderer(config.engine)
        try:
            result = renderer.render(content, config, preset_dir, output)
        except Exception as e:
            typer.echo(f"渲染失败: {e}", err=True)
            raise typer.Exit(1)
    else:
        # 自定义模板（无 preset）
        if not template.exists():
            typer.echo(f"错误: 模板文件不存在: {template}", err=True)
            raise typer.Exit(1)

        if not output:
            output = content_path.with_suffix(".docx")

        resolved_engine = engine or "docxtpl"
        renderer = get_renderer(resolved_engine)
        try:
            result = renderer.render_with_template(content, template, output)
        except Exception as e:
            typer.echo(f"渲染失败: {e}", err=True)
            raise typer.Exit(1)

    logger.success(f"文档生成成功: {result}")


def _load_content(path: Path) -> dict | None:
    """加载 JSON 内容（清洗工作交由渲染器执行）。"""
    if not path.exists():
        typer.echo(f"错误: JSON 文件不存在: {path}", err=True)
        return None

    try:
        return read_json(path)
    except Exception as e:
        typer.echo(f"错误: JSON 解析失败: {e}", err=True)
        return None
