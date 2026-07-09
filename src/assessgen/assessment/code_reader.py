"""代码聚合器 - 把学生代码路径聚合成带行号、可截断的文本。"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from loguru import logger

MAX_LINES_PER_FILE = 800

# 包含的代码扩展名
_CODE_EXTENSIONS = frozenset({
    ".html", ".css", ".js", ".jsx", ".ts", ".tsx", ".vue", ".py",
})

# 排除的目录名
_EXCLUDED_DIRS = frozenset({
    "node_modules", ".venv", "venv", "__pycache__", ".git",
    "dist", "build", ".next", "target", "vendor", ".idea", ".vscode",
})

# 排除的文件名
_EXCLUDED_FILES = frozenset({
    "package-lock.json", "yarn.lock", "pnpm-lock.yaml", "uv.lock",
})


@dataclass(frozen=True)
class FileMeta:
    """单个文件的元信息。"""
    path: str
    lines: int
    truncated: bool


@dataclass(frozen=True)
class CodeAggregation:
    """聚合后的代码文本 + 文件元信息。"""
    text: str
    files: list[FileMeta]


def _is_excluded_file(path: Path) -> bool:
    """判断文件是否应被排除。"""
    if path.name.startswith("."):
        return True
    if path.name in _EXCLUDED_FILES:
        return True
    if path.name.endswith(".min.js") or path.name.endswith(".min.css"):
        return True
    return False


def _read_single_file(path: Path) -> tuple[FileMeta, str] | None:
    """读取单个文件，返回元信息和带行号文本；二进制/读取失败返回 None。"""
    try:
        content = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        logger.warning(f"跳过二进制文件: {path}")
        return None
    except OSError as e:
        logger.warning(f"读取失败 {path}: {e}")
        return None

    all_lines = content.splitlines()
    total_lines = len(all_lines)
    truncated = total_lines > MAX_LINES_PER_FILE
    shown = all_lines[:MAX_LINES_PER_FILE]

    numbered = "\n".join(f"{i + 1:>4}: {line}" for i, line in enumerate(shown))
    if truncated:
        numbered += f"\n... (已截断 {total_lines - MAX_LINES_PER_FILE} 行)"

    # 始终用文件名；目录遍历时会用 relative_to 覆盖
    meta = FileMeta(path=path.name, lines=total_lines, truncated=truncated)
    return meta, numbered


def _collect_code_files(root: Path) -> list[Path]:
    """递归收集所有代码文件（已排序、已排除）。"""
    files: list[Path] = []
    for path in sorted(root.rglob("*")):
        if path.is_dir():
            continue
        # 检查是否在排除目录内
        if any(part in _EXCLUDED_DIRS for part in path.parts):
            continue
        if _is_excluded_file(path):
            continue
        if path.suffix.lower() in _CODE_EXTENSIONS:
            files.append(path)
    return files


def read_code(path: str) -> CodeAggregation:
    """读取代码路径（文件或目录），返回聚合结果。

    Raises:
        ValueError: 路径不存在或没有可识别的代码文件
    """
    root = Path(path)
    if not root.exists():
        raise ValueError(f"路径不存在: {path}")

    # 单文件输入：跳过扩展名/排除规则
    if root.is_file():
        result = _read_single_file(root)
        if result is None:
            raise ValueError(f"无法读取文件: {path}")
        meta, numbered = result
        header = f"=== {meta.path} ({meta.lines} 行) ==="
        if meta.truncated:
            header = f"=== {meta.path} ({meta.lines} 行, 截断展示前 {MAX_LINES_PER_FILE} 行) ==="
        text = f"{header}\n{numbered}\n"
        return CodeAggregation(text=text, files=[meta])

    # 目录输入：收集 + 聚合
    code_files = _collect_code_files(root)
    if not code_files:
        raise ValueError(f"路径下没有可识别的代码文件: {path}")

    metas: list[FileMeta] = []
    blocks: list[str] = []
    for f in code_files:
        result = _read_single_file(f)
        if result is None:
            continue
        meta, numbered = result
        # 相对路径（覆盖 _read_single_file 的 path.name）
        try:
            rel = f.relative_to(root)
            meta = FileMeta(
                path=str(rel).replace("\\", "/"),
                lines=meta.lines,
                truncated=meta.truncated,
            )
        except ValueError:
            pass
        metas.append(meta)
        header = f"=== {meta.path} ({meta.lines} 行) ==="
        if meta.truncated:
            header = f"=== {meta.path} ({meta.lines} 行, 截断展示前 {MAX_LINES_PER_FILE} 行) ==="
        blocks.append(f"{header}\n{numbered}\n")

    if not metas:
        raise ValueError(f"路径下没有可识别的代码文件: {path}")

    return CodeAggregation(text="\n".join(blocks), files=metas)
