"""
Subagent 工具 - 将大任务拆分为子任务，用独立上下文执行

核心思想：Agent 工作越久，messages 数组越臃肿。通过 task 工具将大任务
拆分为子任务，每个子任务在全新的 Subagent 中执行，message 隔离，不污染主对话。
Subagent 只拿到一份干净的任务描述，做完后把摘要返回给主 Agent。

主 Agent 工具集 = 子 Agent 工具集 + task 工具
子 Agent 工具集 = 所有本地工具（不含 task，防止递归爆炸）
"""
import json
import logging

from agent.llm_client import LLMClient
from config import SUBAGENT_MAX_TOOL_CALLS, build_subagent_system_prompt

from tools.web_search import web_search
from tools.web_fetch import fetch_webpage
from tools.file_tools import save_document
from tools.load_skill import load_skill
from tools.todo_write import todo_write

logger = logging.getLogger(__name__)

CHILD_TOOLS: dict[str, callable] = {
    "web_search": web_search,
    "fetch_webpage": fetch_webpage,
    "save_document": save_document,
    "load_skill": load_skill,
    "todo_write": todo_write,
}

CHILD_TOOL_SCHEMAS = []
from tools.web_search import TOOL_SCHEMA as S_SCHEMA; CHILD_TOOL_SCHEMAS.append(S_SCHEMA)
from tools.web_fetch import TOOL_SCHEMA as F_SCHEMA; CHILD_TOOL_SCHEMAS.append(F_SCHEMA)
from tools.file_tools import TOOL_SCHEMA as D_SCHEMA; CHILD_TOOL_SCHEMAS.append(D_SCHEMA)
from tools.load_skill import TOOL_SCHEMA as L_SCHEMA; CHILD_TOOL_SCHEMAS.append(L_SCHEMA)
from tools.todo_write import TOOL_SCHEMA as T_SCHEMA; CHILD_TOOL_SCHEMAS.append(T_SCHEMA)


def run_subagent(prompt: str) -> str:
    llm = LLMClient()
    system_prompt = build_subagent_system_prompt()

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": prompt},
    ]

    logger.info(f"Subagent 启动，prompt 长度: {len(prompt)} 字符")

    for iteration in range(SUBAGENT_MAX_TOOL_CALLS):
        response = llm.chat(messages=messages, tools=CHILD_TOOL_SCHEMAS)
        assistant_msg = llm.assistant_message(response)

        if assistant_msg is None:
            logger.warning("Subagent: LLM 返回空消息")
            break

        messages.append(assistant_msg)

        tool_calls = llm.parse_tool_calls(response)
        if not tool_calls:
            result_text = assistant_msg.get("content", "")
            logger.info(f"Subagent 完成，{iteration + 1} 轮，结果长度: {len(result_text)} 字符")
            return result_text

        for tc in tool_calls:
            tool_name = tc["name"]
            tool_args = tc["arguments"]
            tool_id = tc["id"]

            logger.debug(f"Subagent 调用工具: {tool_name}")

            try:
                handler = CHILD_TOOLS.get(tool_name)
                if handler:
                    result = handler(**tool_args)
                else:
                    result = json.dumps(
                        {"error": f"子 Agent 不支持工具: {tool_name}"},
                        ensure_ascii=False,
                    )
            except Exception as e:
                result = json.dumps({"error": f"工具执行出错: {e}"}, ensure_ascii=False)
                logger.exception(f"Subagent 工具 '{tool_name}' 失败")

            messages.append(llm.format_tool_result(tool_id, result))

    logger.warning(f"Subagent: 达到最大迭代次数 {SUBAGENT_MAX_TOOL_CALLS}")
    return "(Subagent 已达到最大工具调用次数，任务可能未完成)"


TASK_SCHEMA = {
    "type": "function",
    "function": {
        "name": "task",
        "description": (
            "将一项子任务委派给一个拥有全新上下文的子 Agent 执行。"
            "子 Agent 拥有与主 Agent 相同的工具（搜索、抓取、保存、加载技能），"
            "但上下文完全隔离，不会污染主对话的 messages 数组。"
            "当你需要将大任务拆分为多个独立子任务时使用此工具——"
            "例如：同时搜索多个不同主题的资料、为不同章节分别生成内容。"
            "子 Agent 完成后会将摘要返回给你。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "prompt": {
                    "type": "string",
                    "description": (
                        "给子 Agent 的完整任务描述，必须包含所有必要的上下文信息。"
                        "子 Agent 看不到主对话历史，只看到这条 prompt。"
                        "应明确说明：要做什么、预期输出格式、任何约束条件。"
                    ),
                },
            },
            "required": ["prompt"],
        },
    },
}
