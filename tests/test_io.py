"""read_text 编码回退测试 — 覆盖 utf-8 / utf-8 BOM / gbk。"""
from pathlib import Path

from assessgen.utils.io import read_text

_SAMPLE = "第6周：Vue Router 与 Pinia 状态管理\n"


def test_read_text_utf8(tmp_path: Path):
    p = tmp_path / "lecture.txt"
    p.write_text(_SAMPLE, encoding="utf-8")
    assert read_text(p) == _SAMPLE


def test_read_text_utf8_bom(tmp_path: Path):
    p = tmp_path / "lecture.txt"
    p.write_text(_SAMPLE, encoding="utf-8-sig")
    # BOM 应被剥离，不残留 \ufeff
    assert read_text(p) == _SAMPLE


def test_read_text_gbk_fallback(tmp_path: Path):
    p = tmp_path / "lecture.txt"
    p.write_text(_SAMPLE, encoding="gbk")
    assert read_text(p) == _SAMPLE
