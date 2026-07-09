"""prompt builder 测试。"""
from assessgen.assessment.code_reader import CodeAggregation, FileMeta
from assessgen.assessment.models import DiagnosisReport
from assessgen.assessment.prompts import (
    Prompt,
    build_diagnosis_prompt,
    build_questions_prompt,
)


def _make_agg(text="   1: const a = 1\n", files=None):
    if files is None:
        files = [FileMeta(path="main.js", lines=1, truncated=False)]
    return CodeAggregation(text=text, files=files)


def _make_diagnosis():
    return DiagnosisReport.model_validate({
        "files": [{"path": "main.js", "lines": 1, "description": "入口"}],
        "total_lines": 1,
        "knowledge_points": ["Vue"],
        "coverage": [{"name": "Vue", "status": "confirmed", "note": "ok"}],
        "suspicions": [],
    })


class TestBuildDiagnosisPrompt:
    def test_returns_prompt_dataclass(self):
        p = build_diagnosis_prompt(_make_agg(), None)
        assert isinstance(p, Prompt)
        assert isinstance(p.system, str)
        assert isinstance(p.user, str)

    def test_system_contains_status_enums(self):
        p = build_diagnosis_prompt(_make_agg(), None)
        assert "confirmed" in p.system
        assert "suspicious" in p.system
        assert "missing" in p.system

    def test_system_contains_kind_enums(self):
        p = build_diagnosis_prompt(_make_agg(), None)
        assert "style_shift" in p.system
        assert "out_of_scope" in p.system
        assert "over_comment" in p.system
        assert "abnormal_complexity" in p.system
        assert "ai_trace" in p.system

    def test_system_contains_json_instruction(self):
        p = build_diagnosis_prompt(_make_agg(), None)
        assert "JSON" in p.system

    def test_user_contains_code_text(self):
        agg = _make_agg(text="   1: const a = 1\n")
        p = build_diagnosis_prompt(agg, None)
        assert "const a = 1" in p.user

    def test_user_contains_file_meta(self):
        agg = _make_agg(files=[FileMeta(path="main.js", lines=45, truncated=False)])
        p = build_diagnosis_prompt(agg, None)
        assert "main.js" in p.user
        assert "45" in p.user

    def test_user_starts_with_context_when_provided(self):
        p = build_diagnosis_prompt(_make_agg(), "第6周作业")
        assert "第6周作业" in p.user

    def test_truncated_file_marked_in_meta(self):
        agg = _make_agg(files=[FileMeta(path="big.js", lines=1200, truncated=True)])
        p = build_diagnosis_prompt(agg, None)
        assert "已截断" in p.user


class TestBuildQuestionsPrompt:
    def test_returns_prompt_dataclass(self):
        p = build_questions_prompt(_make_diagnosis(), _make_agg(), None)
        assert isinstance(p, Prompt)

    def test_system_contains_l1_l2_l3(self):
        p = build_questions_prompt(_make_diagnosis(), _make_agg(), None)
        assert "L1" in p.system
        assert "L2" in p.system
        assert "L3" in p.system

    def test_system_forbids_recitation_questions(self):
        p = build_questions_prompt(_make_diagnosis(), _make_agg(), None)
        assert "禁止" in p.system or "背诵" in p.system

    def test_user_contains_diagnosis_json(self):
        p = build_questions_prompt(_make_diagnosis(), _make_agg(), None)
        assert "main.js" in p.user
        assert "knowledge_points" in p.user

    def test_user_contains_code_text(self):
        agg = _make_agg(text="   1: const a = 1\n")
        p = build_questions_prompt(_make_diagnosis(), agg, None)
        assert "const a = 1" in p.user

    def test_user_contains_context_when_provided(self):
        p = build_questions_prompt(_make_diagnosis(), _make_agg(), "第6周")
        assert "第6周" in p.user
