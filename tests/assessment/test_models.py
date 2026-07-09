"""pydantic 数据模型校验测试。"""
import pytest
from pydantic import ValidationError

from assessgen.assessment.models import (
    DiagnosisReport,
    FileEntry,
    KnowledgeCoverage,
    Question,
    QuestionSet,
    Suspicion,
)


class TestDiagnosisReport:
    def test_valid_full_report(self, llm_response_loader):
        data = llm_response_loader("diagnosis_valid.json")
        report = DiagnosisReport.model_validate(data)
        assert len(report.files) == 4
        assert report.total_lines == 55
        assert report.coverage[0].status == "confirmed"
        assert report.suspicions[0].kind == "out_of_scope"

    def test_invalid_status_enum_rejected(self, llm_response_loader):
        data = llm_response_loader("diagnosis_invalid_enum.json")
        with pytest.raises(ValidationError):
            DiagnosisReport.model_validate(data)

    def test_invalid_suspicion_kind_rejected(self):
        data = {
            "files": [], "total_lines": 0, "knowledge_points": [],
            "coverage": [],
            "suspicions": [{"kind": "unknown_kind", "location": "x", "description": "y"}],
        }
        with pytest.raises(ValidationError):
            DiagnosisReport.model_validate(data)

    def test_missing_required_field_rejected(self):
        data = {"files": [], "total_lines": 0, "knowledge_points": [], "coverage": []}
        # 缺 suspicions
        with pytest.raises(ValidationError):
            DiagnosisReport.model_validate(data)

    def test_empty_lists_allowed(self):
        report = DiagnosisReport.model_validate({
            "files": [], "total_lines": 0, "knowledge_points": [],
            "coverage": [], "suspicions": [],
        })
        assert report.files == []
        assert report.suspicions == []


class TestQuestionSet:
    def test_valid_question_set(self, llm_response_loader):
        data = llm_response_loader("questions_valid.json")
        qs = QuestionSet.model_validate(data)
        assert len(qs.l1) == 2
        assert len(qs.l2) == 2
        assert len(qs.l3) == 2
        assert qs.l1[0].code_location == "main.js"
        assert ":7" in qs.l1[1].code_location

    def test_missing_l3_rejected(self, llm_response_loader):
        data = llm_response_loader("questions_missing_field.json")
        with pytest.raises(ValidationError):
            QuestionSet.model_validate(data)

    def test_empty_layers_allowed(self):
        qs = QuestionSet.model_validate({"l1": [], "l2": [], "l3": []})
        assert qs.l1 == [] and qs.l2 == [] and qs.l3 == []
