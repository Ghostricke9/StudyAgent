"""
Skills 注册中心 - 管理技能定义和分发

Skills 与 Tools 的区别：
  - Tools: 执行代码逻辑（搜索、抓取、保存文件）
  - Skills: 注入详细提示词引导 LLM 完成复杂任务（编撰教材、出题）

Skill 的调用机制：
  1. LLM 通过 Function Call 决定调用某个 Skill
  2. 注册中心返回该 Skill 的详细提示词
  3. LLM 根据提示词完成内容生成
  4. 生成的内容返回给 Agent 继续处理
"""
import json
import logging
from typing import Any

from skills.knowledge_compiler import COMPILE_KNOWLEDGE_PROMPT, COMPILE_KNOWLEDGE_SCHEMA
from skills.exercise_generator import GENERATE_EXERCISES_PROMPT, GENERATE_EXERCISES_SCHEMA

logger = logging.getLogger(__name__)

SKILL_DEFINITIONS: dict[str, dict] = {
    "compile_knowledge": {
        "schema": COMPILE_KNOWLEDGE_SCHEMA,
        "handler": COMPILE_KNOWLEDGE_PROMPT,
        "description": "将研究资料编撰成结构化的教学教材",
    },
    "generate_exercises": {
        "schema": GENERATE_EXERCISES_SCHEMA,
        "handler": GENERATE_EXERCISES_PROMPT,
        "description": "根据教学内容生成配套练习题",
    },
}


class SkillRegistry:
    def __init__(self):
        self.skills = SKILL_DEFINITIONS
        self.last_skill_context: dict[str, Any] = {}

    def get_schemas(self) -> list[dict]:
        return [info["schema"] for info in self.skills.values()]

    def execute(self, skill_name: str, arguments: dict) -> str:
        """执行 Skill：返回该 Skill 的提示词模板（填充参数后）"""
        if skill_name not in self.skills:
            return json.dumps({"error": f"未知技能: {skill_name}"}, ensure_ascii=False)

        skill = self.skills[skill_name]
        prompt_template = skill["handler"]

        filled_prompt = prompt_template
        for key, value in arguments.items():
            placeholder = "{{" + key + "}}"
            filled_prompt = filled_prompt.replace(placeholder, str(value))

        self.last_skill_context[skill_name] = {
            "arguments": arguments,
            "prompt": filled_prompt,
        }

        return filled_prompt

    def get_context(self, skill_name: str) -> dict | None:
        return self.last_skill_context.get(skill_name)
