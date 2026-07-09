# `cagen code` 命令实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现 `cagen code` 命令--分析学生代码，双次 LLM 调用生成分层答辩问题 + 诊断报告 MD。

**Architecture:** 内聚 `assessment/` 子包（models/code_reader/prompts/renderer/runner），`commands/code.py` 薄 CLI 壳。双次 LLM 调用：先诊断（code -> DiagnosisReport），后出题（diagnosis + code -> QuestionSet）。pydantic v2 强类型校验，纯函数 TDD + LLM mock。

**Tech Stack:** Python 3.12+, typer, pydantic v2, openai SDK, loguru, pytest

**Spec:** `docs/Phase2-code-design.md`

---

## 文件结构

| 文件 | 责任 | 新建/改动 |
|---|---|---|
| `pyproject.toml` | 加 pytest dev 依赖 | 改动 |
| `src/assessgen/assessment/__init__.py` | 子包标识 | 新建 |
| `src/assessgen/assessment/models.py` | pydantic 模型（DiagnosisReport/QuestionSet） | 新建 |
| `src/assessgen/assessment/code_reader.py` | 代码聚合（CodeAggregation/FileMeta/read_code） | 新建 |
| `src/assessgen/assessment/prompts.py` | Prompt + 两个 prompt builder | 新建 |
| `src/assessgen/assessment/renderer.py` | ReportMeta + render_report + 枚举映射 | 新建 |
| `src/assessgen/assessment/runner.py` | AssessmentResult + run_assessment + validate_or_retry | 新建 |
| `src/assessgen/commands/code.py` | CLI 薄壳 | 新建 |
| `src/assessgen/cli.py` | 注册 code 命令 | 改动 |
| `tests/conftest.py` | 共享 fixture | 新建 |
| `tests/assessment/test_models.py` | 模型校验测试 | 新建 |
| `tests/assessment/test_code_reader.py` | 聚合测试 | 新建 |
| `tests/assessment/test_prompts.py` | prompt 构建测试 | 新建 |
| `tests/assessment/test_renderer.py` | 渲染测试 | 新建 |
| `tests/assessment/test_runner.py` | 编排+重试测试 | 新建 |
| `tests/fixtures/sample_student_code/*` | Vue+JS 样例 | 新建 |
| `tests/fixtures/llm_responses/*.json` | LLM 响应 fixture | 新建 |

---

## Task 1: 项目 setup + 测试 fixture

**Files:**
- Modify: `pyproject.toml`
- Create: `tests/__init__.py`, `tests/assessment/__init__.py`, `tests/conftest.py`
- Create: `tests/fixtures/sample_student_code/main.js`, `App.vue`, `stores/todo.js`, `utils/request.js`
- Create: `tests/fixtures/llm_responses/diagnosis_valid.json`, `diagnosis_invalid_enum.json`, `questions_valid.json`, `questions_missing_field.json`

- [ ] **Step 1: 加 pytest dev 依赖**

在 `pyproject.toml` 末尾追加：

```toml
[dependency-groups]
dev = ["pytest>=8.0.0"]
```

- [ ] **Step 2: 安装 dev 依赖**

Run: `uv sync --dev`
Expected: 成功安装 pytest

- [ ] **Step 3: 创建测试目录结构**

创建空文件：
- `tests/__init__.py`（空）
- `tests/assessment/__init__.py`（空）

- [ ] **Step 4: 创建 sample_student_code fixture**

`tests/fixtures/sample_student_code/main.js`:
```javascript
import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import router from './router'

const app = createApp(App)
app.use(createPinia())
app.use(router)
app.mount('#app')
```

`tests/fixtures/sample_student_code/App.vue`:
```vue
<template>
  <div id="app">
    <router-view />
  </div>
</template>

<script setup>
import { useTodoStore } from './stores/todo'
const todoStore = useTodoStore()
</script>
```

