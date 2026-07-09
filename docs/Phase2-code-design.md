# Phase 2 · `cagen code` 命令设计 spec

> **范围：** 实现 `cagen code` 命令（学生代码 -> 答辩问题 + 诊断报告 MD）
> **基础：** `docs/设计文档.md` 仅作方向性参考，本 spec 是 Phase 2 的权威设计
> **创建日期：** 2026-07-09
> **状态：** 待用户审阅

---

## 一、已锁定的决策（brainstorming 产出）

| # | 决策 | 选择 |
|---|---|---|
| 1 | 如何对待 `docs/设计文档.md` | 重新整体设计 Phase 2，原文档只作方向参考 |
| 2 | 主价值 | 答辩问题与诊断报告两者并重，接受更高成本 |
| 3 | 语言范围 | HTML / CSS / JS / Python / Vue（含 TS，因常与 Vue 共存） |
| 4 | LLM 调用策略 | 双次调用：先诊断（code -> diagnosis JSON），后出题（diagnosis + code -> questions JSON） |
| 5 | JSON 契约保证 | pydantic v2 模型 + `extract_json` + `model_validate` |
| 6 | code_reader 聚合格式 | 带行号输出 + 单文件超阈值行截断 |
| 7 | 测试策略 | 纯函数 TDD + LLM 薄包装 mock |

---

## 二、架构总览

### 模块组织：方案 B · 内聚 assessment 子包

code 命令的全部领域逻辑收入 `src/assessgen/assessment/` 子包，`commands/code.py` 退化为薄 CLI 壳。理由：领域逻辑高内聚、自包含、可整体单测；Phase 3 batch 可直接复用 `assessment.runner`。

```
src/assessgen/
├── cli.py                          # +1 行注册 code 命令
├── llm.py                          # 不改动，复用 resolve_llm_config / call_llm / extract_json
├── commands/
│   └── code.py                     # 【新】薄 CLI 壳：参数解析 -> 调 runner -> 输出
└── assessment/                     # 【新子包】code 命令的全部领域逻辑
    ├── __init__.py
    ├── models.py                   # pydantic 模型（DiagnosisReport / QuestionSet 等）
    ├── code_reader.py              # 代码聚合（带行号 + 截断）
    ├── prompts.py                  # 两个 prompt builder（diagnosis / questions）
    ├── renderer.py                 # MD 渲染
    └── runner.py                   # 编排：双调用 + 模型验证 + 渲染
```

### 数据流

```
学生代码路径
    │
    ▼
code_reader.read_code(path) -> CodeAggregation(text, files)
    │
    ├─ build_diagnosis_prompt(agg, context) -> Prompt
    │       │
    │       ▼ call_llm (第 1 次)
    │   raw dict -> DiagnosisReport.model_validate -> diagnosis
    │
    ├─ build_questions_prompt(diagnosis, agg, context) -> Prompt
    │       │
    │       ▼ call_llm (第 2 次)
    │   raw dict -> QuestionSet.model_validate -> questions
    │
    ├─ ReportMeta(code_path, now, context)
    │
    ▼
render_report(diagnosis, questions, meta) -> markdown str
    │
    ▼
AssessmentResult(markdown, diagnosis, questions)
```

两次 LLM 调用都接收完整代码文本（`agg.text`），代价是代码部分 token 翻倍，但确保调用 2 能精确引用行号、设计 L3 变体假设题。用户已接受高成本。

---

## 三、§1 数据模型（`assessment/models.py`）

双调用产生两份 JSON，各自一个 pydantic v2 模型。所有枚举字段用 `Literal` 强类型化（parse-don't-validate）。LLM 输出经 `extract_json` -> `model_validate` 解析。

### 调用 1 产出：`DiagnosisReport`

