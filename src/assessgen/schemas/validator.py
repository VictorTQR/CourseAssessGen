"""动态校验器 — 基于 preset 的 example.json 推导校验规则。"""
from pathlib import Path
from typing import Any

from loguru import logger


def get_value_by_path(data: dict, path: str) -> Any:
    """按 `.` 分隔的 JSON path 逐层取值，路径不存在返回 None。"""
    current: Any = data
    for key in path.split("."):
        if isinstance(current, dict) and key in current:
            current = current[key]
        else:
            return None
    return current


def extract_type_info(value: Any) -> str:
    """将 Python 值映射为类型标签。"""
    if isinstance(value, str):
        return "str"
    if isinstance(value, int) or isinstance(value, float):
        return "number"
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, list):
        return "list"
    if isinstance(value, dict):
        return "dict"
    if value is None:
        return "null"
    return "unknown"


def validate_content(
    content: dict,
    example: dict,
    required_fields: list[str] | None = None,
    prefix: str = "",
) -> list[str]:
    """
    将 content 与 example 做结构对比，返回错误列表（空列表表示通过）。

    校验内容：
    1. required_fields 是否全部存在
    2. 字段类型是否匹配（str / list / dict / number 等）
    3. 嵌套结构是否一致
    """
    errors: list[str] = []

    # 校验必填字段
    if required_fields:
        for field_path in required_fields:
            val = get_value_by_path(content, field_path)
            if val is None:
                errors.append(f"缺少必填字段: {field_path}")

    # 递归校验结构
    _validate_structure(content, example, "", errors)

    return errors


def _validate_structure(content: Any, example: Any, path: str, errors: list[str]):
    """递归校验 content 的结构是否与 example 一致。"""
    if isinstance(example, dict):
        if not isinstance(content, dict):
            errors.append(f"[{path}] 期望 dict，实际为 {type(content).__name__}")
            return
        for key, example_val in example.items():
            child_path = f"{path}.{key}" if path else key
            if key not in content:
                # example 中的键在 content 里缺失，只 warn 不报错（非 required）
                pass
            else:
                _validate_structure(content[key], example_val, child_path, errors)
    elif isinstance(example, list):
        if not isinstance(content, list):
            errors.append(f"[{path}] 期望 list，实际为 {type(content).__name__}")
            return
        # 列表只校验第一个元素的结构
        if example and content:
            _validate_structure(content[0], example[0], f"{path}[0]", errors)
    else:
        # 标量类型校验
        expected_type = extract_type_info(example)
        actual_type = extract_type_info(content)
        if actual_type not in (expected_type, "null"):
            errors.append(f"[{path}] 期望 {expected_type}，实际为 {actual_type}")


def validate_json_syntax(json_path: Path) -> tuple[dict | None, list[str]]:
    """基本 JSON 语法校验，返回 (解析结果, 错误列表)。"""
    errors: list[str] = []
    try:
        import json

        data = json.loads(json_path.read_text(encoding="utf-8"))
        return data, errors
    except json.JSONDecodeError as e:
        errors.append(f"JSON 语法错误 (行 {e.lineno}, 列 {e.colno}): {e.msg}")
        return None, errors
