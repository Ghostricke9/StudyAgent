"""
LLM 客户端 - 封装 OpenAI 兼容 API，支持 Function Calling
"""
import json
import logging
from typing import Any

from openai import OpenAI

from config import OPENAI_API_KEY, OPENAI_BASE_URL, OPENAI_MODEL

logger = logging.getLogger(__name__)


class LLMClient:
    def __init__(self):
        self.client = OpenAI(api_key=OPENAI_API_KEY, base_url=OPENAI_BASE_URL)
        self.model = OPENAI_MODEL

    def chat(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        stream: bool = False,
    ):
        kwargs: dict[str, Any] = dict(
            model=self.model,
            messages=messages,
        )
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"
        if stream:
            kwargs["stream"] = True
            kwargs["stream_options"] = {"include_usage": True}
            return self.client.chat.completions.create(**kwargs)

        return self.client.chat.completions.create(**kwargs)

    def chat_stream(self, messages: list[dict], tools: list[dict] | None = None):
        """流式聊天，逐块返回 delta 内容"""
        return self.chat(messages=messages, tools=tools, stream=True)

    @staticmethod
    def format_tool_result(tool_call_id: str, result: str) -> dict:
        return {
            "role": "tool",
            "tool_call_id": tool_call_id,
            "content": result,
        }

    @staticmethod
    def parse_tool_calls(response) -> list[dict]:
        """从响应中解析出 tool_calls 列表"""
        choice = response.choices[0]
        message = choice.message
        if not message.tool_calls:
            return []

        return [
            {
                "id": tc.id,
                "name": tc.function.name,
                "arguments": json.loads(tc.function.arguments),
            }
            for tc in message.tool_calls
        ]

    @staticmethod
    def assistant_message(response) -> dict | None:
        choice = response.choices[0]
        msg = choice.message

        if not msg.content and not msg.tool_calls and not getattr(msg, "reasoning_content", None):
            return None

        result: dict = {"role": "assistant", "content": msg.content or ""}

        reasoning = getattr(msg, "reasoning_content", None)
        if reasoning:
            result["reasoning_content"] = reasoning

        if msg.tool_calls:
            result["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    },
                }
                for tc in msg.tool_calls
            ]

        return result

    @staticmethod
    def build_tool_schema(name: str, description: str, parameters: dict) -> dict:
        return {
            "type": "function",
            "function": {
                "name": name,
                "description": description,
                "parameters": {"type": "object", "properties": parameters, "required": list(parameters.keys())},
            },
        }