```python
from pydantic import BaseModel, Field
from typing import Literal

class FileEntry(BaseModel):
    path: str                    # 相对路径，如 "stores/todo.js"
    lines: int                   # 行数
    description: str             # 一句话说明

class KnowledgeCoverage(BaseModel):
    name: str                    # 知识点名，如 "Vue Router 基础路由"
    status: Literal["confirmed", "suspicious", "missing"]   # ✅ / ⚠️ / ❌
    note: str                    # 判断依据

class Suspicion(BaseModel):
    kind: Literal[
        "style_shift",           # 风格突变
        "out_of_scope",          # 超出课程范围
        "over_comment",          # 过度注释
        "abnormal_complexity",   # 异常复杂
        "ai_trace",              # AI 痕迹
    ]
    location: str                # "stores/todo.js:45-60" 或 "App.vue / defineStore"
    description: str

class DiagnosisReport(BaseModel):
    files: list[FileEntry]
    total_lines: int
    knowledge_points: list[str]              # 涉及知识点（短词清单）
    coverage: list[KnowledgeCoverage]        # 覆盖状态表
    suspicions: list[Suspicion]              # 疑点标记
```

### 调用 2 产出：`QuestionSet`

```python
class Question(BaseModel):
    code_location: str           # 引用位置，如 "stores/todo.js:12" 或 "App.vue"
    text: str                    # 题目正文

class QuestionSet(BaseModel):
    l1: list[Question] = Field(description="理解确认 · 摸底")
    l2: list[Question] = Field(description="决策追问 · 区分真假")
    l3: list[Question] = Field(description="变体假设 · 验证内化")
```

### 设计取舍

| 决策 | 选择 | 理由 |
|---|---|---|
| status / kind 用 `Literal` 枚举 | 是 | 值有限且明确，prompt 列出允许值；强类型让 renderer 可安全字典查找 |
| 题量不做 schema 约束（2-3 题） | 不约束 | 题量是 prompt 指引而非结构契约；强约束会让 LLM 输出验证失败需重试 |
| 不加 `intent`/`reasoning` 字段 | 不加 | YAGNI；MD 模板无此列，教师只需题目本身 |
| `code_location` 用自由 string | 是 | LLM 产出的位置格式多样（行号/函数名/全局），枚举反而限制 |
| schema 校验失败 | 重试 1 次，仍失败抛 `ValueError` | 单次重试吸收 LLM 抽风；不无限重试避免烧 token |

---

## 四、§2 code_reader（`assessment/code_reader.py`）

**职责**：把学生代码路径（文件或目录）聚合成带行号、可截断的文本。纯函数，可用 tmp 目录 TDD。

### 返回类型

```python
from dataclasses import dataclass

@dataclass(frozen=True)
class FileMeta:
    path: str            # 相对路径
    lines: int           # 实际行数（截断前）
    truncated: bool      # 是否被截断

@dataclass(frozen=True)
class CodeAggregation:
    text: str            # 聚合后的带行号文本
    files: list[FileMeta]
```

### 函数签名

```python
def read_code(path: str) -> CodeAggregation: ...
```

### 聚合文本格式

```
=== stores/todo.js (45 行) ===
   1: import { defineStore } from 'pinia'
   2: 
   3: export const useTodoStore = defineStore('todo', () => {
  ...
  45: })
=== App.vue (80 行) ===
   1: <template>
   ...
=== main.js (1200 行, 截断展示前 800 行) ===
   1: import { createApp } from 'vue'
   ...
 800: app.use(router)
... (已截断 400 行)
```

### 规则

| 项 | 规则 |
|---|---|
| 包含扩展名 | `.html` `.css` `.js` `.jsx` `.ts` `.tsx` `.vue` `.py` |
| 排除目录 | `node_modules` `.venv` `venv` `__pycache__` `.git` `dist` `build` `.next` `target` `vendor` `.idea` `.vscode` |
| 排除文件 | 以 `.` 开头的隐藏文件；`package-lock.json` `yarn.lock` `pnpm-lock.yaml` `uv.lock`；`*.min.js` / `*.min.css` |
| 行号格式 | 右对齐 4 位宽，`{n:>4}: {line}` |
| 单文件阈值 | `MAX_LINES_PER_FILE = 800`（模块常量） |
| 截断策略 | 保留前 800 行 + 追加 `... (已截断 N 行)`；不做摘要 |
| 目录遍历 | 按路径名排序，确保输出稳定（相同输入 -> 相同文本） |
| 空目录/无代码文件 | 抛 `ValueError("路径下没有可识别的代码文件: ...")` |
| 单文件输入 | PATH 是文件时，跳过扩展名/排除规则，直接处理该文件 |

