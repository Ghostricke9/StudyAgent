"""
Agent 核心 - ReAct 模式的主循环
思路：LLM 决策 → 执行工具/Skill → 反馈结果 → LLM 再决策 → ... → 输出最终答案
"""
import json
import logging
from typing import Callable

from config import MAX_TOOL_CALLS, COMPACT_TOKEN_THRESHOLD, ENABLE_COMPACTION
from agent.llm_client import LLMClient
from agent.compactor import micro_compact, auto_compact, estimate_tokens
from tools.todo_write import mark_todo_round

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
            if ENABLE_COMPACTION:
                micro_compact(self.messages)

                current_tokens = estimate_tokens(self.messages)
                if current_tokens > COMPACT_TOKEN_THRESHOLD:
                    logger.warning(
                        f"触发 auto_compact: {current_tokens} tokens > 阈值 {COMPACT_TOKEN_THRESHOLD}"
                    )
                    self._notify("compact_start", "auto", str(current_tokens))
                    self.messages[:] = auto_compact(self.messages, self.llm)
                    self.messages.insert(0, {"role": "system", "content": self.system_prompt})
                    self._notify("compact_end", "auto", str(estimate_tokens(self.messages)))

            reminder = mark_todo_round(False)
            if reminder:
                self.messages.append({"role": "system", "content": f"[TodoWrite 提醒] {reminder}"})

            response = self.llm.chat(messages=self.messages, tools=self.tool_schemas)
            assistant_msg = self.llm.assistant_message(response)

            if assistant_msg is None:
                break

            self.messages.append(assistant_msg)

            tool_calls = self.llm.parse_tool_calls(response)
            if not tool_calls:
                content = assistant_msg.get("content", "")
                if ENABLE_COMPACTION and "[COMPACT]" in content:
                    logger.info("LLM 请求手动压缩 (Layer 3)")
                    self._notify("compact_start", "manual", str(estimate_tokens(self.messages)))
                    self.messages[:] = auto_compact(self.messages, self.llm)
                    self.messages.insert(0, {"role": "system", "content": self.system_prompt})
                    self._notify("compact_end", "manual", str(estimate_tokens(self.messages)))
                    continue
                return content

            had_todo = any(tc["name"] == "todo_write" for tc in tool_calls)

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

                self._notify("tool_end", tool_name, result[:200])

                if tool_name == "todo_write":
                    try:
                        from tools.todo_write import get_todo_manager
                        todo_items = get_todo_manager().items
                        self._notify("todo_update", "", json.dumps(todo_items, ensure_ascii=False))
                    except Exception:
                        pass

                self.messages.append(
                    self.llm.format_tool_result(tool_id, result)
                )

            mark_todo_round(had_todo)
            self._notify("round_end", "", str(iteration + 1))

        return "已达到最大工具调用次数，但任务可能未完成。请尝试更具体的问题。"

    def stream_run(self, user_input: str):
        self.messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": user_input},
        ]

        for iteration in range(MAX_TOOL_CALLS):
            if ENABLE_COMPACTION:
                micro_compact(self.messages)

                current_tokens = estimate_tokens(self.messages)
                if current_tokens > COMPACT_TOKEN_THRESHOLD:
                    logger.warning(
                        f"触发 auto_compact: {current_tokens} tokens > 阈值 {COMPACT_TOKEN_THRESHOLD}"
                    )
                    yield ("compact_start", {"mode": "auto", "tokens_before": current_tokens})
                    self.messages[:] = auto_compact(self.messages, self.llm)
                    self.messages.insert(0, {"role": "system", "content": self.system_prompt})
                    yield ("compact_end", {"mode": "auto", "tokens_after": estimate_tokens(self.messages)})

            reminder = mark_todo_round(False)
            if reminder:
                self.messages.append({"role": "system", "content": f"[TodoWrite 提醒] {reminder}"})

            response = self.llm.chat(messages=self.messages, tools=self.tool_schemas)
            assistant_msg = self.llm.assistant_message(response)

            if assistant_msg is None:
                break

            self.messages.append(assistant_msg)
            tool_calls = self.llm.parse_tool_calls(response)

            if not tool_calls:
                content = assistant_msg.get("content", "")
                if ENABLE_COMPACTION and "[COMPACT]" in content:
                    logger.info("LLM 请求手动压缩 (Layer 3)")
                    yield ("compact_start", {"mode": "manual", "tokens_before": estimate_tokens(self.messages)})
                    self.messages[:] = auto_compact(self.messages, self.llm)
                    self.messages.insert(0, {"role": "system", "content": self.system_prompt})
                    yield ("compact_end", {"mode": "manual", "tokens_after": estimate_tokens(self.messages)})
                    continue
                yield ("text", content)
                return

            had_todo = any(tc["name"] == "todo_write" for tc in tool_calls)

            for tc in tool_calls:
                yield ("tool_start", {"name": tc["name"], "args": tc["arguments"]})

                tool_name = tc["name"]
                tool_args = tc["arguments"]
                tool_id = tc["id"]

                try:
                    result = self.tool_executor(tool_name, tool_args)
                except Exception as e:
                    result = f"工具执行出错: {e}"

                yield ("tool_end", {"name": tool_name, "result_preview": result[:200]})

                if tool_name == "todo_write":
                    try:
                        from tools.todo_write import get_todo_manager
                        todo_items = get_todo_manager().items
                        yield ("todo_update", todo_items)
                    except Exception:
                        pass

                self.messages.append(self.llm.format_tool_result(tool_id, result))

            mark_todo_round(had_todo)
            yield ("round_end", {"round": iteration + 1})

        yield ("text", "已达到最大工具调用次数。")

    def _notify(self, event_type: str, name: str, detail: str):
        if self.on_step:
            self.on_step(event_type, name, detail)