`tests/fixtures/sample_student_code/stores/todo.js`:
```javascript
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export const useTodoStore = defineStore('todo', () => {
  const todos = ref([])
  const remaining = computed(() => todos.value.filter(t => !t.done).length)

  function add(text) {
    todos.value.push({ id: Date.now(), text, done: false })
  }
  function toggle(id) {
    const todo = todos.value.find(t => t.id === id)
    if (todo) todo.done = !todo.done
  }
  function remove(id) {
    todos.value = todos.value.filter(t => t.id !== id)
  }

  return { todos, remaining, add, toggle, remove }
})
```

`tests/fixtures/sample_student_code/utils/request.js`:
```javascript
import axios from 'axios'

const request = axios.create({
  baseURL: '/api',
  timeout: 5000,
})

request.interceptors.request.use(config => {
  const token = localStorage.getItem('token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

export default request
```

- [ ] **Step 5: 创建 LLM 响应 fixture**

`tests/fixtures/llm_responses/diagnosis_valid.json`:
```json
{
  "files": [
    {"path": "main.js", "lines": 9, "description": "应用入口，挂载 Vue 实例"},
    {"path": "App.vue", "lines": 10, "description": "根组件，含 router-view"},
    {"path": "stores/todo.js", "lines": 22, "description": "Pinia 状态管理"},
    {"path": "utils/request.js", "lines": 14, "description": "axios 封装与拦截器"}
  ],
  "total_lines": 55,
  "knowledge_points": ["Vue Router", "Pinia", "Composition API", "axios"],
  "coverage": [
    {"name": "Vue Router", "status": "confirmed", "note": "main.js 正确注册 router"},
    {"name": "Pinia 状态管理", "status": "confirmed", "note": "stores/todo.js 使用 defineStore 组合式写法"},
    {"name": "Composition API", "status": "confirmed", "note": "使用 ref/computed"},
    {"name": "axios 拦截器", "status": "suspicious", "note": "封装完整，可能超出课程范围"}
  ],
  "suspicions": [
    {"kind": "out_of_scope", "location": "utils/request.js", "description": "封装了完整 axios 拦截器，若课程未涉及则属超纲"}
  ]
}
```

`tests/fixtures/llm_responses/diagnosis_invalid_enum.json`:
```json
{
  "files": [],
  "total_lines": 0,
  "knowledge_points": [],
  "coverage": [
    {"name": "test", "status": "invalid_status", "note": "非法枚举值"}
  ],
  "suspicions": []
}
```

`tests/fixtures/llm_responses/questions_valid.json`:
```json
{
  "l1": [
    {"code_location": "main.js", "text": "项目启动时做了哪些初始化？数据流从哪开始？"},
    {"code_location": "stores/todo.js:7", "text": "defineStore 做了什么？这个 store 管理了哪些状态？"}
  ],
  "l2": [
    {"code_location": "stores/todo.js", "text": "你用 Pinia 管理待办列表，为什么不用 props/emit？对这个项目哪个更合适？"},
    {"code_location": "utils/request.js:8", "text": "拦截器里加 token 是为什么？token 的作用是什么？"}
  ],
  "l3": [
    {"code_location": "main.js:6", "text": "如果把 app.use(router) 这行删掉，访问 / 路由会怎样？"},
    {"code_location": "stores/todo.js", "text": "如果需求改为每个 Todo 支持优先级并按优先级排序，你要改哪几个文件？分别改什么？"}
  ]
}
```

`tests/fixtures/llm_responses/questions_missing_field.json`:
```json
{
  "l1": [{"code_location": "main.js", "text": "问题1"}],
  "l2": []
}
```

- [ ] **Step 6: 创建 conftest.py**

`tests/conftest.py`:
```python
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
```

- [ ] **Step 7: 验证 pytest 可运行**

Run: `uv run pytest tests/ -v`
Expected: `no tests ran` (0 items), 无收集错误

- [ ] **Step 8: Commit**