### 边界情况

- **二进制文件**：扩展名命中但读取时 `UnicodeDecodeError` -> 跳过 + `logger.warning`，不中断
- **超大目录**：不设硬上限，`text` 总长度由 runner 软告警兜底
- **空文件**：`lines=0`，仍列出但内容为空

### 与 §1 的衔接

`CodeAggregation.files` 的 `path`/`lines` 与 `DiagnosisReport.files` 的 `FileEntry` 字段对齐。调用 1 的 prompt 会附带 `files` 元信息清单，让 LLM 直接引用准确的文件名/行数，不用自己数。

---

## 五、§3 prompts（`assessment/prompts.py`）

**职责**：为两次 LLM 调用各自构建 `(system_prompt, user_text)`。纯函数，输入确定输出确定，可 TDD。

### 返回类型

```python
from dataclasses import dataclass

@dataclass(frozen=True)
class Prompt:
    system: str
    user: str
```

选 `(system, user)` 元组而非只返 system（现有 `build_exercise_prompt` 的模式），因为两次调用的 user_text 都需组装多个片段，由 prompt 模块独占更内聚，runner 只管调 `call_llm(p.system, p.user, config)`。

### 函数签名

```python
def build_diagnosis_prompt(
    agg: CodeAggregation,
    context: str | None,
) -> Prompt: ...

def build_questions_prompt(
    diagnosis: DiagnosisReport,
    agg: CodeAggregation,
    context: str | None,
) -> Prompt: ...
```

### 调用 1 · `build_diagnosis_prompt`

**system** 结构（5 层，沿用 `build_exercise_prompt` 风格）：
1. 角色：经验丰富的高校教师，正在评估学生代码
2. 任务：分析代码，输出结构化诊断 JSON
3. 输出规则：
   - 严格输出 JSON，无 Markdown 标记
   - 明确列出允许的枚举值：`status ∈ {confirmed, suspicious, missing}`、`kind ∈ {style_shift, out_of_scope, over_comment, abnormal_complexity, ai_trace}`
   - 给出完整 JSON schema（字段名 + 类型 + 含义）
4. 诊断维度说明：
   - 知识点覆盖：✅确认 / ⚠️存疑 / ❌未体现 的判定标准
   - 疑点 5 类的具体定义
   - 措辞原则：疑点是"建议重点关注"非"判定为 AI 生成"
5. `--context` 背景信息（如有）：用于判断"超纲"和"应覆盖未覆盖"

**user** 组装顺序：
```
[背景信息]（如有）
[文件元信息清单]  ← 从 agg.files 生成，如：
  - stores/todo.js (45 行)
  - App.vue (80 行)
  - main.js (1200 行, 已截断展示前 800 行)
[带行号代码全文]  ← agg.text
```

元信息清单的作用：让 LLM 直接引用准确的文件名/行数生成 `DiagnosisReport.files` 和 `total_lines`，不用自己数。

### 调用 2 · `build_questions_prompt`

**system**：
1. 角色：正在为学生的代码提交准备答辩问题的高校教师
2. 任务：基于已完成的诊断报告，生成三层答辩问题
3. L1/L2/L3 哲学（核心，必须显式写入 prompt）：
   - L1 理解确认：考"代码做了什么"，摸底，2-3 题
   - L2 决策追问：考"为什么这么写"，区分 AI 代写，2-3 题
   - L3 变体假设：考"如果改了会怎样"，验证内化，2-3 题
   - **禁止出"是什么"背诵题**（如"Vue 是什么"）
   - 每题必须引用具体代码位置（文件名 + 行号/函数名）
4. 输出规则：JSON schema + 只输出 JSON
5. `--context`（如有）：约束问题不超纲

**user**：
```
[背景信息]（如有）
[诊断报告 JSON]  ← diagnosis.model_dump_json(indent=2)
[带行号代码全文]  ← agg.text（同一份，让 LLM 能精确引用行号）
```

### 可测试性

