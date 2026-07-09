"""CLI 入口点。"""
from dotenv import load_dotenv
from loguru import logger
import typer

load_dotenv()

from assessgen.commands.render import render_cmd
from assessgen.commands.validate import validate_cmd
from assessgen.commands.exercise import exercise_cmd
from assessgen.commands.import_cmd import import_cmd
from assessgen.commands.code import code_cmd
from assessgen.presets.loader import list_presets, show_preset

app = typer.Typer(
    name="cagen",
    help="学生代码评估工具 - AI 时代的理解度验证器",
    no_args_is_help=True,
)
app.command("render")(render_cmd)
app.command("validate")(validate_cmd)
app.command("exercise")(exercise_cmd)
app.command("import")(import_cmd)
app.command("code")(code_cmd)


@app.command("list-presets")
def list_presets_cmd():
    """列出所有可用预设。"""
    presets = list_presets()
    if not presets:
        logger.info("没有可用预设")
        return
    typer.echo(f"{'预设名':<25} {'类型':<15} {'引擎':<15} 描述")
    typer.echo("-" * 70)
    for p in presets:
        typer.echo(f"{p.name:<25} {p.doc_type:<15} {p.engine:<15} {p.description}")


@app.command("show")
def show_cmd(
    name: str = typer.Argument(help="预设名称"),
):
    """显示预设详情。"""
    info = show_preset(name)
    if not info:
        logger.error(f"预设不存在: {name}")
        raise typer.Exit(1)
    typer.echo(f"名称: {info['name']}")
    typer.echo(f"描述: {info['description']}")
    typer.echo(f"文档类型: {info['doc_type']}")
    typer.echo(f"渲染引擎: {info['engine']}")
    typer.echo(f"模板文件: {info['template_file'] or '无'}")
    typer.echo(f"示例文件: {info['example_file'] or '无'}")
    if info["required_fields"]:
        typer.echo("必填字段:")
        for field in info["required_fields"]:
            typer.echo(f"  - {field}")
    if info.get("generate_rules"):
        typer.echo("生成规则 (generate_rules):")
        typer.echo(f"  {info['generate_rules']}")


if __name__ == "__main__":
    app()