```bash
git add pyproject.toml uv.lock tests/
git commit -m "test: 搭建 pytest 测试基础设施 + sample fixture"
```

---

## Task 2: 数据模型 models.py（TDD）

**Files:**
- Create: `src/assessgen/assessment/__init__.py`
- Create: `src/assessgen/assessment/models.py`
- Test: `tests/assessment/test_models.py`

- [ ] **Step 1: 创建子包 __init__.py**

`src/assessgen/assessment/__init__.py`:
```python
"""学生代码评估领域逻辑子包。"""
```

- [ ] **Step 2: 写失败测试**

`tests/assessment/test_models.py`:
```python
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
        assert ":12" in qs.l1[1].code_location

    def test_missing_l3_rejected(self, llm_response_loader):
        data = llm_response_loader("questions_missing_field.json")
        with pytest.raises(ValidationError):
            QuestionSet.model_validate(data)

    def test_empty_layers_allowed(self):
        qs = QuestionSet.model_validate({"l1": [], "l2": [], "l3": []})
        assert qs.l1 == [] and qs.l2 == [] and qs.l3 == []
```

- [ ] **Step 3: 运行测试验证失败**

Run: `uv run pytest tests/assessment/test_models.py -v`
Expected: FAIL (ModuleNotFoundError: No module named 'assessgen.assessment.models')

- [ ] **Step 4: 实现 models.py**

`src/assessgen/assessment/models.py`:
```python
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
```

- [ ] **Step 5: 运行测试验证通过**

Run: `uv run pytest tests/assessment/test_models.py -v`
Expected: 7 passed

- [ ] **Step 6: Commit**

```bash
git add src/assessgen/assessment/__init__.py src/assessgen/assessment/models.py tests/assessment/test_models.py
git commit -m "feat(assessment): 添加 pydantic 数据模型 DiagnosisReport/QuestionSet"
```

---

## Task 3: code_reader.py（TDD）

**Files:**
- Create: `src/assessgen/assessment/code_reader.py`
- Test: `tests/assessment/test_code_reader.py`

- [ ] **Step 1: 写失败测试**

