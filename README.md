# CourseAssessGen

学生代码评估工具 - AI 时代的"懂不懂自己写的东西"验证器。

面向教师，从"评估产出物"转向"评估理解深度"：让 LLM 分析学生提交的代码，自动生成分层答辩问题 + 诊断报告，供教师面谈时验证学生是否真正理解自己的提交物。

## 安装

```bash
# 需要 Python 3.12+
uv sync
```

## 配置

在项目根目录创建 `.env` 文件（已被 .gitignore 排除）：

```env
OPENAI_API_KEY=你的API密钥
# 可选覆盖（默认值如下）：
# OPENAI_BASE_URL=https://open.bigmodel.cn/api/paas/v4
# ASSESSGEN_MODEL=glm-4-flash
```

也可通过命令行参数 `--api-key` / `--api-base` / `--model` 临时覆盖。

## 命令一览

| 命令 | 用途 |
|---|---|
| `cagen code` | 学生代码 -> 答辩问题 + 诊断报告 MD（核心功能） |
| `cagen exercise` | 教案 JSON -> 题库 JSON（LLM 出题） |
| `cagen render` | JSON -> 教学文档（xlsx 等） |
| `cagen validate` | 校验 JSON 文件的 schema |
| `cagen import` | xlsx -> JSON 互转 |
| `cagen list-presets` | 列出可用预设 |
| `cagen show <name>` | 显示预设详情 |

## `cagen code` 用法

分析学生提交的代码，双次 LLM 调用生成**分层答辩问题 + 诊断报告**，输出一份 Markdown。

### 基本用法

```bash
# 输出到终端
cagen code ./student-001/

# 输出到文件
cagen code ./student-001/ -o report.md

# 附带背景信息（让 LLM 判断更精准）
cagen code ./student-001/ -c "第6周作业，学过 Vue Router 和 Pinia，要求做 Todo 应用" -o report.md
```

### 参数

| 参数 | 说明 |
|---|---|
| `PATH` | 学生代码路径（文件或目录），必填 |
| `--context` `-c` | 背景信息文本（可选）。控制不超纲、对齐作业要求 |
| `--output` `-o` | 输出 MD 文件路径（可选，默认输出到终端） |
| `--api-key` | 覆盖 `OPENAI_API_KEY` |
| `--api-base` | 覆盖 `OPENAI_BASE_URL` |
| `--model` | 覆盖 `ASSESSGEN_MODEL` |
| `--temperature` | 生成温度（默认 0.5） |

### 支持的代码语言

`.html` `.css` `.js` `.jsx` `.ts` `.tsx` `.vue` `.py`

### 报告内容

报告包含三部分：

1. **提交物概述** - 文件清单、代码总量、涉及知识点
2. **诊断分析** - 知识点覆盖状态（✅确认 / ⚠️存疑 / ❌未体现）+ 疑点标记
3. **答辩问题清单** - 三层问题：
   - **L1 理解确认** - 考"代码做了什么"（摸底）
   - **L2 决策追问** - 考"为什么这么写"（区分 AI 代写）
   - **L3 变体假设** - 考"如果改了会怎样"（验证内化）

## 其他命令

### `cagen exercise`

根据教案 JSON，通过 LLM 生成练习题。

```bash
cagen exercise lesson-plan.json -p exercise-chaoxing -o exercises.json
cagen exercise lesson-plan.json -p exercise-chaoxing --instructions "侧重考察 Pinia 的实际使用场景"
```

### `cagen render`

将 JSON 渲染为教学文档。

```bash
cagen render content.json -p exercise-chaoxing -o output.xlsx
```

### `cagen validate`

校验 JSON 文件是否符合预设的 schema。

```bash
cagen validate content.json -p exercise-chaoxing
```

### `cagen import`

将 xlsx 转为 JSON。

```bash
cagen import schedule.xlsx -p exercise-chaoxing -o schedule.json
```

## 开发

```bash
# 安装开发依赖（含 pytest）
uv sync --dev

# 运行测试
uv run pytest tests/ -v

# 直接运行（开发模式）
uv run cagen code ./some-code/
# 或
python main.py code ./some-code/
```

## 项目结构

```
src/assessgen/
├── cli.py                  # CLI 入口（Typer）
├── llm.py                  # LLM 调用基础设施
├── commands/               # CLI 命令
│   ├── code.py             # 学生代码评估
│   ├── exercise.py         # 教案出题
│   ├── render.py           # 文档渲染
│   ├── validate.py         # JSON 校验
│   └── import_cmd.py       # xlsx↔JSON 互转
├── assessment/             # code 命令领域逻辑（内聚子包）
│   ├── models.py           # pydantic 数据模型
│   ├── code_reader.py      # 代码聚合（带行号+截断）
│   ├── prompts.py          # 双调用 prompt 构建
│   ├── renderer.py         # MD 报告渲染
│   └── runner.py           # 编排（双调用+重试）
├── presets/                # 预设加载
├── renderers/              # 渲染器
├── schemas/                # 数据校验
└── utils/                  # 工具函数
```

## 设计文档

- [`docs/设计文档.md`](docs/设计文档.md) - 项目整体设计
- [`docs/Phase2-code-design.md`](docs/Phase2-code-design.md) - `cagen code` 命令设计 spec
