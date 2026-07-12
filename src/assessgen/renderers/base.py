"""渲染器抽象基类。"""
from abc import ABC, abstractmethod
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from assessgen.presets.loader import PresetConfig


class BaseRenderer(ABC):
    """所有渲染器的基类。"""

    @abstractmethod
    def render(
        self,
        content: dict,
        config: "PresetConfig",
        preset_dir: Path,
        output_path: Path,
    ) -> Path:
        """
        从 preset 渲染文档。

        Args:
            content: 已解析的 JSON 数据（已清洗）
            config: 预设配置
            preset_dir: 预设目录路径（用于定位模板文件）
            output_path: 输出文件路径

        Returns:
            生成的文件路径
        """
        ...

    def render_with_template(
        self,
        content: dict,
        template_path: Path,
        output_path: Path,
    ) -> Path:
        """
        使用自定义模板渲染（无 preset 场景的 fallback）。
        默认实现不做任何事，子类按需覆盖。
        """
        raise NotImplementedError(f"{self.__class__.__name__} 不支持 render_with_template")