`tests/assessment/test_code_reader.py`:
```python
"""code_reader 聚合测试。"""
import os
from pathlib import Path

import pytest

from assessgen.assessment.code_reader import (
    MAX_LINES_PER_FILE,
    CodeAggregation,
    FileMeta,
    read_code,
)


class TestReadCode:
    def test_single_file_input(self, tmp_path):
        f = tmp_path / "app.js"
        f.write_text("const a = 1\nconst b = 2\n", encoding="utf-8")
        agg = read_code(str(f))
        assert len(agg.files) == 1
        assert agg.files[0].path == "app.js"
        assert agg.files[0].lines == 2
        assert agg.files[0].truncated is False
        assert "   1: const a = 1" in agg.text

    def test_directory_traversal_sorted(self, sample_code_dir):
        agg = read_code(sample_code_dir)
        paths = [fm.path for fm in agg.files]
        assert paths == sorted(paths)
        assert "App.vue" in paths
        assert "main.js" in paths
        assert "stores/todo.js" in paths

    def test_excludes_node_modules(self, tmp_path):
        (tmp_path / "node_modules").mkdir()
        (tmp_path / "node_modules" / "dep.js").write_text("x", encoding="utf-8")
        (tmp_path / "main.js").write_text("const a = 1\n", encoding="utf-8")
        agg = read_code(str(tmp_path))
        paths = [fm.path for fm in agg.files]
        assert "main.js" in paths
        assert all("node_modules" not in p for p in paths)

    def test_excludes_lock_files(self, tmp_path):
        (tmp_path / "package-lock.json").write_text("{}", encoding="utf-8")
        (tmp_path / "main.js").write_text("const a = 1\n", encoding="utf-8")
        agg = read_code(str(tmp_path))
        paths = [fm.path for fm in agg.files]
        assert "main.js" in paths
        assert "package-lock.json" not in paths

    def test_line_number_format(self, tmp_path):
        f = tmp_path / "a.js"
        f.write_text("line1\nline2\n", encoding="utf-8")
        agg = read_code(str(f))
        assert "   1: line1" in agg.text
        assert "   2: line2" in agg.text

    def test_truncation_at_threshold(self, tmp_path):
        f = tmp_path / "big.js"
        content = "\n".join(f"line{i}" for i in range(MAX_LINES_PER_FILE + 100))
        f.write_text(content, encoding="utf-8")
        agg = read_code(str(f))
        assert agg.files[0].truncated is True
        assert agg.files[0].lines == MAX_LINES_PER_FILE + 100
        assert f"已截断 100 行" in agg.text
        last_numbered = f"{MAX_LINES_PER_FILE:>4}:"
        assert last_numbered in agg.text

    def test_empty_directory_raises(self, tmp_path):
        with pytest.raises(ValueError, match="没有可识别的代码文件"):
            read_code(str(tmp_path))

    def test_no_code_files_raises(self, tmp_path):
        (tmp_path / "readme.txt").write_text("hello", encoding="utf-8")
        with pytest.raises(ValueError, match="没有可识别的代码文件"):
            read_code(str(tmp_path))

    def test_binary_file_skipped(self, tmp_path):
        (tmp_path / "main.js").write_text("const a = 1\n", encoding="utf-8")
        (tmp_path / "image.png").write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00")
        agg = read_code(str(tmp_path))
        paths = [fm.path for fm in agg.files]
        assert "main.js" in paths
        assert "image.png" not in paths

    def test_file_header_in_text(self, sample_code_dir):
        agg = read_code(sample_code_dir)
        assert "=== main.js" in agg.text
        assert "行)" in agg.text

    def test_single_file_skips_extension_filter(self, tmp_path):
        f = tmp_path / "weird.xyz"
        f.write_text("content\n", encoding="utf-8")
        agg = read_code(str(f))
        assert len(agg.files) == 1
        assert agg.files[0].path == "weird.xyz"
```

- [ ] **Step 2: 运行测试验证失败**

Run: `uv run pytest tests/assessment/test_code_reader.py -v`
Expected: FAIL (ModuleNotFoundError)

- [ ] **Step 3: 实现 code_reader.py**

