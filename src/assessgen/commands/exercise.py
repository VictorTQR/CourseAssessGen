"""exercise 命令实现 — 教案 JSON / 授课讲稿 txt → LLM → exercises.json（习题）。

出题素材支持两种形态：
- 教案 JSON（generate 的产物）：结构化，含教学目标、重难点、教学环节
- 授课讲稿 txt/md：教师口头授课内容的文本

两种素材都送 LLM 出题，讲稿模式让教师不写教案也能直接出题。
"""
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import typer
from loguru import logger

from assessgen.llm import build_exercise_prompt, call_llm, resolve_llm_config
from assessgen.presets.loader import get_preset_dir, load_preset
from assessgen.utils.io import read_json, read_text, write_json

_TEXT_SUFFIXES = {".txt", ".md"}

# 讲稿模式的 system prompt 素材描述（与教案 JSON 默认值对应）
_LECTURE_DESC = "授课讲稿"
_LECTURE_HINT = (
    "讲稿是教师的授课内容文本，包含知识讲解、示例与强调的重点，"
    "出题应覆盖其中的知识点，题目内容要贴合教学实际。"
)


@dataclass(frozen=True)
class Material:
    """出题素材：desc 用于 system prompt 措辞，user_text 是嵌入 user prompt 的素材段。"""

    desc: str
    hint: str
    user_text: str


def load_material(path: Path) -> Material:
    """读取出题素材（.json 教案 或 .txt/.md 讲稿）。

    Raises:
        ValueError: 文件为空、JSON 非法或后缀不受支持时
    """
    suffix = path.suffix.lower()

    if suffix == ".json":
        try:
            content = read_json(path)
        except json.JSONDecodeError as e:
            raise ValueError(f"教案 JSON 解析失败: {path}\n{e}") from e
        user_text = "以下是本节课的教案 JSON，请据此生成习题：\n\n" + json.dumps(
            content, ensure_ascii=False, indent=2
        )
        return Material(
            desc="教案 JSON",
            hint="教案包含教学目标、重难点、教学环节等信息，出题应覆盖这些知识点，题目内容要贴合教学实际。",
            user_text=user_text,
        )

    if suffix in _TEXT_SUFFIXES:
        text = read_text(path).strip()
        if not text:
            raise ValueError(f"讲稿文件为空: {path}")
        user_text = f"以下是本节课的授课讲稿，请据此生成习题：\n\n{text}"
        return Material(desc=_LECTURE_DESC, hint=_LECTURE_HINT, user_text=user_text)

    raise ValueError(
        f"不支持的文件类型: '{suffix or path.name}'。"
        f"支持 .json（教案）、{'/'.join(sorted(_TEXT_SUFFIXES))}（授课讲稿）。"
    )


def exercise_cmd(
    content_path: Path = typer.Argument(
        help="出题素材：教案 JSON 或授课讲稿 txt/md 文件路径"
    ),
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
    """根据教案 JSON 或授课讲稿，通过 LLM 生成配套习题（exercises.json）。"""
    # 1. 读取出题素材
    if not content_path.exists():
        typer.echo(f"错误: 素材文件不存在: {content_path}", err=True)
        raise typer.Exit(1)
    try:
        material = load_material(content_path)
    except ValueError as e:
        typer.echo(f"错误: {e}", err=True)
        raise typer.Exit(1)

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
        example,
        generate_rules=config.generate_rules,
        instructions=instructions,
        material_desc=material.desc,
        material_hint=material.hint,
    )
    user_text = material.user_text

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
