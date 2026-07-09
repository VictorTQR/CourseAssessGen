"""cagen code 命令的 pydantic 数据模型。

双调用产生两份 JSON，各自一个模型。所有枚举字段用 Literal 强类型化。
LLM 输出经 extract_json -> model_validate 解析。
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class FileEntry(BaseModel):
    """提交物概述中的单个文件条目。"""
    path: str
    lines: int
    description: str


class KnowledgeCoverage(BaseModel):
    """知识点覆盖状态条目。"""
    name: str
    status: Literal["confirmed", "suspicious", "missing"]
    note: str


class Suspicion(BaseModel):
    """疑点标记条目。"""
    kind: Literal[
        "style_shift",
        "out_of_scope",
        "over_comment",
        "abnormal_complexity",
        "ai_trace",
    ]
    location: str
    description: str


class DiagnosisReport(BaseModel):
    """调用 1 产出：诊断报告（提交物概述 + 知识点覆盖 + 疑点）。"""
    files: list[FileEntry]
    total_lines: int
    knowledge_points: list[str]
    coverage: list[KnowledgeCoverage]
    suspicions: list[Suspicion]


class Question(BaseModel):
    """单个答辩问题。"""
    code_location: str
    text: str


class QuestionSet(BaseModel):
    """调用 2 产出：三层答辩问题清单。"""
    l1: list[Question] = Field(description="理解确认 · 摸底")
    l2: list[Question] = Field(description="决策追问 · 区分真假")
    l3: list[Question] = Field(description="变体假设 · 验证内化")