`src/assessgen/assessment/code_reader.py`:
```python
"""代码聚合器 - 把学生代码路径聚合成带行号、可截断的文本。"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from loguru import logger

MAX_LINES_PER_FILE = 800

# 包含的代码扩展名
_CODE_EXTENSIONS = frozenset({
    ".html", ".css", ".js", ".jsx", ".ts", ".tsx", ".vue", ".py",
})

# 排除的目录名
_EXCLUDED_DIRS = frozenset({
    "node_modules", ".venv", "venv", "__pycache__", ".git",
    "dist", "build", ".next", "target", "vendor", ".idea", ".vscode",
})

# 排除的文件名
_EXCLUDED_FILES = frozenset({
    "package-lock.json", "yarn.lock", "pnpm-lock.yaml", "uv.lock",
})


@dataclass(frozen=True)
class FileMeta:
    """单个文件的元信息。"""
    path: str
    lines: int
    truncated: bool


@dataclass(frozen=True)
class CodeAggregation:
    """聚合后的代码文本 + 文件元信息。"""
    text: str
    files: list[FileMeta]


def _is_excluded(path: Path, is_dir: bool = False) -> bool:
    """判断路径是否应被排除。"""
    if is_dir:
        return path.name in _EXCLUDED_DIRS
    if path.name.startswith("."):
        return True
    if path.name in _EXCLUDED_FILES:
        return True
    if path.name.endswith(".min.js") or path.name.endswith(".min.css"):
        return True
    return False


def _read_single_file(path: Path) -> tuple[FileMeta, str] | None:
    """读取单个文件，返回元信息和带行号文本；二进制/读取失败返回 None。"""
    try:
        content = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        logger.warning(f"跳过二进制文件: {path}")
        return None
    except OSError as e:
        logger.warning(f"读取失败 {path}: {e}")
        return None

    all_lines = content.splitlines()
    total_lines = len(all_lines)
    truncated = total_lines > MAX_LINES_PER_FILE
    shown = all_lines[:MAX_LINES_PER_FILE]

    numbered = "\n".join(f"{i + 1:>4}: {line}" for i, line in enumerate(shown))
    if truncated:
        numbered += f"\n... (已截断 {total_lines - MAX_LINES_PER_FILE} 行)"

    rel_path = str(path) if path.is_absolute() else path.name
    meta = FileMeta(path=rel_path, lines=total_lines, truncated=truncated)
    return meta, numbered


def _collect_code_files(root: Path) -> list[Path]:
    """递归收集所有代码文件（已排序、已排除）。"""
    files: list[Path] = []
    for path in sorted(root.rglob("*")):
        if path.is_dir():
            continue
        # 检查是否在排除目录内
        if any(part in _EXCLUDED_DIRS for part in path.parts):
            continue
        if _is_excluded(path):
            continue
        if path.suffix.lower() in _CODE_EXTENSIONS:
            files.append(path)
    return files


def read_code(path: str) -> CodeAggregation:
    """读取代码路径（文件或目录），返回聚合结果。

    Raises:
        ValueError: 路径不存在或没有可识别的代码文件
    """
    root = Path(path)
    if not root.exists():
        raise ValueError(f"路径不存在: {path}")

    # 单文件输入：跳过扩展名/排除规则
    if root.is_file():
        result = _read_single_file(root)
        if result is None:
            raise ValueError(f"无法读取文件: {path}")
        meta, numbered = result
        header = f"=== {meta.path} ({meta.lines} 行) ==="
        if meta.truncated:
            header = f"=== {meta.path} ({meta.lines} 行, 截断展示前 {MAX_LINES_PER_FILE} 行) ==="
        text = f"{header}\n{numbered}\n"
        return CodeAggregation(text=text, files=[meta])

    # 目录输入：收集 + 聚合
    code_files = _collect_code_files(root)
    if not code_files:
        raise ValueError(f"路径下没有可识别的代码文件: {path}")

    metas: list[FileMeta] = []
    blocks: list[str] = []
    for f in code_files:
        result = _read_single_file(f)
        if result is None:
            continue
        meta, numbered = result
        # 相对路径
        try:
            rel = f.relative_to(root)
            meta = FileMeta(path=str(rel).replace("\\", "/"), lines=meta.lines, truncated=meta.truncated)
        except ValueError:
            pass
        metas.append(meta)
        header = f"=== {meta.path} ({meta.lines} 行) ==="
        if meta.truncated:
            header = f"=== {meta.path} ({meta.lines} 行, 截断展示前 {MAX_LINES_PER_FILE} 行) ==="
        blocks.append(f"{header}\n{numbered}\n")

    if not metas:
        raise ValueError(f"路径下没有可识别的代码文件: {path}")

    return CodeAggregation(text="\n".join(blocks), files=metas)
```

- [ ] **Step 4: 运行测试验证通过**

Run: `uv run pytest tests/assessment/test_code_reader.py -v`
Expected: 11 passed

- [ ] **Step 5: Commit**

```bash
git add src/assessgen/assessment/code_reader.py tests/assessment/test_code_reader.py
git commit -m "feat(assessment): 实现 code_reader 代码聚合器（带行号+截断）"
```

---

## Task 4: prompts.py（TDD）

**Files:**
- Create: `src/assessgen/assessment/prompts.py`
- Test: `tests/assessment/test_prompts.py`

- [ ] **Step 1: 写失败测试**

`tests/assessment/test_prompts.py`:
```python
"""prompt builder 测试。"""
from assessgen.assessment.code_reader import CodeAggregation, FileMeta
from assessgen.assessment.models import DiagnosisReport, FileEntry, KnowledgeCoverage, Suspicion
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
```