- `build_diagnosis_prompt(agg, None)` 的 `system` 包含 `"confirmed"`/`"suspicious"`/`"missing"`
- `build_diagnosis_prompt(agg, "第6周")` 的 `user` 以背景信息开头
- `build_questions_prompt(diag, agg, None)` 的 `system` 包含 `"L1"`/`"L2"`/`"L3"` 且提到"禁止背诵题"
- 截断文件的元信息标注"已截断"

### 文件规模

两个 builder 各约 80-100 行，总计约 180 行，低于 250 行上限。

---

## 六、§4 renderer（`assessment/renderer.py`）

**职责**：把 `DiagnosisReport` + `QuestionSet` + 报告元信息渲染成 Markdown 字符串。纯函数，零依赖（无 Jinja2）。

### 输入类型

```python
@dataclass(frozen=True)
class ReportMeta:
    code_path: str          # CLI 的 PATH 参数原值
    generated_at: str       # ISO 时间戳，由 runner 生成
    context: str | None     # --context 原值
```

### 函数签名

```python
def render_report(
    diagnosis: DiagnosisReport,
    questions: QuestionSet,
    meta: ReportMeta,
) -> str: ...
```

不做文件 IO，renderer 只产字符串。

### 输出结构（对齐设计文档 MD 模板）

```markdown
# 学生代码评估报告

> **代码路径：** ./student-001/
> **生成时间：** 2026-07-09 14:30
> **背景信息：** 第6周作业，学过 Vue Router 和 Pinia，要求做 Todo 应用

---

## 📋 提交物概述

| 文件 | 行数 | 说明 |
|------|------|------|
| main.js | 15 | 应用入口 |
| stores/todo.js | 45 | Pinia 状态管理 |

**代码总量：** 288 行 / 5 个文件
**涉及知识点：** Vue Router、Pinia、Composition API、组件通信

---

## 🔍 诊断分析

### 知识点覆盖

| 知识点 | 状态 | 说明 |
|--------|------|------|
| Vue Router 基础路由 | ✅ 确认掌握 | 正确使用 router-link / router-view |
| Pinia 状态管理 | ⚠️ 存疑 | 定义了但使用方式异常复杂 |

### ⚠️ 疑点标记

1. **风格突变**（`App.vue` 第 45-60 行）- 突然使用 computed + watch 组合...
2. **超出课程范围**（`utils/request.js`）- 封装了完整 axios 拦截器...

---

## 📝 答辩问题清单

### L1 · 理解确认

1. **[App.vue]** 你的项目整体数据流是怎样的？...
2. **[stores/todo.js:12]** `defineStore` 做了什么？...

### L2 · 决策追问

1. **[stores/todo.js]** 你用 Pinia 管理待办列表，为什么不用 props/emit？...

### L3 · 变体假设

1. **[router/index.js]** 如果把 `/about` 这条路由删掉...
```

### 枚举 -> 中文显示映射（模块级常量）

```python
_STATUS_DISPLAY = {
    "confirmed":  "✅ 确认掌握",
    "suspicious": "⚠️ 存疑",
    "missing":    "❌ 未体现",
}

_SUSPICION_DISPLAY = {
    "style_shift":         "风格突变",
    "out_of_scope":        "超出课程范围",
    "over_comment":        "过度注释",
    "abnormal_complexity": "异常复杂",
    "ai_trace":            "AI 痕迹",
}
```

因 §1 用 `Literal` 枚举，renderer 可安全字典查找，无 KeyError 风险。

### 渲染规则

| 项 | 规则 |
|---|---|
| 代码位置标注 | 问题前缀 `**[{code_location}]**`，原样使用 LLM 给的位置串 |
| 疑点序号 | 从 1 递增，`kind` 走中文映射，`location` 用反引号包裹 |
| 空列表处理 | 某层问题为空 -> 该节显示"（无）"；`suspicions == []` -> "未发现明显疑点。"；`knowledge_points == []` -> "（未识别到明显知识点）" |
| 背景信息缺失 | `context is None` -> 报告头省略该行 |
| Markdown 转义 | 不转义代码内容（风险低，不做） |

### 文件规模

约 120-150 行，低于 250 行上限。

---

## 七、§5 runner + CLI

### `assessment/runner.py` · 编排层

