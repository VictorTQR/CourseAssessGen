"""双调用 LLM prompt 构建器。

两个纯函数，输入确定输出确定，可 TDD。
两次调用都喂完整代码文本（接受 code token 翻倍以换取问题质量）。
"""
from __future__ import annotations

from dataclasses import dataclass

from assessgen.assessment.code_reader import CodeAggregation
from assessgen.assessment.models import DiagnosisReport


@dataclass(frozen=True)
class Prompt:
    """一次 LLM 调用的完整 prompt。"""
    system: str
    user: str


def _format_file_meta(agg: CodeAggregation) -> str:
    """格式化文件元信息清单。"""
    lines = []
    for fm in agg.files:
        if fm.truncated:
            lines.append(f"  - {fm.path} ({fm.lines} 行, 已截断展示前 800 行)")
        else:
            lines.append(f"  - {fm.path} ({fm.lines} 行)")
    return "\n".join(lines)


def build_diagnosis_prompt(
    agg: CodeAggregation,
    context: str | None,
) -> Prompt:
    """构建调用 1 的 prompt：读代码 -> 诊断 JSON。"""
    system = """你是一名经验丰富的高校教师，正在评估学生提交的代码。

任务：分析学生代码，输出一份结构化诊断 JSON。只输出 JSON 本身，不要任何 Markdown 标记或解释。

输出 JSON 结构：
{
  "files": [{"path": "相对路径", "lines": 行数, "description": "一句话说明"}],
  "total_lines": 总行数,
  "knowledge_points": ["知识点1", "知识点2"],
  "coverage": [{"name": "知识点名", "status": "confirmed|suspicious|missing", "note": "判断依据"}],
  "suspicions": [{"kind": "疑点类型", "location": "文件名:行号", "description": "说明"}]
}

字段规则：
1. files：列出所有代码文件，path/lines 参考下方"文件元信息清单"。
2. total_lines：所有文件行数总和（参考元信息清单，不要自己数代码行）。
3. knowledge_points：代码中涉及的知识点（短词）。
4. coverage 知识点覆盖状态，status 只能取以下三个值：
   - "confirmed"（✅ 确认掌握）：代码正确使用了该知识点，写法规范自然
   - "suspicious"（⚠️ 存疑）：代码用了但写法可疑（过于复杂/风格突变/超出课程范围）
   - "missing"（❌ 未体现）：作业应该涉及但代码中完全没有
5. suspicions 疑点标记，kind 只能取以下五个值：
   - "style_shift"：风格突变 - 同一文件内编码风格不一致
   - "out_of_scope"：超出课程范围 - 使用了课程尚未教授的技术
   - "over_comment"：过度注释 - 每行都有详尽注释或注释风格不符
   - "abnormal_complexity"：异常复杂 - 简单需求用了过于高级的写法
   - "ai_trace"：AI 痕迹 - 典型 AI 生成代码特征（过度防御性编程等）

措辞原则：疑点是"建议重点关注"的参考信号，而非"判定为 AI 生成"的证据。
"""
    if context:
        system += f"\n背景信息（用于判断超纲和应覆盖未覆盖）：\n{context}\n"

    user_parts = []
    if context:
        user_parts.append(f"[背景信息]\n{context}\n")
    user_parts.append(f"[文件元信息清单]\n{_format_file_meta(agg)}\n")
    user_parts.append(f"[带行号代码全文]\n{agg.text}")
    user = "\n".join(user_parts)

    return Prompt(system=system, user=user)


def build_questions_prompt(
    diagnosis: DiagnosisReport,
    agg: CodeAggregation,
    context: str | None,
) -> Prompt:
    """构建调用 2 的 prompt：基于诊断 + 代码 -> 三层答辩问题。"""
    system = """你是一名经验丰富的高校教师，正在为学生的代码提交准备答辩问题。

任务：基于已完成的诊断报告和代码，生成三层答辩问题。只输出 JSON 本身，不要任何 Markdown 标记。

输出 JSON 结构：
{
  "l1": [{"code_location": "文件名:行号", "text": "题目正文"}],
  "l2": [{"code_location": "文件名:行号", "text": "题目正文"}],
  "l3": [{"code_location": "文件名:行号", "text": "题目正文"}]
}

三层问题设计（核心）：
- L1 理解确认（2-3题）：考"代码做了什么"，摸底学生是否读得懂自己的代码
- L2 决策追问（2-3题）：考"为什么这么写"，区分 AI 代写（能背"是什么"但答不出"为什么"）
- L3 变体假设（2-3题）：考"如果改了会怎样"，验证内化（需要理解运行时行为和架构关联）

出题规则：
1. 禁止出"是什么"背诵题（如"Vue 是什么""Pinia 是什么"）
2. 每题必须引用具体代码位置（文件名 + 行号或函数名），使用 code_location 字段
3. L2/L3 是关键区分层，必须需要理解代码才能回答
4. 题量：每层 2-3 题，不要过多
"""
    if context:
        system += f"\n背景信息（约束问题不超纲）：\n{context}\n"

    user_parts = []
    if context:
        user_parts.append(f"[背景信息]\n{context}\n")
    user_parts.append(f"[诊断报告 JSON]\n{diagnosis.model_dump_json(indent=2)}\n")
    user_parts.append(f"[带行号代码全文]\n{agg.text}")
    user = "\n".join(user_parts)

    return Prompt(system=system, user=user)