- [ ] **Step 2: 运行测试验证失败**

Run: `uv run pytest tests/assessment/test_prompts.py -v`
Expected: FAIL (ModuleNotFoundError)

- [ ] **Step 3: 实现 prompts.py**

`src/assessgen/assessment/prompts.py`:
```python
"""双调用 LLM prompt 构建器。

两个纯函数，输入确定输出确定，可 TDD。
两次调用都喂完整代码文本（接受 code token 翻倍以换取问题质量）。
"""
from __future__ import annotations

import json
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
```

- [ ] **Step 4: 运行测试验证通过**

Run: `uv run pytest tests/assessment/test_prompts.py -v`
Expected: 14 passed

- [ ] **Step 5: Commit**

```bash
git add src/assessgen/assessment/prompts.py tests/assessment/test_prompts.py
git commit -m "feat(assessment): 实现双调用 prompt 构建器"
```

---

## Task 5: renderer.py（TDD）

**Files:**
- Create: `src/assessgen/assessment/renderer.py`
- Test: `tests/assessment/test_renderer.py`

- [ ] **Step 1: 写失败测试**

`tests/assessment/test_renderer.py`:
```python
"""MD 渲染器测试。"""
from assessgen.assessment.models import (
    DiagnosisReport, FileEntry, KnowledgeCoverage, Question, QuestionSet, Suspicion,
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
        "l1": l1 or [{"code_location": "main.js", "text": "数据流是怎样的？"}],
        "l2": l2 or [{"code_location": "stores/todo.js", "text": "为什么用 Pinia？"}],
        "l3": l3 or [{"code_location": "main.js:6", "text": "删掉 router 会怎样？"}],
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
```

- [ ] **Step 2: 运行测试验证失败**

Run: `uv run pytest tests/assessment/test_renderer.py -v`
Expected: FAIL (ModuleNotFoundError)

- [ ] **Step 3: 实现 renderer.py**

`src/assessgen/assessment/renderer.py`:
```python
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
```

- [ ] **Step 4: 运行测试验证通过**

Run: `uv run pytest tests/assessment/test_renderer.py -v`
Expected: 13 passed

- [ ] **Step 5: Commit**

```bash
git add src/assessgen/assessment/renderer.py tests/assessment/test_renderer.py
git commit -m "feat(assessment): 实现 MD 报告渲染器"
```

---

## Task 6: runner.py（TDD with mock）

**Files:**
- Create: `src/assessgen/assessment/runner.py`
- Test: `tests/assessment/test_runner.py`

- [ ] **Step 1: 写失败测试**

`tests/assessment/test_runner.py`:
```python
"""runner 编排 + 重试测试。"""
from unittest.mock import patch

import pytest
from pydantic import ValidationError

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
```

- [ ] **Step 2: 运行测试验证失败**

Run: `uv run pytest tests/assessment/test_runner.py -v`
Expected: FAIL (ModuleNotFoundError)

- [ ] **Step 3: 实现 runner.py**