**职责**：串联 code_reader -> 调用1 -> 调用2 -> renderer，返回完整结果。

#### 返回类型

```python
@dataclass(frozen=True)
class AssessmentResult:
    markdown: str                  # 最终 MD 报告
    diagnosis: DiagnosisReport     # 调用1 解析结果（batch 可复用）
    questions: QuestionSet         # 调用2 解析结果
```

返回模型而不只返 MD 字符串：Phase 3 batch 可能基于 diagnosis 做汇总，现在就暴露模型避免日后返工。

#### 函数签名

```python
def run_assessment(
    code_path: str,
    context: str | None,
    config: LLMConfig,
) -> AssessmentResult: ...
```

#### 编排流程

```
1. agg = read_code(code_path)                    # §2，可能抛 ValueError
2. _warn_if_huge(agg)                            # 软告警
3. p1 = build_diagnosis_prompt(agg, context)     # §3
4. raw1 = call_llm(p1.system, p1.user, config)   # 复用 llm.py
5. diagnosis = validate_or_retry(raw1, DiagnosisReport, config, p1)
6. p2 = build_questions_prompt(diagnosis, agg, context)
7. raw2 = call_llm(p2.system, p2.user, config)
8. questions = validate_or_retry(raw2, QuestionSet, config, p2)
9. meta = ReportMeta(code_path, datetime.now().isoformat(timespec="minutes"), context)
10. md = render_report(diagnosis, questions, meta)   # §4
11. return AssessmentResult(md, diagnosis, questions)
```

#### 验证 + 重试辅助函数

```python
def validate_or_retry(
    raw: dict,
    Model: type,                   # DiagnosisReport | QuestionSet
    config: LLMConfig,
    prompt: Prompt,
):
    """model_validate；失败重试 1 次（重新调 LLM）；仍失败抛 ValueError。"""
    try:
        return Model.model_validate(raw)
    except ValidationError as e:
        logger.warning(f"LLM 输出 schema 校验失败，重试 1 次: {e}")
        raw2 = call_llm(prompt.system, prompt.user, config)
        try:
            return Model.model_validate(raw2)
        except ValidationError as e2:
            raise ValueError(
                f"LLM 两次输出均不符合 schema。最后一次错误: {e2}"
            ) from e2
```

单次重试吸收 LLM 抽风。不无限重试避免烧 token。重试用同一 prompt（不调整参数）。

#### Token 预算软告警

```python
_SOFT_CHAR_LIMIT = 80_000  # 约 20k tokens

def _warn_if_huge(agg: CodeAggregation) -> None:
    if len(agg.text) > _SOFT_CHAR_LIMIT:
        logger.warning(
            f"代码聚合后 {len(agg.text)} 字符（约 {len(agg.text)//4} tokens），"
            f"可能接近模型上下文上限，输出质量可能下降。"
        )
```

不硬失败，让 API 自己拒超长输入。只告警让用户知情。

### `commands/code.py` · CLI 薄壳

```python
import typer
from pathlib import Path
from typing import Optional
from loguru import logger

# code 命令默认温度低于 llm.py 的 0.7：结构化 JSON 输出需更低温度保证稳定性
_DEFAULT_CODE_TEMPERATURE = 0.5

def code_cmd(
    path: Path = typer.Argument(exists=True, help="学生代码路径（文件或目录）"),
    context: Optional[str] = typer.Option(None, "--context", "-c", help="背景信息文本"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="输出 MD 文件路径"),
    api_key: Optional[str] = typer.Option(None, "--api-key", help="覆盖 OPENAI_API_KEY"),
    base_url: Optional[str] = typer.Option(None, "--api-base", help="覆盖 OPENAI_BASE_URL"),
    model: Optional[str] = typer.Option(None, "--model", help="覆盖 ASSESSGEN_MODEL"),
    temperature: Optional[float] = typer.Option(None, "--temperature", help="生成温度（默认 0.5）"),
):
    """分析学生代码，生成分层答辩问题 + 诊断报告（MD）。"""
    resolved_temp = temperature if temperature is not None else _DEFAULT_CODE_TEMPERATURE
    try:
        config = resolve_llm_config(api_key, base_url, model, resolved_temp)
    except ValueError as e:
        logger.error(str(e)); raise typer.Exit(1)

    try:
        result = run_assessment(str(path), context, config)
    except ValueError as e:
        logger.error(f"评估失败: {e}"); raise typer.Exit(1)

    if output:
        output.write_text(result.markdown, encoding="utf-8")
        logger.info(f"报告已写入: {output}")
    else:
        typer.echo(result.markdown)
```

