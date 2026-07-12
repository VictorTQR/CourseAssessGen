"""超星学习通题库导入 xlsx 渲染器。

将 exercises.json 展开成超星「课程题库」Excel 导入格式：
- 独立题型（单选/多选/填空/判断/简答）→ 1 行
- 嵌套题型（阅读理解）→ 1 大题行 + N 小题行

表头 19 列：目录|题目类型|大题题干|小题题型|小题题干|正确答案|答案解析|难易度|知识点|标签|选项数|选项A~H
"""
from pathlib import Path
from typing import TYPE_CHECKING

from loguru import logger

from assessgen.renderers.base import BaseRenderer

if TYPE_CHECKING:
    from assessgen.presets.loader import PresetConfig


# 表头（19 列，A-S）
_HEADERS = [
    "目录", "题目类型", "大题题干", "小题题型", "小题题干",
    "正确答案", "答案解析", "难易度", "知识点", "标签",
    "选项数", "选项A", "选项B", "选项C", "选项D",
    "选项E", "选项F", "选项G", "选项H",
]


class ChaoxingXlsxRenderer(BaseRenderer):
    """超星学习通题库导入格式渲染器。

    按 preset 的 format_spec 将 exercises.json 展开成超星 xlsx 行结构。
    """

    def render(
        self,
        content: dict,
        config: "PresetConfig",
        preset_dir: Path,
        output_path: Path,
    ) -> Path:
        from openpyxl import Workbook

        spec = config.format_spec or {}
        type_mapping = spec.get("type_mapping", {})
        difficulty_mapping = spec.get("difficulty_mapping", {})
        default_catalog = spec.get("default_catalog", "")
        # 数据起始行：超星平台导入时会跳过表头行和提示行，数据从第 3 行开始
        data_start_row = spec.get("data_start_row", 2)

        exercises = content.get("exercises", [])
        if not exercises:
            logger.warning("exercises.json 中没有习题，仅输出表头")

        wb = Workbook()
        ws = wb.active
        ws.title = "课程题库"

        # 写表头（第 1 行）
        for col_idx, header in enumerate(_HEADERS, 1):
            ws.cell(row=1, column=col_idx, value=header)

        # 逐题展开成行
        row = data_start_row
        for ex in exercises:
            if ex.get("type") == "reading_comprehension":
                row = self._write_composite(ws, ex, row, type_mapping, difficulty_mapping, default_catalog)
            else:
                self._write_standalone(ws, ex, row, type_mapping, difficulty_mapping, default_catalog)
                row += 1

        # 设置列宽（题干列宽一些）
        from openpyxl.utils import get_column_letter
        col_widths = [12, 10, 50, 10, 40, 10, 30, 8, 15, 15, 8,
                      20, 20, 20, 20, 20, 20, 20, 20]
        for col_idx, width in enumerate(col_widths, 1):
            ws.column_dimensions[get_column_letter(col_idx)].width = width

        output_path.parent.mkdir(parents=True, exist_ok=True)
        wb.save(output_path)
        logger.info(f"超星习题 xlsx 生成完成: {output_path}")
        return output_path

    def _write_standalone(
        self,
        ws,
        ex: dict,
        row: int,
        type_mapping: dict,
        difficulty_mapping: dict,
        default_catalog: str,
    ) -> None:
        """写独立题型（1 行）。"""
        q_type = ex.get("type", "")
        catalog = ex.get("catalog", default_catalog) or default_catalog
        ws.cell(row=row, column=1, value=catalog)
        ws.cell(row=row, column=2, value=type_mapping.get(q_type, q_type))
        ws.cell(row=row, column=3, value=ex.get("stem", ""))
        # D/E（小题题型/小题题干）留空
        ws.cell(row=row, column=6, value=_format_answer(ex))
        ws.cell(row=row, column=7, value=ex.get("explanation", ""))
        ws.cell(row=row, column=8, value=_map_difficulty(ex.get("difficulty"), difficulty_mapping))
        ws.cell(row=row, column=9, value=_join_list(ex.get("knowledge_points")))
        ws.cell(row=row, column=10, value=_join_list(ex.get("tags"), sep="；"))
        ws.cell(row=row, column=11, value=_option_count(ex))
        _write_options(ws, ex, row)

    def _write_composite(
        self,
        ws,
        ex: dict,
        row: int,
        type_mapping: dict,
        difficulty_mapping: dict,
        default_catalog: str,
    ) -> int:
        """写嵌套题型（大题行 + N 小题行），返回下一空行号。"""
        catalog = ex.get("catalog", default_catalog) or default_catalog
        q_type = ex.get("type", "")

        # 大题行：A=目录, B=题型, C=题干, H=难易度, I=知识点, J=标签
        ws.cell(row=row, column=1, value=catalog)
        ws.cell(row=row, column=2, value=type_mapping.get(q_type, q_type))
        ws.cell(row=row, column=3, value=ex.get("stem", ""))
        ws.cell(row=row, column=8, value=_map_difficulty(ex.get("difficulty"), difficulty_mapping))
        ws.cell(row=row, column=9, value=_join_list(ex.get("knowledge_points")))
        ws.cell(row=row, column=10, value=_join_list(ex.get("tags"), sep="；"))
        row += 1

        # 小题行：D=小题题型, E=小题题干, F=答案, G=解析, K=选项数, L-S=选项
        for sub in ex.get("sub_questions", []):
            sub_type = sub.get("type", "")
            ws.cell(row=row, column=4, value=type_mapping.get(sub_type, sub_type))
            ws.cell(row=row, column=5, value=sub.get("stem", ""))
            ws.cell(row=row, column=6, value=_format_answer(sub))
            ws.cell(row=row, column=7, value=sub.get("explanation", ""))
            ws.cell(row=row, column=11, value=_option_count(sub))
            _write_options(ws, sub, row)
            row += 1

        return row


