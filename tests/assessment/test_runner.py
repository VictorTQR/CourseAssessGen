"""runner 编排 + 重试测试。"""
from unittest.mock import patch

import pytest

from assessgen.assessment.runner import AssessmentResult, run_assessment


class TestRunAssessmentNormal:
    @patch("assessgen.assessment.runner.call_llm")
    def test_normal_flow_two_calls(self, mock_call_llm, sample_code_dir, fake_llm_config, llm_response_loader):
        mock_call_llm.side_effect = [
            llm_response_loader("diagnosis_valid.json"),
            llm_response_loader("questions_valid.json"),
        ]
        result = run_assessment(sample_code_dir, None, fake_llm_config)
        assert isinstance(result, AssessmentResult)
        assert "# 学生代码评估报告" in result.markdown
        assert mock_call_llm.call_count == 2

    @patch("assessgen.assessment.runner.call_llm")
    def test_markdown_contains_all_sections(self, mock_call_llm, sample_code_dir, fake_llm_config, llm_response_loader):
        mock_call_llm.side_effect = [
            llm_response_loader("diagnosis_valid.json"),
            llm_response_loader("questions_valid.json"),
        ]
        result = run_assessment(sample_code_dir, "第6周作业", fake_llm_config)
        assert "📋 提交物概述" in result.markdown
        assert "🔍 诊断分析" in result.markdown
        assert "📝 答辩问题清单" in result.markdown
        assert "L1 · 理解确认" in result.markdown
        assert "第6周作业" in result.markdown


class TestRetryLogic:
    @patch("assessgen.assessment.runner.call_llm")
    def test_schema_failure_retries_once_and_succeeds(
        self, mock_call_llm, sample_code_dir, fake_llm_config, llm_response_loader
    ):
        # 第1次调用返回非法 enum，第2次（重试）返回合法
        # 第3次（调用2）返回合法 questions
        mock_call_llm.side_effect = [
            llm_response_loader("diagnosis_invalid_enum.json"),
            llm_response_loader("diagnosis_valid.json"),
            llm_response_loader("questions_valid.json"),
        ]
        result = run_assessment(sample_code_dir, None, fake_llm_config)
        assert isinstance(result, AssessmentResult)
        assert mock_call_llm.call_count == 3  # 1 失败 + 1 重试 + 1 调用2

    @patch("assessgen.assessment.runner.call_llm")
    def test_two_failures_raises_valueerror(
        self, mock_call_llm, sample_code_dir, fake_llm_config, llm_response_loader
    ):
        mock_call_llm.side_effect = [
            llm_response_loader("diagnosis_invalid_enum.json"),
            llm_response_loader("diagnosis_invalid_enum.json"),
        ]
        with pytest.raises(ValueError, match="不符合 schema"):
            run_assessment(sample_code_dir, None, fake_llm_config)


class TestErrorPropagation:
    @patch("assessgen.assessment.runner.call_llm")
    def test_empty_dir_raises_valueerror(self, mock_call_llm, tmp_path, fake_llm_config):
        with pytest.raises(ValueError, match="没有可识别的代码文件"):
            run_assessment(str(tmp_path), None, fake_llm_config)
        assert mock_call_llm.call_count == 0  # 不应调用 LLM
