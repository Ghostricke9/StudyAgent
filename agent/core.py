"""
Agent 核心 - ReAct 模式的主循环
思路：LLM 决策 → 执行工具/Skill → 反馈结果 → LLM 再决策 → ... → 输出最终答案
"""
import json
import logging
from typing import Callable

from config import MAX_TOOL_CALLS
from agent.llm_client import LLMClient

logger = logging.getLogger(__name__)

ToolExecutor = Callable[[str, dict], str]


class Agent:
    def __init__(
        self,
        llm: LLMClient | None = None,
        tool_schemas: list[dict] | None = None,
        tool_executor: ToolExecutor | None = None,
        on_step: Callable[[str, str, str], None] | None = None,
        system_prompt: str = "",
    ):
        self.llm = llm or LLMClient()
        self.tool_schemas = tool_schemas or []
        self.tool_executor = tool_executor or (lambda name, args: "")
        self.on_step = on_step
        self.system_prompt = system_prompt
        self.messages: list[dict] = []

    def run(self, user_input: str) -> str:
        self.messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": user_input},
        ]

        for iteration in range(MAX_TOOL_CALLS):
            response = self.llm.chat(messages=self.messages, tools=self.tool_schemas)
            assistant_msg = self.llm.assistant_message(response)

            if assistant_msg is None:
                break

            self.messages.append(assistant_msg)

            tool_calls = self.llm.parse_tool_calls(response)
            if not tool_calls:
                return assistant_msg.get("content", "")

            for tc in tool_calls:
                tool_name = tc["name"]
                tool_args = tc["arguments"]
                tool_id = tc["id"]

                self._notify("tool_start", tool_name, json.dumps(tool_args, ensure_ascii=False))

                try:
                    result = self.tool_executor(tool_name, tool_args)
                except Exception as e:
                    result = f"工具执行出错: {e}"
                    logger.exception(f"Tool '{tool_name}' failed")

                self._notify("tool_end", tool_name, result[:500])

                self.messages.append(
                    self.llm.format_tool_result(tool_id, result)
                )

        return "已达到最大工具调用次数，但任务可能未完成。请尝试更具体的问题。"

    def stream_run(self, user_input: str):
        """流式运行，逐步 yield (type, content)"""
        self.messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": user_input},
        ]

        for iteration in range(MAX_TOOL_CALLS):
            response = self.llm.chat(messages=self.messages, tools=self.tool_schemas)
            assistant_msg = self.llm.assistant_message(response)

            if assistant_msg is None:
                break

            self.messages.append(assistant_msg)
            tool_calls = self.llm.parse_tool_calls(response)

            if not tool_calls:
                yield ("text", assistant_msg.get("content", ""))
                return
            for tc in tool_calls:
                yield ("tool_start", {"name": tc["name"], "args": tc["arguments"]})

                tool_name = tc["name"]
                tool_args = tc["arguments"]
                tool_id = tc["id"]

                try:
                    result = self.tool_executor(tool_name, tool_args)
                except Exception as e:
                    result = f"工具执行出错: {e}"

                yield ("tool_end", {"name": tool_name, "result_preview": result[:500]})
                self.messages.append(self.llm.format_tool_result(tool_id, result))

        yield ("text", "已达到最大工具调用次数。")

    def _notify(self, event_type: str, name: str, detail: str):
        if self.on_step:
            self.on_step(event_type, name, detail)
