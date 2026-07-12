"""exercise 命令实现 — content.json（教案）→ LLM → exercises.json（习题）。

与 generate 的区别：
- generate: 纯文本 → LLM → content.json（教案）
- exercise: content.json（教案）→ LLM → exercises.json（习题）

教案作为出题素材，LLM 能看到教学目标、重难点、教学环节，生成更精准的习题。
"""
from pathlib import Path
from typing import Optional

import typer
from loguru import logger

from assessgen.llm import build_exercise_prompt, call_llm, resolve_llm_config
from assessgen.presets.loader import get_preset_dir, load_preset
from assessgen.utils.io import read_json, write_json


def exercise_cmd(
    content_path: Path = typer.Argument(help="教案 JSON 文件路径（generate 的产物，作为出题素材）"),
    preset: str = typer.Option(..., "--preset", "-p", help="预设名称（决定习题输出结构）"),
    instructions: Optional[str] = typer.Option(
        None,
        "--instructions",
        help="用户自定义出题指令（覆盖默认题量分布，优先级高于 preset 的 generate_rules）",
    ),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="输出 JSON 路径"),
    api_key: Optional[str] = typer.Option(None, "--api-key", help="覆盖 OPENAI_API_KEY"),
    api_base: Optional[str] = typer.Option(None, "--api-base", help="覆盖 OPENAI_BASE_URL"),
    model: Optional[str] = typer.Option(None, "--model", help="覆盖 ASSESSGEN_MODEL"),
    temperature: float = typer.Option(0.7, "--temperature", help="生成温度"),
):
    """根据教案 JSON，通过 LLM 生成配套习题（exercises.json）。"""
    # 1. 读取教案 content.json
    if not content_path.exists():
        typer.echo(f"错误: 教案文件不存在: {content_path}", err=True)
        raise typer.Exit(1)
    content = read_json(content_path)

    # 2. 加载 preset & example.json
    try:
        config = load_preset(preset)
    except FileNotFoundError as e:
        typer.echo(f"错误: {e}", err=True)
        raise typer.Exit(1)

    if not config.example_file:
        typer.echo(f"错误: preset '{preset}' 未定义 example_file，无法构建 prompt", err=True)
        raise typer.Exit(1)

    preset_dir = get_preset_dir(preset)
    example_path = preset_dir / config.example_file
    if not example_path.exists():
        typer.echo(f"错误: 示例文件不存在: {example_path}", err=True)
        raise typer.Exit(1)

    example = read_json(example_path)

    # 3. 解析 LLM 配置
    try:
        llm_config = resolve_llm_config(
            api_key=api_key,
            base_url=api_base,
            model=model,
            temperature=temperature,
        )
    except ValueError as e:
        typer.echo(f"错误: {e}", err=True)
        raise typer.Exit(1)

    # 4. 构建 prompt（题量分布由 preset 的 generate_rules 控制，--instructions 覆盖）
    system_prompt = build_exercise_prompt(
        content,
        example,
        generate_rules=config.generate_rules,
        instructions=instructions,
    )

    # user prompt 是教案 JSON 全文，让 LLM 能看到教学目标/重难点/教学环节
    import json
    user_text = "以下是本节课的教案 JSON，请据此生成习题：\n\n" + json.dumps(
        content, ensure_ascii=False, indent=2
    )

    # 5. 调用 LLM
    try:
        result = call_llm(system_prompt, user_text, llm_config)
    except Exception as e:
        typer.echo(f"LLM 调用失败: {e}", err=True)
        raise typer.Exit(1)

    # 6. 写入输出
    if output is None:
        output = Path("output") / "exercises.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    write_json(result, output)
    logger.success(f"exercises.json 生成成功: {output}")
