"""评估报告 Markdown 渲染器 - 把模型渲染成 MD 字符串。纯函数，零依赖。"""
from __future__ import annotations

from dataclasses import dataclass

from assessgen.assessment.models import DiagnosisReport, QuestionSet

_STATUS_DISPLAY = {
    "confirmed": "✅ 确认掌握",
    "suspicious": "⚠️ 存疑",
    "missing": "❌ 未体现",
}

_SUSPICION_DISPLAY = {
    "style_shift": "风格突变",
    "out_of_scope": "超出课程范围",
    "over_comment": "过度注释",
    "abnormal_complexity": "异常复杂",
    "ai_trace": "AI 痕迹",
}


@dataclass(frozen=True)
class ReportMeta:
    """报告元信息（来自 CLI 参数，非 LLM 产出）。"""
    code_path: str
    generated_at: str
    context: str | None


def _render_meta(meta: ReportMeta) -> str:
    lines = [f"> **代码路径：** {meta.code_path}", f"> **生成时间：** {meta.generated_at}"]
    if meta.context:
        lines.append(f"> **背景信息：** {meta.context}")
    return "\n".join(lines)


def _render_overview(diagnosis: DiagnosisReport) -> str:
    lines = ["## 📋 提交物概述", "", "| 文件 | 行数 | 说明 |", "|------|------|------|"]
    for f in diagnosis.files:
        lines.append(f"| {f.path} | {f.lines} | {f.description} |")
    lines.append("")
    lines.append(f"**代码总量：** {diagnosis.total_lines} 行 / {len(diagnosis.files)} 个文件")
    if diagnosis.knowledge_points:
        lines.append(f"**涉及知识点：** {'、'.join(diagnosis.knowledge_points)}")
    else:
        lines.append("**涉及知识点：** （未识别到明显知识点）")
    return "\n".join(lines)


def _render_diagnosis(diagnosis: DiagnosisReport) -> str:
    lines = ["## 🔍 诊断分析", "", "### 知识点覆盖", "",
             "| 知识点 | 状态 | 说明 |", "|--------|------|------|"]
    for c in diagnosis.coverage:
        lines.append(f"| {c.name} | {_STATUS_DISPLAY[c.status]} | {c.note} |")
    lines.append("")
    lines.append("### ⚠️ 疑点标记")
    if diagnosis.suspicions:
        for i, s in enumerate(diagnosis.suspicions, 1):
            kind_label = _SUSPICION_DISPLAY[s.kind]
            lines.append(f"{i}. **{kind_label}**（`{s.location}`）- {s.description}")
    else:
        lines.append("未发现明显疑点。")
    return "\n".join(lines)


def _render_questions(questions: QuestionSet) -> str:
    lines = ["## 📝 答辩问题清单"]
    for label, qs in [("L1 · 理解确认", questions.l1),
                      ("L2 · 决策追问", questions.l2),
                      ("L3 · 变体假设", questions.l3)]:
        lines.append("")
        lines.append(f"### {label}")
        if qs:
            for i, q in enumerate(qs, 1):
                lines.append(f"{i}. **[{q.code_location}]** {q.text}")
        else:
            lines.append("（无）")
    return "\n".join(lines)


def render_report(
    diagnosis: DiagnosisReport,
    questions: QuestionSet,
    meta: ReportMeta,
) -> str:
    """渲染完整评估报告 Markdown。"""
    sections = [
        "# 学生代码评估报告",
        "",
        _render_meta(meta),
        "",
        "---",
        "",
        _render_overview(diagnosis),
        "",
        "---",
        "",
        _render_diagnosis(diagnosis),
        "",
        "---",
        "",
        _render_questions(questions),
        "",
    ]
    return "\n".join(sections)