`src/assessgen/assessment/runner.py`:
```python
"""编排层 - 串联 code_reader -> 双 LLM 调用 -> renderer。"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from loguru import logger
from pydantic import BaseModel, ValidationError

from assessgen.assessment.code_reader import CodeAggregation, read_code
from assessgen.assessment.models import DiagnosisReport, QuestionSet
from assessgen.assessment.prompts import Prompt, build_diagnosis_prompt, build_questions_prompt
from assessgen.assessment.renderer import ReportMeta, render_report
from assessgen.llm import LLMConfig, call_llm

_SOFT_CHAR_LIMIT = 80_000


@dataclass(frozen=True)
class AssessmentResult:
    """评估完整结果。"""
    markdown: str
    diagnosis: DiagnosisReport
    questions: QuestionSet


def _warn_if_huge(agg: CodeAggregation) -> None:
    """代码过大时软告警。"""
    if len(agg.text) > _SOFT_CHAR_LIMIT:
        logger.warning(
            f"代码聚合后 {len(agg.text)} 字符（约 {len(agg.text) // 4} tokens），"
            f"可能接近模型上下文上限，输出质量可能下降。"
        )


def _validate_or_retry(
    raw: dict,
    model_cls: type,
    config: LLMConfig,
    prompt: Prompt,
):
    """model_validate；失败重试 1 次；仍失败抛 ValueError。"""
    try:
        return model_cls.model_validate(raw)
    except ValidationError as e:
        logger.warning(f"LLM 输出 schema 校验失败，重试 1 次: {e}")
        raw2 = call_llm(prompt.system, prompt.user, config)
        try:
            return model_cls.model_validate(raw2)
        except ValidationError as e2:
            raise ValueError(
                f"LLM 两次输出均不符合 schema。最后一次错误: {e2}"
            ) from e2


def run_assessment(
    code_path: str,
    context: str | None,
    config: LLMConfig,
) -> AssessmentResult:
    """完整评估流程：读代码 -> 诊断 -> 出题 -> 渲染。"""
    # 1. 读代码
    agg = read_code(code_path)

    # 2. 软告警
    _warn_if_huge(agg)

    # 3. 调用 1：诊断
    p1 = build_diagnosis_prompt(agg, context)
    raw1 = call_llm(p1.system, p1.user, config)
    diagnosis = _validate_or_retry(raw1, DiagnosisReport, config, p1)

    # 4. 调用 2：出题
    p2 = build_questions_prompt(diagnosis, agg, context)
    raw2 = call_llm(p2.system, p2.user, config)
    questions = _validate_or_retry(raw2, QuestionSet, config, p2)

    # 5. 渲染
    meta = ReportMeta(
        code_path=code_path,
        generated_at=datetime.now().isoformat(timespec="minutes"),
        context=context,
    )
    markdown = render_report(diagnosis, questions, meta)

    return AssessmentResult(markdown=markdown, diagnosis=diagnosis, questions=questions)
```

- [ ] **Step 4: 运行测试验证通过**

Run: `uv run pytest tests/assessment/test_runner.py -v`
Expected: 5 passed

- [ ] **Step 5: 全量测试回归**

Run: `uv run pytest tests/ -v`
Expected: 全部 passed（models 7 + code_reader 11 + prompts 14 + renderer 13 + runner 5 = 50）

- [ ] **Step 6: Commit**

```bash
git add src/assessgen/assessment/runner.py tests/assessment/test_runner.py
git commit -m "feat(assessment): 实现编排层（双调用+重试+软告警）"
```

---

## Task 7: CLI 命令 + 注册

**Files:**
- Create: `src/assessgen/commands/code.py`
- Modify: `src/assessgen/cli.py`

- [ ] **Step 1: 实现 commands/code.py**

`src/assessgen/commands/code.py`:
```python
"""cagen code 命令 - CLI 薄壳。"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from loguru import logger
import typer

from assessgen.assessment.runner import run_assessment
from assessgen.llm import resolve_llm_config

# code 命令默认温度低于 llm.py 的 0.7：结构化 JSON 需更低温度
_DEFAULT_CODE_TEMPERATURE = 0.5


def code_cmd(
    path: Path = typer.Argument(exists=True, help="学生代码路径（文件或目录）"),
    context: Optional[str] = typer.Option(
        None, "--context", "-c", help="背景信息文本"
    ),
    output: Optional[Path] = typer.Option(
        None, "--output", "-o", help="输出 MD 文件路径"
    ),
    api_key: Optional[str] = typer.Option(
        None, "--api-key", help="覆盖 OPENAI_API_KEY"
    ),
    base_url: Optional[str] = typer.Option(
        None, "--api-base", help="覆盖 OPENAI_BASE_URL"
    ),
    model: Optional[str] = typer.Option(
        None, "--model", help="覆盖 ASSESSGEN_MODEL"
    ),
    temperature: Optional[float] = typer.Option(
        None, "--temperature", help="生成温度（默认 0.5）"
    ),
):
    """分析学生代码，生成分层答辩问题 + 诊断报告（MD）。"""
    resolved_temp = temperature if temperature is not None else _DEFAULT_CODE_TEMPERATURE
    try:
        config = resolve_llm_config(api_key, base_url, model, resolved_temp)
    except ValueError as e:
        logger.error(str(e))
        raise typer.Exit(1)

    try:
        result = run_assessment(str(path), context, config)
    except ValueError as e:
        logger.error(f"评估失败: {e}")
        raise typer.Exit(1)

    if output:
        output.write_text(result.markdown, encoding="utf-8")
        logger.info(f"报告已写入: {output}")
    else:
        typer.echo(result.markdown)
```

