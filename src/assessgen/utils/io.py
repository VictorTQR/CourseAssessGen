"""文件读写工具。"""
import json
from pathlib import Path
from typing import Any


def read_text(path: Path) -> str:
    """读取文本文件，utf-8（含 BOM）优先，回退 gbk。

    兼容 Windows 中文环境下记事本/WPS 保存的 GBK 编码讲稿。
    """
    try:
        return path.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError:
        return path.read_text(encoding="gbk", errors="replace")


def read_json(path: Path) -> dict:
    """读取 JSON 文件，返回 dict。"""
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(data: Any, path: Path, indent: int = 2) -> Path:
    """写入 JSON 文件。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=indent), encoding="utf-8")
    return path
