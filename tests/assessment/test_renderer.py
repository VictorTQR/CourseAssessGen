"""MD 渲染器测试。"""
from assessgen.assessment.models import (
    DiagnosisReport, QuestionSet,
)
from assessgen.assessment.renderer import ReportMeta, render_report


def _make_diagnosis(suspicions=None, knowledge_points=None):
    return DiagnosisReport.model_validate({
        "files": [
            {"path": "main.js", "lines": 15, "description": "应用入口"},
            {"path": "stores/todo.js", "lines": 45, "description": "Pinia 状态管理"},
        ],
        "total_lines": 60,
        "knowledge_points": knowledge_points if knowledge_points is not None else ["Vue Router", "Pinia"],
        "coverage": [
            {"name": "Vue Router", "status": "confirmed", "note": "正确使用"},
            {"name": "Pinia", "status": "suspicious", "note": "使用方式复杂"},
        ],
        "suspicions": suspicions if suspicions is not None else [],
    })


def _make_questions(l1=None, l2=None, l3=None):
    return QuestionSet.model_validate({
        "l1": [{"code_location": "main.js", "text": "数据流是怎样的？"}] if l1 is None else l1,
        "l2": [{"code_location": "stores/todo.js", "text": "为什么用 Pinia？"}] if l2 is None else l2,
        "l3": [{"code_location": "main.js:6", "text": "删掉 router 会怎样？"}] if l3 is None else l3,
    })


def _make_meta(context=None):
    return ReportMeta(code_path="./student/", generated_at="2026-07-09T14:30", context=context)


class TestRenderReport:
    def test_title_present(self):
        md = render_report(_make_diagnosis(), _make_questions(), _make_meta())
        assert "# 学生代码评估报告" in md

    def test_meta_header(self):
        md = render_report(_make_diagnosis(), _make_questions(), _make_meta(context="第6周"))
        assert "./student/" in md
        assert "2026-07-09T14:30" in md
        assert "第6周" in md

    def test_context_omitted_when_none(self):
        md = render_report(_make_diagnosis(), _make_questions(), _make_meta(context=None))
        assert "背景信息" not in md

    def test_files_table(self):
        md = render_report(_make_diagnosis(), _make_questions(), _make_meta())
        assert "| 文件 | 行数 | 说明 |" in md
        assert "main.js" in md
        assert "stores/todo.js" in md
        assert "应用入口" in md

    def test_total_lines_and_knowledge_points(self):
        md = render_report(_make_diagnosis(), _make_questions(), _make_meta())
        assert "60 行" in md
        assert "2 个文件" in md
        assert "Vue Router" in md
        assert "Pinia" in md

    def test_coverage_table_with_emoji(self):
        md = render_report(_make_diagnosis(), _make_questions(), _make_meta())
        assert "✅ 确认掌握" in md
        assert "⚠️ 存疑" in md

    def test_suspicion_with_chinese_kind(self):
        diag = _make_diagnosis(suspicions=[
            {"kind": "out_of_scope", "location": "utils/request.js", "description": "axios 拦截器超纲"},
        ])
        md = render_report(diag, _make_questions(), _make_meta())
        assert "超出课程范围" in md
        assert "utils/request.js" in md

    def test_empty_suspicions_renders_hint(self):
        md = render_report(_make_diagnosis(suspicions=[]), _make_questions(), _make_meta())
        assert "未发现明显疑点" in md

    def test_empty_knowledge_points_renders_hint(self):
        md = render_report(_make_diagnosis(knowledge_points=[]), _make_questions(), _make_meta())
        assert "未识别到明显知识点" in md

    def test_questions_three_layers(self):
        md = render_report(_make_diagnosis(), _make_questions(), _make_meta())
        assert "L1 · 理解确认" in md
        assert "L2 · 决策追问" in md
        assert "L3 · 变体假设" in md

    def test_question_code_location_bold(self):
        md = render_report(_make_diagnosis(), _make_questions(), _make_meta())
        assert "**[main.js]**" in md
        assert "**[stores/todo.js]**" in md
        assert "**[main.js:6]**" in md

    def test_empty_layer_renders_none(self):
        qs = _make_questions(l3=[])
        md = render_report(_make_diagnosis(), qs, _make_meta())
        assert "（无）" in md

    def test_all_suspicion_kinds_mapped(self):
        kinds = [
            ("style_shift", "风格突变"),
            ("out_of_scope", "超出课程范围"),
            ("over_comment", "过度注释"),
            ("abnormal_complexity", "异常复杂"),
            ("ai_trace", "AI 痕迹"),
        ]
        for kind, display in kinds:
            diag = _make_diagnosis(suspicions=[
                {"kind": kind, "location": "f.js", "description": "test"},
            ])
            md = render_report(diag, _make_questions(), _make_meta())
            assert display in md
