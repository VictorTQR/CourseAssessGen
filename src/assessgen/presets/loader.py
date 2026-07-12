"""预设加载器。"""
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field
from loguru import logger

# 默认预设目录：项目根目录下的 presets/
DEFAULT_PRESETS_DIR = Path(__file__).resolve().parent.parent.parent.parent / "presets"


class PresetConfig(BaseModel):
    """预设配置模型 — 整个项目中唯一固定的 Pydantic model。"""

    name: str
    description: str = ""
    doc_type: str  # "lesson-plan" / "schedule" / "exercise-import"
    engine: str = "docxtpl"
    template_file: Optional[str] = None  # docxtpl / docxtemplater 需要
    example_file: Optional[str] = None  # 校验参考 + AI 生成参考
    required_fields: list[str] = Field(default_factory=list)
    generate_rules: Optional[str] = None  # 生成约束规则（可选，注入 generate/exercise prompt）
    style_rules: Optional[dict] = None  # schedule 专用：表格结构定义
    format_spec: Optional[dict] = None  # exercise-import 专用：平台导入格式映射


def _find_presets_dir() -> Path:
    """查找预设目录（优先当前工作目录，其次项目内置）。"""
    # 当前工作目录下找
    cwd_presets = Path.cwd() / "presets"
    if cwd_presets.exists():
        return cwd_presets
    return DEFAULT_PRESETS_DIR


def load_preset(name: str, presets_dir: Optional[Path] = None) -> PresetConfig:
    """加载预设配置。"""
    presets_dir = presets_dir or _find_presets_dir()
    preset_dir = presets_dir / name
    config_path = preset_dir / "config.json"

    if not config_path.exists():
        raise FileNotFoundError(f"预设不存在: {name}（未找到 {config_path}）")

    import json

    data = json.loads(config_path.read_text(encoding="utf-8"))
    config = PresetConfig(**data)
    logger.debug(f"加载预设: {name}")
    return config


def list_presets(presets_dir: Optional[Path] = None) -> list[PresetConfig]:
    """列出所有预设。"""
    presets_dir = presets_dir or _find_presets_dir()
    if not presets_dir.exists():
        return []

    presets = []
    for child in sorted(presets_dir.iterdir()):
        if child.is_dir() and (child / "config.json").exists():
            try:
                presets.append(load_preset(child.name, presets_dir))
            except Exception as e:
                logger.warning(f"跳过无效预设 {child.name}: {e}")
    return presets


def get_preset_dir(name: str, presets_dir: Optional[Path] = None) -> Path:
    """获取预设目录路径。"""
    presets_dir = presets_dir or _find_presets_dir()
    preset_dir = presets_dir / name
    if not preset_dir.exists():
        raise FileNotFoundError(f"预设目录不存在: {preset_dir}")
    return preset_dir


def show_preset(name: str, presets_dir: Optional[Path] = None) -> dict | None:
    """返回预设的可展示信息字典，不存在返回 None。"""
    presets_dir = presets_dir or _find_presets_dir()
    preset_dir = presets_dir / name
    config_path = preset_dir / "config.json"
    if not config_path.exists():
        return None

    try:
        config = load_preset(name, presets_dir)
        return config.model_dump()
    except Exception:
        return None