### `cli.py` 注册（一行新增）

```python
from assessgen.commands.code import code_cmd
app.command("code")(code_cmd)
```

### 设计取舍

| 决策 | 选择 | 理由 |
|---|---|---|
| runner 返回 `AssessmentResult`（含模型） | 是 | Phase 3 batch 可复用；测试可断言模型字段 |
| LLM 调用复用现有 `call_llm` 不改 | 不改 | llm.py 是共享基础设施，validation 在 runner 做 |
| 重试策略：单次重试，同 prompt | 是 | 最小干预；不引入退避/参数调整 |
| code 命令默认温度 0.5（非 llm.py 的 0.7） | 是 | 结构化 JSON 输出需更低温度保证稳定性；用户未传 `--temperature` 时用 0.5 |
| `--output` 缺省时 `typer.echo` 全文 | 是 | 用户不指定文件即要终端输出 |
| `--output` 写文件编码 | utf-8 | 中文报告必须；Windows 默认编码会乱码 |
| CLI 错误退出码 | `Exit(1)` | 配置错误/评估失败统一非零退出 |

### 文件规模

- `runner.py`：约 90 行
- `commands/code.py`：约 50 行

---

## 八、§6 测试 + 错误处理

### 测试基础设施

项目当前无 `tests/` 目录、无 pytest 依赖。需新增：

```toml
# pyproject.toml 新增
[dependency-groups]
dev = ["pytest>=8.0.0"]
```

### 测试目录结构

```
tests/
├── conftest.py                       # 共享 fixture
├── assessment/
│   ├── test_models.py                # §1 pydantic 模型
│   ├── test_code_reader.py           # §2 聚合
│   ├── test_prompts.py               # §3 prompt 构建
│   ├── test_renderer.py              # §4 MD 渲染
│   └── test_runner.py                # §5 编排 + 重试
└── fixtures/
    ├── sample_student_code/          # 真实结构的小型 Vue+JS 样例
    │   ├── main.js
    │   ├── App.vue
    │   ├── stores/todo.js
    │   └── utils/request.js
    └── llm_responses/                # 录制的 LLM JSON（合法 + 非法）
        ├── diagnosis_valid.json
        ├── diagnosis_invalid_enum.json
        ├── questions_valid.json
        └── questions_missing_field.json
```

### 各测试文件覆盖范围

| 文件 | 纯函数? | 关键用例 |
|---|---|---|
| `test_models.py` | ✅ | 合法 dict -> `model_validate` 成功；非法 enum -> `ValidationError`；缺必填字段 -> 报错 |
| `test_code_reader.py` | ✅（tmp 目录） | 单文件输入；目录遍历含排序稳定性；排除 `node_modules` 等；行号格式 `   1:`；800 行截断 + 标记；空目录抛 `ValueError`；二进制文件跳过；扩展名过滤 |
| `test_prompts.py` | ✅ | diagnosis prompt 的 system 含 3 个 status 枚举值 + 5 个 kind 枚举值；questions prompt 含 L1/L2/L3 + "禁止背诵题"；context 出现在 user 开头；截断文件元信息标注 |
| `test_renderer.py` | ✅ | 完整报告含所有章节标题；枚举 -> 中文映射正确；空 `suspicions` 渲染"未发现明显疑点"；空 L3 渲染"（无）"；`context=None` 省略背景行；文件表行数正确 |
| `test_runner.py` | mock `call_llm` | 正常流程：两次调用 -> AssessmentResult；首次 schema 失败 -> 重试成功；两次都失败 -> `ValueError`；code_reader 抛错时 runner 透传 |

### `test_runner.py` 的 mock 策略

