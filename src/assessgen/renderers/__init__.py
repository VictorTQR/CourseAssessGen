"""渲染器注册与工厂。"""
from assessgen.renderers.base import BaseRenderer
from assessgen.renderers.chaoxing_xlsx import ChaoxingXlsxRenderer

RENDERERS: dict[str, type[BaseRenderer]] = {
    "chaoxing-xlsx": ChaoxingXlsxRenderer,
}


def get_renderer(engine: str) -> BaseRenderer:
    """根据引擎名称获取渲染器实例。"""
    renderer_cls = RENDERERS.get(engine)
    if renderer_cls is None:
        available = ", ".join(sorted(RENDERERS.keys()))
        raise ValueError(f"不支持的渲染引擎: {engine}（可用: {available}）")
    return renderer_cls()


def register_renderer(engine: str, renderer_cls: type[BaseRenderer]) -> None:
    """注册新渲染器（供扩展使用）。"""
    RENDERERS[engine] = renderer_cls
