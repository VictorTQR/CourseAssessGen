"""code_reader 聚合测试。"""
import os
from pathlib import Path

import pytest

from assessgen.assessment.code_reader import (
    MAX_LINES_PER_FILE,
    CodeAggregation,
    FileMeta,
    read_code,
)


class TestReadCode:
    def test_single_file_input(self, tmp_path):
        f = tmp_path / "app.js"
        f.write_text("const a = 1\nconst b = 2\n", encoding="utf-8")
        agg = read_code(str(f))
        assert len(agg.files) == 1
        assert agg.files[0].path == "app.js"
        assert agg.files[0].lines == 2
        assert agg.files[0].truncated is False
        assert "   1: const a = 1" in agg.text

    def test_directory_traversal_sorted(self, sample_code_dir):
        agg = read_code(sample_code_dir)
        paths = [fm.path for fm in agg.files]
        assert paths == sorted(paths)
        assert "App.vue" in paths
        assert "main.js" in paths
        assert "stores/todo.js" in paths

    def test_excludes_node_modules(self, tmp_path):
        (tmp_path / "node_modules").mkdir()
        (tmp_path / "node_modules" / "dep.js").write_text("x", encoding="utf-8")
        (tmp_path / "main.js").write_text("const a = 1\n", encoding="utf-8")
        agg = read_code(str(tmp_path))
        paths = [fm.path for fm in agg.files]
        assert "main.js" in paths
        assert all("node_modules" not in p for p in paths)

    def test_excludes_lock_files(self, tmp_path):
        (tmp_path / "package-lock.json").write_text("{}", encoding="utf-8")
        (tmp_path / "main.js").write_text("const a = 1\n", encoding="utf-8")
        agg = read_code(str(tmp_path))
        paths = [fm.path for fm in agg.files]
        assert "main.js" in paths
        assert "package-lock.json" not in paths

    def test_line_number_format(self, tmp_path):
        f = tmp_path / "a.js"
        f.write_text("line1\nline2\n", encoding="utf-8")
        agg = read_code(str(f))
        assert "   1: line1" in agg.text
        assert "   2: line2" in agg.text

    def test_truncation_at_threshold(self, tmp_path):
        f = tmp_path / "big.js"
        content = "\n".join(f"line{i}" for i in range(MAX_LINES_PER_FILE + 100))
        f.write_text(content, encoding="utf-8")
        agg = read_code(str(f))
        assert agg.files[0].truncated is True
        assert agg.files[0].lines == MAX_LINES_PER_FILE + 100
        assert "已截断 100 行" in agg.text
        last_numbered = f"{MAX_LINES_PER_FILE:>4}:"
        assert last_numbered in agg.text

    def test_empty_directory_raises(self, tmp_path):
        with pytest.raises(ValueError, match="没有可识别的代码文件"):
            read_code(str(tmp_path))

    def test_no_code_files_raises(self, tmp_path):
        (tmp_path / "readme.txt").write_text("hello", encoding="utf-8")
        with pytest.raises(ValueError, match="没有可识别的代码文件"):
            read_code(str(tmp_path))

    def test_binary_file_skipped(self, tmp_path):
        (tmp_path / "main.js").write_text("const a = 1\n", encoding="utf-8")
        (tmp_path / "image.png").write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00")
        agg = read_code(str(tmp_path))
        paths = [fm.path for fm in agg.files]
        assert "main.js" in paths
        assert "image.png" not in paths

    def test_file_header_in_text(self, sample_code_dir):
        agg = read_code(sample_code_dir)
        assert "=== main.js" in agg.text
        assert "行)" in agg.text

    def test_single_file_skips_extension_filter(self, tmp_path):
        f = tmp_path / "weird.xyz"
        f.write_text("content\n", encoding="utf-8")
        agg = read_code(str(f))
        assert len(agg.files) == 1
        assert agg.files[0].path == "weird.xyz"