```python
from unittest.mock import patch

@patch("assessgen.assessment.runner.call_llm")
def test_normal_flow(mock_call_llm):
    mock_call_llm.side_effect = [
        load_fixture("llm_responses/diagnosis_valid.json"),
        load_fixture("llm_responses/questions_valid.json"),
    ]
    result = run_assessment("tests/fixtures/sample_student_code", None, fake_config)
    assert "# 学生代码评估报告" in result.markdown
    assert mock_call_llm.call_count == 2
```

mock 打在 `runner.call_llm`（runner 模块内的引用），不打 `llm.call_llm` 原始位置，确保测的是 runner 的调用编排。

### 错误处理总表

| 来源 | 错误 | 处理 | 用户可见 |
|---|---|---|---|
| code_reader | 路径下无代码文件 | 抛 `ValueError` | CLI 捕获 -> `Exit(1)` + "路径下没有可识别的代码文件: ..." |
| code_reader | 二进制文件 `UnicodeDecodeError` | 跳过 + `logger.warning` | 警告日志，不中断 |
| code_reader | 单文件超 800 行 | 截断 + 标记 | 聚合文本含"... (已截断 N 行)" |
| runner | 聚合文本 > 80k 字符 | `logger.warning` 软告警 | 警告日志，继续执行 |
| llm.py | API key 缺失 | `resolve_llm_config` 抛 `ValueError` | CLI 捕获 -> `Exit(1)` |
| llm.py | 网络错误 / API 报错 | openai SDK 抛异常 | 透传到 CLI -> 异常堆栈 |
| llm.py | 响应非 JSON / 提取失败 | `extract_json` 抛 `ValueError` | 透传到 CLI -> `Exit(1)`（不重试，只对 schema 失败重试） |
| runner | JSON 合法但 schema 不符 | `validate_or_retry` 重试 1 次 | 重试成功：`logger.warning`；仍失败：`ValueError` -> `Exit(1)` |
| CLI | `--output` 父目录不存在 | `write_text` 抛 `FileNotFoundError` | 透传（不自动建目录） |

### 不做的事（YAGNI）

- ❌ 不做 VCR 式真实 LLM 响应录制/回放
- ❌ 不做 LLM 输出的语义质量自动评估（靠手动 smoke test）
- ❌ 不做重试退避策略
- ❌ 不做 `--output` 父目录自动创建
- ❌ 不做异步/并发 LLM 调用（双调用是顺序依赖关系）

---

## 九、验收标准（Phase 2 完成的判定）

1. `cagen code <dir>` 对 `tests/fixtures/sample_student_code/` 跑通，输出符合 MD 模板的报告
2. `pytest tests/` 全绿，覆盖率覆盖 5 个纯函数模块的关键路径
3. 手动 smoke test：用一个真实 Vue 学生作业跑 `cagen code`，人工检查 L2/L3 问题质量（能区分 AI 代写、能验证内化）
4. `cagen code --help` 显示完整选项
5. 缺 `OPENAI_API_KEY` 时给出清晰中文报错

---

## 十、实现文件清单

| 文件 | 类型 | 估行数 |
|---|---|---|
| `src/assessgen/assessment/__init__.py` | 新建 | 1 |
| `src/assessgen/assessment/models.py` | 新建 | ~80 |
| `src/assessgen/assessment/code_reader.py` | 新建 | ~110 |
| `src/assessgen/assessment/prompts.py` | 新建 | ~180 |
| `src/assessgen/assessment/renderer.py` | 新建 | ~140 |
| `src/assessgen/assessment/runner.py` | 新建 | ~90 |
| `src/assessgen/commands/code.py` | 新建 | ~50 |
| `src/assessgen/cli.py` | 改动 | +2 行 |
| `pyproject.toml` | 改动 | +3 行（dev deps） |
| `tests/conftest.py` | 新建 | ~20 |
| `tests/assessment/test_*.py` × 5 | 新建 | ~400 合计 |
| `tests/fixtures/sample_student_code/*` | 新建 | ~250 合计 |
| `tests/fixtures/llm_responses/*.json` × 4 | 新建 | ~150 合计 |

**新增代码总计约 1200 行（含测试与 fixture），生产代码约 650 行。**
