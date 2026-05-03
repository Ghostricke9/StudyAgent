"""
load_skill 工具 - Layer 2 渐进式披露
LLM 调用此工具获取 SKILL.md 的完整正文内容
"""
import json
import logging

from skills.registry import SKILL_LOADER

logger = logging.getLogger(__name__)


def load_skill(name: str) -> str:
    """按需加载技能的完整正文"""
    content = SKILL_LOADER.get_content(name)
    return content


TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "load_skill",
        "description": (
            "加载特定技能的详细使用说明。当你需要了解如何处理某项复杂任务时，"
            "先调用此工具获取技能的完整指导，然后按照指导完成任务。"
            "可用技能已在系统提示词中列出。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "技能名称，如 'knowledge-compiler' 或 'exercise-generator'",
                },
            },
            "required": ["name"],
        },
    },
}
