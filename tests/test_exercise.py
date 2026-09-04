"""exercise 命令素材加载测试 — load_material 的后缀分支 + prompt 素材类型渲染。"""
import json
from pathlib import Path

import pytest

from assessgen.commands.exercise import load_material
from assessgen.llm import build_exercise_prompt

_LESSON_PLAN = {
    "meta": {"source_lesson": "第6周 Vue Router 与 Pinia"},
    "topics": ["Vue Router", "Pinia"],
}
_LECTURE = "今天我们讲 Vue Router 的两种路由模式，重点是导航守卫……"


def _write(tmp_path: Path, name: str, content: str, encoding: str = "utf-8") -> Path:
    p = tmp_path / name
    p.write_text(content, encoding=encoding)
    return p


# ---------- load_material：JSON 教案 ----------


def test_load_material_json(tmp_path: Path):
    p = _write(tmp_path, "lesson.json", json.dumps(_LESSON_PLAN, ensure_ascii=False))
    m = load_material(p)
    assert m.desc == "教案 JSON"
    assert "教案 JSON" in m.user_text
    assert json.loads(m.user_text.split("\n\n", 1)[1]) == _LESSON_PLAN


def test_load_material_json_uppercase_suffix(tmp_path: Path):
    p = _write(tmp_path, "lesson.JSON", json.dumps(_LESSON_PLAN))
    m = load_material(p)
    assert m.desc == "教案 JSON"


def test_load_material_invalid_json(tmp_path: Path):
    p = _write(tmp_path, "lesson.json", "{not valid json")
    with pytest.raises(ValueError, match="解析失败"):
        load_material(p)


# ---------- load_material：txt/md 讲稿 ----------


@pytest.mark.parametrize("name", ["lecture.txt", "lecture.md", "lecture.TXT"])
def test_load_material_lecture_text(tmp_path: Path, name: str):
    p = _write(tmp_path, name, _LECTURE)
    m = load_material(p)
    assert m.desc == "授课讲稿"
    assert "授课讲稿" in m.user_text
    assert _LECTURE in m.user_text


def test_load_material_lecture_gbk(tmp_path: Path):
    p = _write(tmp_path, "lecture.txt", _LECTURE, encoding="gbk")
    m = load_material(p)
    assert _LECTURE in m.user_text


def test_load_material_empty_lecture(tmp_path: Path):
    p = _write(tmp_path, "lecture.txt", "   \n\n  ")
    with pytest.raises(ValueError, match="为空"):
        load_material(p)


# ---------- load_material：不支持的后缀 ----------


def test_load_material_unsupported_suffix(tmp_path: Path):
    p = _write(tmp_path, "lecture.docx", _LECTURE)
    with pytest.raises(ValueError, match="不支持的文件类型"):
        load_material(p)


# ---------- build_exercise_prompt：素材类型渲染 ----------


def test_build_exercise_prompt_default_lesson_plan():
    prompt = build_exercise_prompt({"exercises": []})
    assert "教案 JSON" in prompt
    assert "教学目标、重难点、教学环节" in prompt


def test_build_exercise_prompt_lecture_material():
    prompt = build_exercise_prompt(
        {"exercises": []},
        material_desc="授课讲稿",
        material_hint="讲稿是教师的授课内容文本。",
    )
    assert "授课讲稿" in prompt
    assert "讲稿是教师的授课内容文本。" in prompt
    assert "教案" not in prompt
