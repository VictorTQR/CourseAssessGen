"""共享 pytest fixture。"""
import json
from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"
SAMPLE_CODE_DIR = FIXTURES_DIR / "sample_student_code"
LLM_RESPONSES_DIR = FIXTURES_DIR / "llm_responses"


@pytest.fixture
def sample_code_dir() -> str:
    return str(SAMPLE_CODE_DIR)


@pytest.fixture
def llm_response_loader():
    def _load(name: str) -> dict:
        return json.loads((LLM_RESPONSES_DIR / name).read_text(encoding="utf-8"))
    return _load


@pytest.fixture
def fake_llm_config():
    from assessgen.llm import LLMConfig
    return LLMConfig(
        api_key="fake-key",
        base_url="http://localhost",
        model="fake-model",
        temperature=0.5,
    )