- [ ] **Step 2: 注册到 cli.py**

在 `src/assessgen/cli.py` 中：

1. 在 import 区（第 8-12 行附近）加：
```python
from assessgen.commands.code import code_cmd
```

2. 在 `app.command("import")(import_cmd)` 之后加：
```python
app.command("code")(code_cmd)
```

- [ ] **Step 3: 验证命令注册**

Run: `uv run cagen --help`
Expected: 输出含 `code` 命令

- [ ] **Step 4: 验证 code 子命令 help**

Run: `uv run cagen code --help`
Expected: 显示 PATH 参数 + 全部选项（--context/--output/--api-key/--api-base/--model/--temperature）

- [ ] **Step 5: 验证缺 API key 报错**

Run: `$env:OPENAI_API_KEY=""; uv run cagen code tests/fixtures/sample_student_code`
Expected: 错误退出 + "缺少 OPENAI_API_KEY" 中文报错

- [ ] **Step 6: Commit**

```bash
git add src/assessgen/commands/code.py src/assessgen/cli.py
git commit -m "feat(cli): 注册 cagen code 命令"
```

---

## Task 8: 集成验证

**Files:** 无新建，仅运行验证

- [ ] **Step 1: 全量测试**

Run: `uv run pytest tests/ -v`
Expected: 全部 passed（50 tests）

- [ ] **Step 2: LSP 诊断**

Run: 对 `src/assessgen/assessment/` 和 `src/assessgen/commands/code.py` 运行 lsp_diagnostics
Expected: 无 error

- [ ] **Step 3: 手动 smoke test（需真实 API key）**

前提：环境变量 `OPENAI_API_KEY` 已设置

Run: `uv run cagen code tests/fixtures/sample_student_code -c "第6周作业，学过 Vue Router 和 Pinia" -o test_report.md`
Expected:
- 生成 `test_report.md` 文件
- 文件含 `# 学生代码评估报告` 标题
- 含 📋/🔍/📝 三个章节
- 含 L1/L2/L3 三层问题
- 问题引用了具体文件名

- [ ] **Step 4: 检查输出报告质量**

人工审阅 `test_report.md`：
- L2 问题是否考"为什么"（非"是什么"）
- L3 问题是否考"如果改"
- 诊断是否标记了 `utils/request.js` 的 axios 拦截器为超纲

- [ ] **Step 5: 清理 smoke test 产物**

```bash
rm test_report.md
```

- [ ] **Step 6: 最终全量回归**

Run: `uv run pytest tests/ -v`
Expected: 全部 passed

---

## 验收标准对照

| 验收项 | 对应 Task | 验证方式 |
|---|---|---|
| `cagen code <dir>` 跑通输出 MD | Task 8 Step 3 | smoke test |
| `pytest tests/` 全绿 | Task 8 Step 1/6 | 50 tests passed |
| 手动 smoke test 问题质量 | Task 8 Step 4 | 人工审阅 |
| `cagen code --help` 完整 | Task 7 Step 4 | help 输出 |
| 缺 API key 中文报错 | Task 7 Step 5 | 错误退出 |