def _format_answer(ex: dict) -> str:
    """格式化答案到 F 列。

    - single_choice: answer[0]，如 "B"
    - multiple_choice: "".join(answer)，如 "BCD"
    - true_false: answer[0]，如 "A"
    - short_answer: 固定 "A"（答案内容写在选项A列）
    - fill_blank: 空（答案在各选项列）
    - reading_comprehension 大题行: 空
    """
    q_type = ex.get("type")
    answer = ex.get("answer", [])

    if q_type == "multiple_choice":
        return "".join(answer) if answer else ""
    if q_type == "single_choice" or q_type == "true_false":
        return answer[0] if answer else ""
    if q_type == "short_answer":
        return "A"
    # fill_blank / reading_comprehension 大题行
    return ""


def _option_count(ex: dict) -> int | str:
    """计算选项数（K 列）。

    - single_choice / multiple_choice: len(options)
    - true_false: 2
    - fill_blank: len(answer)（空数）
    - short_answer: 1
    """
    q_type = ex.get("type")
    if q_type in ("single_choice", "multiple_choice"):
        return len(ex.get("options", []))
    if q_type == "true_false":
        return 2
    if q_type == "fill_blank":
        return len(ex.get("answer", []))
    if q_type == "short_answer":
        return 1
    return ""


def _write_options(ws, ex: dict, row: int) -> None:
    """写选项到 L-S 列（12-19 列）。

    - single_choice / multiple_choice: options 逐列填
    - true_false: L="正确", M="错误"
    - fill_blank: answer 逐空填到 L、M、N...
    - short_answer: L=answer[0]（答案全文）
    """
    q_type = ex.get("type")
    options_col_start = 12  # L 列

    if q_type in ("single_choice", "multiple_choice"):
        for i, opt in enumerate(ex.get("options", [])):
            ws.cell(row=row, column=options_col_start + i, value=opt)
    elif q_type == "true_false":
        ws.cell(row=row, column=options_col_start, value="正确")
        ws.cell(row=row, column=options_col_start + 1, value="错误")
    elif q_type == "fill_blank":
        for i, ans in enumerate(ex.get("answer", [])):
            ws.cell(row=row, column=options_col_start + i, value=ans)
    elif q_type == "short_answer":
        answer = ex.get("answer", [])
        if answer:
            ws.cell(row=row, column=options_col_start, value=answer[0])


def _map_difficulty(difficulty: str | None, mapping: dict) -> str:
    """难度映射：easy→易, medium→中, hard→难。未映射时原样返回。"""
    if not difficulty:
        return ""
    return mapping.get(difficulty, difficulty)


def _join_list(value, sep: str = "；") -> str:
    """将列表用分隔符拼接成字符串；非列表原样返回。"""
    if value is None:
        return ""
    if isinstance(value, list):
        return sep.join(str(v) for v in value)
    return str(value)
