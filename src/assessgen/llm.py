"""LLM 调用与 API 配置解析 — 被 exercise 和 code 评估共用。"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from typing import Optional

from loguru import logger

_DEFAULT_BASE_URL = "https://open.bigmodel.cn/api/paas/v4"
_DEFAULT_MODEL = "glm-4-flash"
_DEFAULT_TEMPERATURE = 0.7


@dataclass(frozen=True)
class LLMConfig:
    api_key: str
    base_url: str
    model: str
    temperature: float


def resolve_llm_config(
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    model: Optional[str] = None,
    temperature: Optional[float] = None,
) -> LLMConfig:
    """按 CLI 参数 > 环境变量 > 默认值 的优先级解析配置。

    Raises:
        ValueError: 当 api_key 在所有来源都缺失时
    """
    resolved_key = api_key or os.environ.get("OPENAI_API_KEY")
    if not resolved_key:
        raise ValueError(
            "缺少 OPENAI_API_KEY。请通过 --api-key 传入，或在 .env / 环境变量中设置 OPENAI_API_KEY。"
        )

    resolved_base = base_url or os.environ.get("OPENAI_BASE_URL") or _DEFAULT_BASE_URL
    resolved_model = model or os.environ.get("ASSESSGEN_MODEL") or _DEFAULT_MODEL
    resolved_temp = temperature if temperature is not None else _DEFAULT_TEMPERATURE

    return LLMConfig(
        api_key=resolved_key,
        base_url=resolved_base,
        model=resolved_model,
        temperature=resolved_temp,
    )


def build_exercise_prompt(
    example: dict,
    generate_rules: Optional[str] = None,
    instructions: Optional[str] = None,
    material_desc: str = "教案 JSON",
    material_hint: str = "教案包含教学目标、重难点、教学环节等信息，出题应覆盖这些知识点，题目内容要贴合教学实际。",
) -> str:
    """构建习题生成的 system prompt。

    与 build_system_prompt 平行，但任务语义不同：
    - 输入是出题素材（教案 JSON 或授课讲稿文本，由 material_desc/hint 描述）
    - 输出是符合 example 结构的 exercises.json

    五层结构（优先级从低到高）：
    1. 角色 + 任务说明
    2. 题型与字段规则
    3. example.json 结构示例
    4. preset 的 generate_rules
    5. 用户 --instructions（优先级最高）
    """
    example_json = json.dumps(example, ensure_ascii=False, indent=2)
    sections = [
        "你是一名经验丰富的出题专家。",
        f"请根据用户提供的{material_desc}，生成配套的课堂练习和课后习题。",
        "",
        material_hint,
        "",
        "题型与字段规则：",
        "1. type 只能从以下 6 种中选择：single_choice、multiple_choice、fill_blank、true_false、short_answer、reading_comprehension。",
        "2. single_choice / multiple_choice：必须提供 options（2-8 个），answer 是字母数组，如 [\"B\"] 或 [\"B\",\"C\",\"D\"]。",
        "3. fill_blank：无 options，answer 是各空答案数组，如 [\"type\"]。题干中空位用 ___ 表示。",
        "4. true_false：options 固定为 [\"正确\",\"错误\"]，answer 用 [\"A\"]（正确）或 [\"B\"]（错误）。",
        "5. short_answer：无 options，answer 是 [\"答案全文\"]。",
        "6. reading_comprehension：大题无 options/answer，必须包含 sub_questions 数组。每个小题是上述 5 种独立题型之一（不再嵌套）。大题的 difficulty/knowledge_points/tags 适用于所有小题。",
        "7. id 按顺序编号 Q1、Q2...，阅读理解小题用 Q6.1、Q6.2 格式。",
        "8. difficulty 取值：easy / medium / hard。",
        "9. scene 取值：classroom（课堂）/ after_class（课后）。",
        "10. 输出必须是合法的 JSON，且结构与下面的示例完全一致。只输出 JSON 本身，不要任何 Markdown 标记或解释。",
        "",
        "结构示例：",
        example_json,
    ]

    if generate_rules:
        sections.extend([
            "",
            "preset 默认生成规则（来自 config.generate_rules）：",
            generate_rules.strip(),
        ])

    if instructions:
        sections.extend([
            "",
            "用户自定义指令（优先级最高，与上述规则冲突时以此为准）：",
            instructions.strip(),
        ])

    return "\n".join(sections) + "\n"


def extract_json(text: str) -> dict:
    """从 LLM 响应中提取 JSON。

    支持 3 种情况：
    1. 纯 JSON 文本
    2. ```json ... ``` 代码块包裹
    3. ``` ... ``` 代码块包裹
    """
    stripped = text.strip()

    # 优先尝试 fenced code block
    fence_match = re.search(r"```(?:json)?\s*\n(.*?)\n```", stripped, re.DOTALL)
    if fence_match:
        stripped = fence_match.group(1).strip()

    try:
        return json.loads(stripped)
    except json.JSONDecodeError as e:
        # 兜底：定位最外层 { }
        first = stripped.find("{")
        last = stripped.rfind("}")
        if first != -1 and last != -1 and last > first:
            candidate = stripped[first : last + 1]
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                pass
        raise ValueError(f"无法从 LLM 响应中解析出 JSON: {e}") from e


def call_llm(system_prompt: str, user_text: str, config: LLMConfig) -> dict:
    """调用 LLM 并返回解析后的 dict。"""
    from openai import OpenAI

    client = OpenAI(api_key=config.api_key, base_url=config.base_url)

    logger.info(f"调用 LLM: model={config.model}, base_url={config.base_url}")
    response = client.chat.completions.create(
        model=config.model,
        temperature=config.temperature,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_text},
        ],
    )
    raw = response.choices[0].message.content or ""
    logger.debug(f"LLM 原始响应（前 200 字符）: {raw[:200]}")
    return extract_json(raw)
